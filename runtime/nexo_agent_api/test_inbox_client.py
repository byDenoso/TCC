import copy
import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from .inbox_client import INBOX_ID, prepare, deliver, receipt_status, DriveInboxClientTransport
from .drive_transport import TowerTransportError
from .live_tower import build_live_tower_payload
from .gpt_writer import apply_to_tower


ENV = {'kind':'BOARD_POST','source':'CHATGPT','intent_id':'SYNTHETIC-CANARY',
       'created_at':'2026-10-07T00:00:00Z',
       'payload':{'id':'SYNTHETIC-POST','to':'DENER','text':'synthetic delivery check','private':True}}


class Transport:
    can_write = True
    def __init__(self):
        self.files = {}; self.calls = 0; self.timeout = False; self.checkpoints = []
    def lookup(self, filename, inbox):
        return [k for k,v in self.files.items() if v['filename']==filename]
    def checkpoint(self, journal):
        self.checkpoints.append(copy.deepcopy(journal))
    def create(self, raw, filename, inbox):
        self.calls += 1
        self.files['FILE'] = {'raw':raw,'filename':filename,'mime_type':'application/json','parent_ids':[inbox]}
        if self.timeout: raise TimeoutError()
        return 'FILE'
    def read(self, identity): return self.files[identity]


