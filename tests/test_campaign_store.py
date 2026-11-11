import copy
import hashlib
import json
import tempfile
import unittest
from email import policy
from email.parser import BytesParser
from pathlib import Path
from unittest.mock import patch

from runtime.nexo_execution.campaign_store import (
    CampaignError, DriveCampaignStore, FOLDER, DOC, API, UPLOAD,
    make_event, validate_event, json_bytes, parse_event, local_lock,
)


def event(**updates):
    args = dict(campaign_id='CAMP-SYNTHETIC', entity_id='TEST-SYNTHETIC', kind='METHOD', role='CIENTISTA',
                actor_id='scientist-fixture', data={'question':'Synthetic transport fixture only', 'threshold':0.05},
                atlas_scope='PRIVATE', timestamp_utc='2026-10-15T02:00:00Z')
    args.update(updates)
    return make_event(**args)


class Response:
    def __init__(self, status=200, data=None, raw=b'', headers=None):
        self.status_code, self.data, self.raw = status, data, raw
        self.headers, self.closed = headers or {}, False
    def json(self): return copy.deepcopy(self.data)
    def iter_content(self, size):
        for i in range(0,len(self.raw),size): yield self.raw[i:i+size]
    def close(self): self.closed = True


class FakeDrive:
    def __init__(self):
        self.files = {
            'root':{'id':'root','name':'Campaigns','mimeType':FOLDER,'trashed':False,'parents':[],'version':'1'},
            'folder':{'id':'folder','name':'CAMP-SYNTHETIC','mimeType':FOLDER,'parents':['root'],'trashed':False,'version':'1'},
        }
        self.raw, self.calls, self.responses = {}, [], []
        self.generated, self.created, self.lost, self.corrupt, self.block = 0,0,False,False,None
        self.list_pages, self.page_index = None, 0
    def response(self, *args, **kwargs):
        r=Response(*args,**kwargs);self.responses.append(r);return r
    def put(self, file_id, raw, mime='application/json', name='event.json'):
        self.raw[file_id]=raw
        self.files[file_id]=dict(id=file_id,name=name,mimeType=mime,parents=['folder'],trashed=False,version='1',
                                size=str(len(raw)),md5Checksum=hashlib.md5(raw).hexdigest())
    def request(self, method, url, **kwargs):
        self.calls.append((method,url,kwargs))
        if self.block is not None: return self.response(self.block, headers={'Retry-After':'60'} if self.block==429 else {})
        if url==API+'/generateIds':
            self.generated+=1;return self.response(data={'ids':[f'created_{self.generated}']})
        if url==UPLOAD and method=='POST':
            message=BytesParser(policy=policy.default).parsebytes(('Content-Type: '+kwargs['headers']['Content-Type']+'\r\nMIME-Version: 1.0\r\n\r\n').encode()+kwargs['data'])
            metadata_part, raw_part=list(message.iter_parts())
            meta=json.loads(metadata_part.get_payload(decode=True));raw=raw_part.get_payload(decode=True)
            fid=meta['id']
            if fid in self.files:return self.response(409)
            self.created+=1;self.put(fid,raw,meta['mimeType'],meta['name'])
            if 'appProperties' in meta:self.files[fid]['appProperties']=meta['appProperties']
            if self.lost:
                self.lost=False;raise TimeoutError('simulated lost response')
            return self.response(200,data=self.files[fid])
        if url==API:
            if self.list_pages is not None:
                index=self.page_index;self.page_index+=1;return self.response(data=self.list_pages[min(index,len(self.list_pages)-1)])
            return self.response(data={'files':[m for m in self.files.values() if m.get('parents')==['folder']]})
        file_id=url.removeprefix(API+'/').split('/')[0]
        if file_id not in self.files:return self.response(404)
        if kwargs.get('params',{}).get('alt')=='media' or url.endswith('/export'):
            raw=self.raw[file_id]
            if self.corrupt:raw=raw+b'wrong'
            return self.response(raw=raw)
        return self.response(data=self.files[file_id])


