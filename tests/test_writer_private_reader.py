"""Offline tests: least-privilege Writer reads only the explicitly shared Doc.

Fakes do not establish provider ACL capability; real Writer principal needs
its own authenticated readback before production is declared fixed.
"""
import copy
import unittest
from runtime.nexo_agent_api import doc_persistence as dp
from runtime.nexo_agent_api.drive_transport import DriveInbox

ARTIFACT = 'ARTIFACT-AUDIT-001'
CAMPAIGN = 'CAMP-DDE-ANOMALIES-MEGA-20260922'
FOLDER = 'campaignFolder123'
FILE = 'docFile456'

class Response:
    def __init__(self, obj=None, *, status=200, content=None):
        self.status_code = status
        self.obj = obj or {}
        self.content = content
        self.text = 'denied' if status != 200 else ''
    def json(self): return copy.deepcopy(self.obj)

class Session:
    def __init__(self):
        self.package = dp.pack(artifact_id=ARTIFACT,campaign_id=CAMPAIGN,
            created_at='2026-10-16T08:00:00Z',producer_role='CIENTISTA',
            provenance={'origin':'audit'},
            files=[{'name':'out.txt','mime_type':'text/plain','content':b'real bytes\n'}])
        self.meta = {'id':FILE,'name':'nexo-doc-v1-'+ARTIFACT,
                     'mimeType':dp.DOC_MIME,'parents':[FOLDER],'trashed':False}
        self.acl = {'permissions':[{'id':'u1','type':'user','role':'owner'},{'id':'u2','type':'user','role':'reader'}]}
        self.calls = []
        self.forbid = None
        self.move_after = False
    def get(self, url, *, params, timeout):
        self.calls.append((url, params))
        # No parent folder request is ever necessary under a direct document share.
        if url.endswith('/'+FOLDER) or url.endswith('/root') or url.endswith('/1Rxu3GJ1hHlvVBbAkBRp4e_5F7fTIOsNE'):
            raise AssertionError('must not access unshared parent')
        if url.endswith('/permissions'):
            return Response(self.acl, status=403 if self.forbid=='permissions' else 200)
        if url.endswith('/export'):
            return Response(content=b'\xef\xbb\xbf'+dp.canonical(self.package)+b'\n')
        if url.endswith('/'+FILE):
            if self.forbid=='doc': return Response(status=403)
            meta=copy.deepcopy(self.meta)
            if self.move_after and len([x for x, _ in self.calls if x.endswith('/'+FILE)])>1:
                meta['parents']=['differentFolder']
            return Response(meta)
        raise AssertionError(url)

class LeastPrivilegeReadTest(unittest.TestCase):
    def setUp(self):
        self.session = Session()
        self.reader = DriveInbox(session=self.session)
        self.ref = {'file_id': FILE,'folder_id':FOLDER,'campaign_id':CAMPAIGN,
                    'artifact_id':ARTIFACT,'package_sha256':dp.digest(dp.canonical(self.session.package))}
    def read(self): return self.reader.read_artifact_package(self.ref)
    def test_reader_can_read_only_doc_not_ancestors(self):
        self.assertEqual(self.read(),self.session.package)
        self.assertEqual(len(self.session.calls),5)
    def test_direct_document_permission_denial_blocks(self):
        self.session.forbid='doc'
        with self.assertRaisesRegex(dp.PackageUnavailable,'ARTIFACT_READ_ACCESS_REQUIRED'):
            self.read()
    def test_acl_permission_denial_does_not_bypass(self):
        self.session.forbid='permissions'
        with self.assertRaisesRegex(dp.PackageUnavailable,'ARTIFACT_PRIVACY_UNVERIFIED'):
            self.read()
    def test_public_link_forbidden(self):
        self.session.acl['permissions'].append({'id':'public','type':'anyone','role':'reader'})
        with self.assertRaisesRegex(dp.PackageError,'ARTIFACT_PRIVATE_IDENTITY_UNVERIFIED'):
            self.read()
    def test_group_access_forbidden(self):
        self.session.acl['permissions'].append({'id':'group1','type':'group','role':'reader'})
        with self.assertRaisesRegex(dp.PackageError,'ARTIFACT_PRIVATE_IDENTITY_UNVERIFIED'):
            self.read()
    def test_doc_wrong_parent_forbidden(self):
        self.session.meta['parents']=['somewhereElse']
        with self.assertRaisesRegex(dp.PackageError,'ARTIFACT_CAMPAIGN_PARENT_MISMATCH'):
            self.read()
    def test_doc_wrong_name_forbidden(self):
        self.session.meta['name']='unrelated'
        with self.assertRaisesRegex(dp.PackageError,'ARTIFACT_CAMPAIGN_PARENT_MISMATCH'):
            self.read()
    def test_doc_changed_mid_read_forbidden(self):
        self.session.move_after=True
        with self.assertRaisesRegex(dp.PackageError,'ARTIFACT_CAMPAIGN_PARENT_MISMATCH'):
            self.read()
    def test_content_identity_mismatch_forbidden(self):
        self.session.package['campaign_id']='ANOTHER-CAMPAIGN'
        with self.assertRaisesRegex(dp.PackageError,'ARTIFACT_REFERENCE_IDENTITY_MISMATCH'):
            self.read()
    def test_digest_reference_mismatch_forbidden(self):
        self.ref["package_sha256"] = "sha256:" + "0" * 64
        with self.assertRaisesRegex(dp.PackageError,'ARTIFACT_REFERENCE_IDENTITY_MISMATCH'):
            self.read()
    def test_acl_role_swap_midread_detected(self):
        class Mutable(Session):
            def get(self, url, *, params, timeout):
                if url.endswith('/permissions') and len([x for x, _ in self.calls if x.endswith('/permissions')]) > 0:
                    self.acl = {'permissions':[{'id':'u1','type':'user','role':'owner'},
                                               {'id':'u3','type':'user','role':'reader'}]}
                return super().get(url,params=params,timeout=timeout)
        self.session=Mutable();self.reader=DriveInbox(session=self.session)
        with self.assertRaisesRegex(dp.PackageUnavailable,'ARTIFACT_METADATA_CHANGED'):
            self.read()
    def test_empty_acl_not_treated_private(self):
        self.session.acl['permissions']=[]
        with self.assertRaisesRegex(dp.PackageUnavailable,'ARTIFACT_PRIVACY_UNVERIFIED'):
            self.read()
    def test_acl_pagination_and_readback(self):
        class Pages(Session):
            def get(self,url, *, params, timeout):
                if url.endswith('/permissions'):
                    self.calls.append((url,params))
                    if 'pageToken' not in params:
                        return Response({'permissions':[{'id':'u1','type':'user','role':'owner'}], 'nextPageToken':'next'})
                    return Response({'permissions':[{'id':'u2','type':'user','role':'reader'}]})
                return super().get(url,params=params,timeout=timeout)
        self.session=Pages()
        self.reader=DriveInbox(session=self.session)
        self.assertEqual(self.read()['artifact_id'],ARTIFACT)

if __name__ == '__main__': unittest.main()
