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
from .gpt_writer import apply_to_tower, _is_request
from .operation_receipts import intent_id, payload_hash, build_receipt, envelope_effect_id, OperationReceiptError


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
    def test_rejects_noncanonical_intent_identity_before_delivery(self):
        for identity in (' ', '\t\n', '\u00a0', ' SYNTHETIC-CANARY',
                         'SYNTHETIC-CANARY ', '\tSYNTHETIC-CANARY',
                         'SYNTHETIC-CANARY\n', '\u2003SYNTHETIC-CANARY\u2003'):
            with self.subTest(identity=repr(identity)):
                envelope={**ENV,'intent_id':identity};before=copy.deepcopy(envelope)
                with self.assertRaisesRegex(ValueError,'STABLE_INTENT_ID_REQUIRED'):
                    prepare(envelope,runtime_role='CHATGPT',allowed_kinds={'BOARD_POST'})
                self.assertEqual(envelope,before)
    def test_valid_identity_matches_writer_without_changing_approved_payload(self):
        for identity in ('SYNTHETIC-CANARY','science/ref:1','canário-café','valid internal space'):
            with self.subTest(identity=identity):
                envelope={**ENV,'intent_id':identity};before=copy.deepcopy(envelope)
                prepared=prepare(envelope,runtime_role='CHATGPT',allowed_kinds={'BOARD_POST'})
                self.assertEqual(prepared['intent_id'],intent_id(envelope,'fallback'))
                self.assertEqual(json.loads(prepared['raw']),before)
                self.assertEqual(prepared['payload_sha256'],payload_hash(before))
                self.assertEqual(envelope,before)
    def test_raw_writer_dispatch_cannot_hide_in_an_authorized_envelope(self):
        attacks = [
            {'document':'evolution/synthetic-outside-board.json','merge':{'unexpected':True}},
            {'entity_kind':'test','entity_name':'SYNTHETIC','changes':{'state':'DONE'}},
            {'nexo_operation':'HANDOFF_CREATE','handoff':{}},
            {'nexo_operation':'HANDOFF_TRANSITION','transition':{}},
            {'nexo_operation':'EXECUTION_OBSERVATION_ASSESSMENT'},
            {'nexo_operation':'OPERATIONAL_CANARY'},
        ]
        for fields in attacks:
            with self.subTest(fields=list(fields)):
                envelope={**ENV,**fields}
                self.assertTrue(_is_request(envelope))
                with self.assertRaisesRegex(ValueError,'UNSUPPORTED_ENVELOPE_FIELDS'):
                    prepare(envelope,runtime_role='CHATGPT',allowed_kinds={'BOARD_POST'})
        for fields in ({'merge':{}},{'writer_role':'DENER'},{'request':{}},{'envelope':{}}):
            with self.assertRaisesRegex(ValueError,'UNSUPPORTED_ENVELOPE_FIELDS'):
                prepare({**ENV,**fields},runtime_role='CHATGPT',allowed_kinds={'BOARD_POST'})
    def test_batch_requires_separately_authorized_child_deliveries(self):
        for kind in ('BATCH','batch'):
            envelope={**ENV,'kind':kind,'payload':{'items':[{**ENV,'source':'DENER'}]}}
            with self.assertRaisesRegex(ValueError,'BATCH_REQUIRES_INDIVIDUAL_DELIVERY'):
                prepare(envelope,runtime_role='CHATGPT',allowed_kinds={kind,'BOARD_POST'})
    def test_unknown_kind_cannot_authorize_writer_payload_inference(self):
        from .inbox_apply import _infer_kind
        payload={'test_id':'SYNTHETIC','result':{'verdict':'PROMOTED'}}
        self.assertEqual(_infer_kind(payload),'MUTATION_PROPOSAL')
        with self.assertRaisesRegex(ValueError,'UNSUPPORTED_PROPOSAL_KIND'):
            prepare({**ENV,'kind':'UNRECOGNIZED_NOTE','payload':payload},
                    runtime_role='CHATGPT',allowed_kinds={'UNRECOGNIZED_NOTE'})
    def test_handoff_payload_role_is_bound_in_direct_wrapped_and_alias_forms(self):
        for kind, wrapper, field in (
                ('HANDOFF','handoff','from_role'), ('NEXO_HANDOFF','handoff','from_role'),
                ('AGENT_HANDOFF','handoff','from_role'),
                ('HANDOFF_TRANSITION','transition','writer_role'),
                ('HANDOFF_ACK','transition','writer_role'), ('HANDOFF_DONE','transition','writer_role'),
                ('HANDOFF_FAILED','transition','writer_role')):
            for wrapped in (False,True):
                with self.subTest(kind=kind,wrapped=wrapped):
                    body={field:'EXECUTOR'}
                    payload={wrapper:body} if wrapped else body
                    envelope={**ENV,'kind':kind,'source':'ADVISOR','payload':payload}
                    with self.assertRaisesRegex(PermissionError,'PAYLOAD_ROLE_NOT_AUTHORIZED'):
                        prepare(envelope,runtime_role='ADVISOR',allowed_kinds={kind})
    def test_supersedes_preserves_explicit_correction_identity(self):
        envelope={**ENV,'supersedes':'OR-'+'a'*32}
        prepared=prepare(envelope,runtime_role='CHATGPT',allowed_kinds={'BOARD_POST'})
        self.assertEqual(json.loads(prepared['raw']),envelope)
        for value in (' ', ' OR-x', 123):
            with self.assertRaisesRegex(ValueError,'SUPERSEDES_ID_INVALID'):
                prepare({**ENV,'supersedes':value},runtime_role='CHATGPT',allowed_kinds={'BOARD_POST'})
    def test_created_at_rejects_non_utc_or_invalid_chronology(self):
        for stamp in (None, True, 123, {'date':'today'}, '', 'not-a-date', '2026-10-07',
                      '2026-10-07T01:00:00', '2026-10-07T01:00:00+01:00',
                      '2026-10-07T01:00:00-00:00', '2026-02-30T00:00:00Z',
                      '2026-10-07T25:00:00Z', ' 2026-10-07T00:00:00Z'):
            with self.subTest(stamp=stamp), self.assertRaisesRegex(ValueError,'CREATED_AT_UTC_REQUIRED'):
                prepare({**ENV,'created_at':stamp},runtime_role='CHATGPT',allowed_kinds={'BOARD_POST'})
    def test_created_at_valid_utc_bytes_are_preserved(self):
        for stamp in ('2026-10-07T00:00:00Z','2026-10-07T01:40:40.885204Z',
                      '2026-10-07T00:00:00+00:00'):
            with self.subTest(stamp=stamp):
                envelope={**ENV,'created_at':stamp}
                prepared=prepare(envelope,runtime_role='CHATGPT',allowed_kinds={'BOARD_POST'})
                self.assertEqual(json.loads(prepared['raw']),envelope)
    def test_contest_actor_fields_cannot_change_authorized_runtime_role(self):
        for kind in ('CONTEST','REFUTATION'):
            for fields in ({'source':'SENTINEL'},{'referee':'SENTINEL'},
                           {'source':'REFEREE_1','referee':'SENTINEL'}, {'source':True}):
                with self.subTest(kind=kind,fields=fields):
                    envelope={**ENV,'kind':kind,'source':'REFEREE_1',
                              'payload':{'test_id':'SYNTHETIC',**fields}}
                    with self.assertRaisesRegex(PermissionError,'PAYLOAD_ROLE_NOT_AUTHORIZED'):
                        prepare(envelope,runtime_role='REFEREE_1',allowed_kinds={kind})
    def test_explicitly_authorized_contest_roles_remain_supported(self):
        for role in ('REFEREE_1','SENTINEL'):
            for fields in ({},{'source':role},{'referee':role},{'source':role,'referee':role}):
                with self.subTest(role=role,fields=fields):
                    envelope={**ENV,'kind':'CONTEST','source':role,'payload':{'test_id':'SYNTHETIC',**fields}}
                    if role=='SENTINEL' and not fields:
                        with self.assertRaisesRegex(PermissionError,'PAYLOAD_ROLE_NOT_AUTHORIZED'):
                            prepare(envelope,runtime_role=role,allowed_kinds={'CONTEST'})
                        continue
                    self.assertEqual(json.loads(prepare(envelope,runtime_role=role,
                        allowed_kinds={'CONTEST'})['raw']),envelope)
    def test_nested_command_fields_and_intent_wrapper_are_data_to_actual_writer(self):
        for kind in ('BOARD_POST','INTENT','OPERATOR_INTENT'):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);(root/'CONTROL.json').write_text(json.dumps({'truth_owner':'TOWER_V06@GOOGLE_DRIVE_PRIVATE'}))
                raw=json.dumps(build_live_tower_payload(root)).encode()
                nested={'kind':'BATCH','source':'DENER','document':'evolution/synthetic-outside-board.json',
                        'merge':{'unexpected':True},'items':[{'source':'DENER','kind':'HANDOFF'}]}
                payload={**ENV['payload'],'envelope':nested,'request':nested,
                         'document':nested['document'],'merge':nested['merge'],'source':'DENER'}
                envelope={**ENV,'kind':kind,'payload':payload}
                prepared=prepare(envelope,runtime_role='CHATGPT',allowed_kinds={kind})
                item={**json.loads(prepared['raw']),'_inbox_source':'DRIVE','_inbox_id':'FILE',
                      '_inbox_name':prepared['filename']}
                written,report=apply_to_tower(raw,[item]);self.assertFalse(report['rejected'])
                tower=json.loads(written)
                self.assertNotIn('evolution/synthetic-outside-board.json',tower['files'])
                events=[e['value'] for p,e in tower['files'].items() if p.startswith('events/')]
                self.assertFalse(any(e.get('event_type')=='HANDOFF_CREATED' for e in events))
                self.assertEqual(receipt_status(tower,prepared)['stage'],'APPLIED')
    def test_actual_writer_accepts_handoff_only_as_its_authorized_roles(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'CONTROL.json').write_text(json.dumps({'truth_owner':'TOWER_V06@GOOGLE_DRIVE_PRIVATE'}))
            raw=json.dumps(build_live_tower_payload(root)).encode()
            body={'request_id':'SYNTHETIC-HANDOFF','from_role':'ADVISOR','to_role':'EXECUTOR',
                  'handoff_type':'TASK','entity_ref':'WORK-SYNTHETIC','thread_id':'synthetic-thread',
                  'summary_plain':'Review the example','why_it_matters':'Check the role guard',
                  'next_action':'Read the example'}
            envelope={**ENV,'kind':'HANDOFF','source':'ADVISOR','payload':{'handoff':body}}
            prepared=prepare(envelope,runtime_role='ADVISOR',allowed_kinds={'HANDOFF'})
            item={**json.loads(prepared['raw']),'_inbox_source':'DRIVE','_inbox_id':'F1','_inbox_name':prepared['filename']}
            raw,report=apply_to_tower(raw,[item]);self.assertFalse(report['rejected'])
            tower=json.loads(raw)
            event=next(e['value'] for p,e in tower['files'].items()
                       if p.startswith('events/') and e['value'].get('event_type')=='HANDOFF_CREATED')
            self.assertEqual(event['from_role'],'ADVISOR')
            transition={**ENV,'kind':'HANDOFF_DONE','source':'EXECUTOR','intent_id':'SYNTHETIC-DONE',
                        'payload':{'transition':{'handoff_id':event['handoff_id'],'writer_role':'EXECUTOR'}}}
            prepared=prepare(transition,runtime_role='EXECUTOR',allowed_kinds={'HANDOFF_DONE'})
            item={**json.loads(prepared['raw']),'_inbox_source':'DRIVE','_inbox_id':'F2','_inbox_name':prepared['filename']}
            raw,report=apply_to_tower(raw,[item]);self.assertFalse(report['rejected'])
            self.assertEqual(receipt_status(json.loads(raw),prepared)['stage'],'APPLIED')
    def test_denied_write_makes_no_create(self):
        t=Transport();t.can_write=False
        with self.assertRaises(PermissionError): deliver(self.prepared,t,tower=self.tower,journal={})
        self.assertEqual(t.calls,0)
    def test_missing_session_cannot_trigger_ambient_credential_discovery(self):
        with patch('runtime.nexo_agent_api.inbox_client.DriveInbox') as inbox:
            with self.assertRaisesRegex(ValueError,'AUTHENTICATED_DRIVE_SESSION_REQUIRED'):
                DriveInboxClientTransport(None,can_write=True,checkpoint=lambda journal:None)
            inbox.assert_not_called()
    def test_current_and_legacy_receipts_prevent_redundant_delivery(self):
        receipt=build_receipt(intent=self.prepared['intent_id'],
            payload_sha256=self.prepared['payload_sha256'],effect=envelope_effect_id(self.prepared['intent_id']),
            outcome='APPLIED',source_revision=None,result_revision=None)
        for parent in ('operations/receipts','mutations/receipts/operations','mutations/receipts'):
            for minimal in (False,True):
                with self.subTest(parent=parent,minimal=minimal):
                    row=copy.deepcopy(receipt)
                    if minimal:
                        for key in ('contract','stage','reason_code','source_revision','result_revision',
                                    'occurred_at','observed_at','visibility','retry_condition','supersedes'):
                            row.pop(key,None)
                    tower={'files':{parent+'/'+receipt['receipt_id']+'.json':{'value':row}}}
                    t=Transport();status=deliver(self.prepared,t,tower=tower,journal={})
                    self.assertEqual(status['stage'],'APPLIED')
                    self.assertTrue(status['entity_readback_required']);self.assertEqual(t.calls,0)
    def test_legacy_unrelated_records_are_ignored_but_current_corruption_is_not_absence(self):
        for parent in ('mutations/receipts/operations','mutations/receipts'):
            tower={'files':{parent+'/unrelated.json':{'value':{'legacy_mutation':True}}}}
            self.assertEqual(receipt_status(tower,self.prepared)['stage'],'UNOBSERVED')
        tower={'files':{'operations/receipts/broken.json':{'value':{}}}}
        with self.assertRaisesRegex(OperationReceiptError,'OPERATION_RECEIPT_LEDGER_INVALID'):
            receipt_status(tower,self.prepared)
    def test_invalid_matching_receipt_is_not_reported_as_applied(self):
        receipt=build_receipt(intent=self.prepared['intent_id'],
            payload_sha256=self.prepared['payload_sha256'],effect=envelope_effect_id(self.prepared['intent_id']),
            outcome='APPLIED',source_revision=None,result_revision=None)
        receipt['contract']='UNTRUSTED'
        for parent in ('operations/receipts','mutations/receipts/operations','mutations/receipts'):
            with self.subTest(parent=parent), self.assertRaisesRegex(OperationReceiptError,'OPERATION_RECEIPT_LEDGER_INVALID'):
                receipt_status({'files':{parent+'/invalid.json':{'value':receipt}}},self.prepared)
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
            self.assertEqual(status['receipt']['intent_id'],self.prepared['intent_id'])
            transport=Transport();transport.can_write=False
            self.assertEqual(deliver(self.prepared,transport,tower=tower,journal={})['stage'],'APPLIED')
            self.assertEqual(transport.calls,0)
            post=tower['files']['evolution/board.json']['value']['posts'][0];self.assertTrue(post['private']);self.assertEqual(post['id'],ENV['payload']['id'])
            replay_bytes,replay=apply_to_tower(written,[item]);self.assertIsNone(replay_bytes)
            self.assertEqual(replay['operation_receipts'][0]['outcome'],'ALREADY_APPLIED')
            replay_tower=copy.deepcopy(tower)
            for entry in replay_tower['files'].values():
                if entry.get('value',{}).get('receipt_id')==status['receipt']['receipt_id']:
                    entry['value']['outcome']='ALREADY_APPLIED'
            self.assertTrue(receipt_status(replay_tower,self.prepared)['entity_readback_required'])
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
