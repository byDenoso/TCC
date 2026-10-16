"""Offline failure-injection tests. The fake transport does not prove Google ACLs."""
import copy
import unittest
from runtime.nexo_agent_api import doc_persistence as dp

class FakeTransport:
    staging_folder_id='staging123'
    def __init__(self):
        self.docs={}; self.created=0; self.filled=0; self.moved=0; self.snapshots=[]
        self.lose_create_ack=False; self.lose_move_ack=False; self.deny=False
    def checkpoint(self,journal): self.snapshots.append(copy.deepcopy(journal))
    def verify_destination(self,folder):
        if self.deny: raise PermissionError('injected denial')
        return True
    def lookup(self,title): return [key for key,value in self.docs.items() if value['title']==title]
    def create(self,title):
        self.created+=1; key='doc'+str(self.created)
        self.docs[key]={'raw':b'','title':title,'revision':'r1','mime_type':dp.DOC_MIME,
                        'parent_ids':[self.staging_folder_id],'private_verified':True}
        if self.lose_create_ack:
            self.lose_create_ack=False; raise TimeoutError('injected lost create acknowledgement')
        return key
    def read(self,key): return copy.deepcopy(self.docs[key])
    def fill(self,key,text,revision):
        assert self.docs[key]['revision']==revision
        self.filled+=1; self.docs[key]['raw']=text.encode(); self.docs[key]['revision']='r2'
    def move(self,key,folder):
        self.moved+=1; self.docs[key]['parent_ids']=[folder]
        if self.lose_move_ack:
            self.lose_move_ack=False; raise TimeoutError('injected lost move acknowledgement')

class TransportAudit(unittest.TestCase):
    def setUp(self):
        self.prepared=dp.prepare_document(b'{"audit":true}',stable_id='AUDIT-TRANSPORT-V1',folder_id='folder123')
        self.transport=FakeTransport(); self.journal={}
    def send(self): return dp.publish_document(self.prepared,self.transport,journal=self.journal)
    def test_idempotent_delivery(self):
        self.assertEqual(self.send()['stage'],'DELIVERED')
        self.assertEqual(self.send()['stage'],'DELIVERED')
        self.assertEqual((self.transport.created,self.transport.filled,self.transport.moved),(1,1,1))
    def test_lost_create_ack_reconciles(self):
        self.transport.lose_create_ack=True
        self.assertEqual(self.send()['stage'],'OUTCOME_UNKNOWN')
        self.assertEqual(self.send()['stage'],'DELIVERED')
        self.assertEqual(self.transport.created,1)
    def test_lost_move_ack_reconciles(self):
        self.transport.lose_move_ack=True
        self.assertEqual(self.send()['stage'],'OUTCOME_UNKNOWN')
        self.assertEqual(self.send()['stage'],'DELIVERED')
        self.assertEqual(self.transport.moved,1)
    def test_denial_not_automatically_retried(self):
        self.transport.deny=True
        with self.assertRaises(PermissionError): self.send()
        self.assertEqual(self.journal['stage'],'PERMISSION_DENIED')
        self.transport.deny=False
        with self.assertRaises(PermissionError): self.send()
        self.assertEqual(self.transport.created,0)
    def test_duplicate_identity_rejected(self):
        self.transport.create(self.prepared['title']); self.transport.create(self.prepared['title'])
        with self.assertRaises(dp.PackageError): self.send()
        self.assertEqual(self.transport.filled,0)
    def test_divergent_nonempty_content_never_overwritten(self):
        key=self.transport.create(self.prepared['title'])
        self.transport.docs[key]['raw']=b'{"other":true}'
        with self.assertRaises(dp.PackageError): self.send()
        self.assertEqual(self.transport.docs[key]['raw'],b'{"other":true}')
    def package(self):
        return dp.pack(artifact_id='AUDIT-PACK-V1',campaign_id='CAMP-DDE-ANOMALIES-MEGA-20260922',
            created_at='2026-10-16T10:00:00Z',producer_role='ENGENHEIRO',provenance={'classification':'TECHNICAL_QA'},
            files=[{'name':'audit.txt','mime_type':'text/plain','content':b'nonempty audit\n'}])
    def test_package_roundtrip_and_bom(self):
        package=self.package(); raw=dp.canonical(package)
        self.assertEqual(dp.parse_package(b'\xef\xbb\xbf'+raw+b'\n'),package)
    def test_modified_bytes_fail_hash(self):
        package=self.package(); package['files'][0]['content_b64']='Y2hhbmdlZA=='
        with self.assertRaises(dp.PackageError): dp.validate_package(package)
if __name__=='__main__': unittest.main()