class ClientTests(unittest.TestCase):
    def setUp(self):
        self.prepared = prepare(ENV,runtime_role='CHATGPT',allowed_kinds={'BOARD_POST'})
        self.tower = {'files':{},'revision':'sha256:'+'a'*64}
    def test_schema_and_authorization(self):
        for change in [{'source':'EXECUTOR'},{'kind':'TEST_BATTERY'}]:
            with self.assertRaises(PermissionError): prepare({**ENV,**change},runtime_role='CHATGPT',allowed_kinds={'BOARD_POST'})
        for change in [{'intent_id':''},{'payload':None},{'_inbox_source':'DRIVE'}]:
            with self.assertRaises(ValueError): prepare({**ENV,**change},runtime_role='CHATGPT',allowed_kinds={'BOARD_POST'})
    def test_denied_write_makes_no_create(self):
        t=Transport();t.can_write=False
        with self.assertRaises(PermissionError): deliver(self.prepared,t,tower=self.tower,journal={})
        self.assertEqual(t.calls,0)
    def test_delivery_readback_and_idempotence(self):
        t=Transport();j={}
        for _ in range(2): self.assertEqual(deliver(self.prepared,t,tower=self.tower,journal=j)['stage'],'DELIVERED')
        self.assertEqual(t.calls,1);self.assertEqual(t.checkpoints[0]['stage'],'SENDING')
    def test_concurrent_same_client_creates_once(self):
        t=Transport();j={};out=[]
        threads=[threading.Thread(target=lambda:out.append(deliver(self.prepared,t,tower=self.tower,journal=j))) for _ in range(6)]
        for thread in threads:thread.start()
        for thread in threads:thread.join()
        self.assertEqual(len(out),6);self.assertEqual(t.calls,1)
    def test_timeout_reconciles_existing_without_second_create(self):
        t=Transport();t.timeout=True;j={}
        self.assertEqual(deliver(self.prepared,t,tower=self.tower,journal=j)['stage'],'OUTCOME_UNKNOWN')
        self.assertEqual(deliver(self.prepared,t,tower=self.tower,journal=j)['stage'],'DELIVERED');self.assertEqual(t.calls,1)
    def test_timeout_without_observed_file_never_recreates(self):
        t=Transport();j={**{k:self.prepared[k] for k in ('intent_id','payload_sha256')},'stage':'OUTCOME_UNKNOWN'}
        self.assertEqual(deliver(self.prepared,t,tower=self.tower,journal=j)['stage'],'OUTCOME_UNKNOWN');self.assertEqual(t.calls,0)
    def test_wrong_journal_or_parent_rejected(self):
        t=Transport()
        with self.assertRaises(ValueError): deliver(self.prepared,t,tower=self.tower,journal={'intent_id':'other'})
        deliver(self.prepared,t,tower=self.tower,journal={});t.files['FILE']['parent_ids']=['OTHER']
        with self.assertRaisesRegex(ValueError,'PARENT'): deliver(self.prepared,t,tower=self.tower,journal={})
    def test_changed_payload_same_identity_refuses_duplicate_create(self):
        t=Transport();deliver(self.prepared,t,tower=self.tower,journal={})
        changed=prepare({**ENV,'payload':{**ENV['payload'],'text':'different'}},runtime_role='CHATGPT',allowed_kinds={'BOARD_POST'})
        self.assertEqual(changed['filename'],self.prepared['filename'])
        with self.assertRaisesRegex(ValueError,'READBACK_MISMATCH'):deliver(changed,t,tower=self.tower,journal={})
        self.assertEqual(t.calls,1)
    def test_actual_writer_receipt_private_board_and_replay(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'CONTROL.json').write_text(json.dumps({'truth_owner':'TOWER_V06@GOOGLE_DRIVE_PRIVATE'}))
            raw=json.dumps(build_live_tower_payload(root)).encode()
            item={**ENV,'_inbox_source':'DRIVE','_inbox_id':'FILE','_inbox_name':self.prepared['filename']}
            written,report=apply_to_tower(raw,[item]);self.assertFalse(report['rejected'])
            tower=json.loads(written);status=receipt_status(tower,self.prepared)
            self.assertEqual(status['stage'],'APPLIED');self.assertTrue(status['entity_readback_required'])
            post=tower['files']['evolution/board.json']['value']['posts'][0];self.assertTrue(post['private']);self.assertEqual(post['id'],ENV['payload']['id'])
            replay_bytes,replay=apply_to_tower(written,[item]);self.assertIsNone(replay_bytes)
            self.assertEqual(replay['operation_receipts'][0]['outcome'],'ALREADY_APPLIED')
            modified={**item,'payload':{**item['payload'],'text':'changed'}}
            _,rejection=apply_to_tower(written,[modified]);self.assertTrue(rejection['rejected'])
    def test_authenticated_adapter_uses_one_raw_multipart_create_and_pinned_destination(self):
        class Response:
            status_code=200
            def json(self):return {'id':'NEW-FILE'}
        class Session:
            def post(self,url,**kwargs):
                self.call=(url,kwargs);return Response()
        session=Session();transport=DriveInboxClientTransport(session,can_write=True,checkpoint=lambda j:None)
        with patch.object(transport.inbox,'_inbox',return_value=INBOX_ID):
            identity=transport.create(self.prepared['raw'],self.prepared['filename'],INBOX_ID)
        self.assertEqual(identity,'NEW-FILE');url,args=session.call
        self.assertEqual(url,'https://www.googleapis.com/upload/drive/v3/files')
        self.assertIn(self.prepared['raw'],args['data']);self.assertIn(INBOX_ID.encode(),args['data'])
        self.assertEqual(args['params']['uploadType'],'multipart')
        transport.can_write=False
        with self.assertRaises(PermissionError):transport.create(b'{}','x.json',INBOX_ID)
    def test_remote_permission_denial_is_terminal_and_preserves_exact_journal(self):
        class Denied(Transport):
            def create(self,*args):raise TowerTransportError('INBOX_CREATE',403,'OPERATOR_REAUTHORIZATION')
        journal={}
        with self.assertRaises(TowerTransportError):deliver(self.prepared,Denied(),tower=self.tower,journal=journal)
        self.assertEqual(journal['stage'],'PERMISSION_DENIED')
        with self.assertRaises(PermissionError):deliver(self.prepared,Transport(),tower=self.tower,journal=journal)

    def test_definitive_remote_create_rejection_is_distinct_from_timeout(self):
        class Response:
            def __init__(self,code):self.status_code=code
        class Session:
            def post(self,*args,**kwargs):self.calls+=1;return Response(self.code)
        for code in (400,404,409,422):
            with self.subTest(code=code):
                session=Session();session.calls=0;session.code=code;journal={}
                transport=DriveInboxClientTransport(session,can_write=True,checkpoint=lambda j:None)
                transport.lookup=lambda *args:[]
                with patch.object(transport.inbox,'_inbox',return_value=INBOX_ID):
                    result=deliver(self.prepared,transport,tower=self.tower,journal=journal)
                    self.assertEqual(result['stage'],'CREATE_REJECTED')
                    self.assertEqual(result['status_code'],code)
                    self.assertEqual(result['retry'],'OPERATOR_CORRECTION')
                    self.assertEqual(deliver(self.prepared,transport,tower=self.tower,journal=journal),result)
                    self.assertEqual(session.calls,1)


if __name__=='__main__':unittest.main()