class EventTests(unittest.TestCase):
    def test_identity_is_repeatable(self):
        a=event();self.assertEqual(a,event());self.assertEqual(parse_event(json_bytes(a)),a)
    def test_bom_and_crlf(self):
        raw=b'\xef\xbb\xbf'+json.dumps(event(),indent=2).replace('\n','\r\n').encode()
        self.assertEqual(parse_event(raw),event())
    def test_duplicate_keys_rejected(self):
        with self.assertRaisesRegex(CampaignError,'DUPLICATE_JSON_KEY'):parse_event(b'{"a":1,"a":2}')
    def test_unknown_schema_not_empty_success(self):
        with self.assertRaisesRegex(CampaignError,'SCHEMA'):parse_event(b'{}')
    def test_campaign_mismatch(self):
        with self.assertRaisesRegex(CampaignError,'CAMPAIGN_ID_MISMATCH'):parse_event(json_bytes(event()),'OTHER')
    def test_role_cannot_self_review(self):
        with self.assertRaisesRegex(CampaignError,'ROLE_KIND'):event(kind='REVIEW')
    def test_scope_defaults_excluded(self):
        self.assertEqual(make_event(campaign_id='C',entity_id='E',kind='METHOD',role='CIENTISTA',actor_id='A',data={})['atlas_scope'],'EXCLUDED')
    def test_nonfinite_and_unsafe_integers(self):
        for value in [float('nan'),float('inf'),2**54]:
            with self.subTest(value=value),self.assertRaises(CampaignError):event(data={'value':value})
    def test_non_json_keys(self):
        with self.assertRaises(CampaignError):event(data={'__proto__':{}})
    def test_changed_identity_rejected(self):
        e=event();e['version']=2
        with self.assertRaisesRegex(CampaignError,'IDENTITY'):validate_event(e)
    def test_paths_not_ids(self):
        with self.assertRaises(CampaignError):event(campaign_id='../private')
    def test_timestamp_not_naive(self):
        with self.assertRaises(CampaignError):event(timestamp_utc='2026-10-15')


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.directory=Path(self.temp.name)
        self.drive=FakeDrive();self.store=DriveCampaignStore('root',session=self.drive,write=True,sleep=lambda _:None)
    def tearDown(self):self.temp.cleanup()
    def publish(self,e=None):return self.store.publish_event(e or event(),'folder',self.directory)
    def test_round_trip(self):
        receipt=self.publish();self.assertEqual(receipt['state'],'PERSISTED_VERIFIED')
        self.assertEqual(self.store.read_event(receipt['file_id'],'folder','CAMP-SYNTHETIC')['event'],event())
        self.assertTrue(all(r.closed for r in self.drive.responses))
    def test_retry_reuses_id(self):
        first=self.publish();second=self.publish()
        self.assertEqual(first,second);self.assertEqual(self.drive.created,1);self.assertEqual(self.drive.generated,1)
    def test_lost_write_response(self):
        self.drive.lost=True;receipt=self.publish()
        self.assertEqual(self.drive.created,1);self.assertEqual(receipt['file_id'],'created_1')
        self.assertEqual(self.drive.generated,1)
    def test_same_identity_changed_bytes_conflicts(self):
        self.publish()
        with self.assertRaisesRegex(CampaignError,'INTENT_CONFLICT'):self.publish(event(data={'threshold':0.99}))
        self.assertEqual(self.drive.created,1)
    def test_changed_timestamp_requires_same_saved_event(self):
        self.publish()
        with self.assertRaisesRegex(CampaignError,'INTENT_CONFLICT'):self.publish(event(timestamp_utc='2026-10-15T03:00:00Z'))
    def test_auth_failure_does_not_retry(self):
        for code in [401,403]:
            self.drive.block=code;self.drive.calls.clear()
            with self.subTest(code=code),self.assertRaisesRegex(CampaignError,f'AUTH_{code}'):self.publish()
            self.assertEqual(len(self.drive.calls),1)
    def test_read_only_denies_write(self):
        self.store.write=False
        with self.assertRaisesRegex(CampaignError,'WRITE_NOT_ENABLED'):self.publish()
        self.assertEqual(self.drive.calls,[])
    def test_missing_and_mismatched_folder(self):
        self.drive.files['folder']['name']='different'
        with self.assertRaisesRegex(CampaignError,'FOLDER_MISMATCH'):self.publish()
        self.assertEqual(self.drive.created,0)
    def test_corrupt_readback(self):
        self.drive.corrupt=True
        with self.assertRaisesRegex(CampaignError,'BYTES_MISMATCH'):self.publish()
        self.assertEqual(self.drive.created,1)
    def test_pagination_complete(self):
        self.drive.list_pages=[{'files':[],'nextPageToken':'p2'},{'files':[{'id':'f'}]}]
        self.assertEqual(self.store.list_files('folder','CAMP-SYNTHETIC'),[{'id':'f'}])
    def test_repeated_page_token(self):
        self.drive.list_pages=[{'files':[],'nextPageToken':'p2'}]
        with self.assertRaisesRegex(CampaignError,'PAGE_LOOP'):self.store.list_files('folder','CAMP-SYNTHETIC')
    def test_incomplete_listing(self):
        self.drive.list_pages=[{'files':[],'incompleteSearch':True}]
        with self.assertRaisesRegex(CampaignError,'INCOMPLETE'):self.store.list_files('folder','CAMP-SYNTHETIC')
    def test_native_doc_preserves_type(self):
        self.drive.put('doc',b'\xef\xbb\xbf'+json_bytes(event()),DOC)
        actual=self.store.read_event('doc','folder','CAMP-SYNTHETIC')
        self.assertEqual(actual['mime_type'],DOC);self.assertEqual(actual['event'],event())
    def test_read_wrong_parent(self):
        self.drive.put('outside',json_bytes(event()));self.drive.files['outside']['parents']=['other']
        with self.assertRaisesRegex(CampaignError,'PARENT_MISMATCH'):self.store.read_event('outside','folder','CAMP-SYNTHETIC')
    def test_long_retry_after_is_deferred(self):
        self.drive.block=429
        with self.assertRaisesRegex(CampaignError,'DEFERRED'):self.publish()
        self.assertEqual(len(self.drive.calls),1)
    def test_lock_is_not_stealable(self):
        p=self.directory/'mutex'
        with local_lock(p):
            with self.assertRaisesRegex(CampaignError,'ALREADY_RUNNING'):
                with local_lock(p):pass
        with local_lock(p):pass
    def test_lock_releases_on_exception(self):
        p=self.directory/'mutex'
        with self.assertRaises(RuntimeError):
            with local_lock(p):raise RuntimeError('fixture')
        with local_lock(p):pass
    def test_journal_precedes_remote_write(self):
        original=self.drive.request
        def request(method,url,**kwargs):
            if url==UPLOAD:
                records=list(self.directory.glob('*.json'));self.assertEqual(len(records),1)
                self.assertEqual(json.loads(records[0].read_bytes())['file_id'],'created_1')
            return original(method,url,**kwargs)
        self.drive.request=request;self.publish()


class PackageBoundaryTests(unittest.TestCase):
    def test_client_does_not_import_tower_package(self):
        import subprocess,sys
        code = "import sys; from runtime.nexo_execution.campaign_store import DriveCampaignStore; assert 'runtime.nexo_agent_api' not in sys.modules"
        subprocess.run([sys.executable, "-c", code], check=True, timeout=10)

    def test_session_must_be_explicitly_supplied(self):
        with self.assertRaisesRegex(CampaignError, "AUTHORIZED_SESSION_REQUIRED"):
            DriveCampaignStore("root", session=None)


if __name__=='__main__':unittest.main()
