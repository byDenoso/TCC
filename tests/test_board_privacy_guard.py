from __future__ import annotations
import base64
import io
import json
import re
import tempfile
import unittest
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from runtime.nexo_agent_api import evolution
from runtime.nexo_agent_api.inbox_apply import proposal_to_requests
from runtime.nexo_agent_api.public_projection import _load_evolution
from runtime.nexo_agent_api.tower_apply import apply_requests

AT = datetime(2026, 10, 8, 18, 36, tzinfo=timezone.utc)

def fixture_root(base):
    root = base / 'TOWER'
    (root/'roadmaps').mkdir(parents=True)
    (root/'indexes').mkdir()
    (root/'indexes/active-roadmaps.json').write_text(json.dumps({'items':[]}))
    (root/'CONTROL.json').write_text('{}')
    return root

def post(root, label='private PEER diagnostic', private_flag=None):
    body={'to':'GUARDIAO','text':label,'refs':['WORK::PEER-DETECTION-D04']}
    if private_flag is not None:
        body['private']=private_flag
    item={'kind':'BOARD_POST','source':'ENGINEER',
          'created_at':'2026-10-08T18:35:00Z','payload':body}
    receipts=apply_requests(root,proposal_to_requests(item,root))
    assert all(r.get('accepted',True) is not False for r in receipts)
    return item

class BoardPrivacyGuardTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=fixture_root(Path(self.temp.name))

    def board_doc(self):
        return self.root/evolution.BOARD_DOC

    def test_explicit_false_is_stored_private(self):
        post(self.root,private_flag=False)
        data=json.loads(self.board_doc().read_text())
        self.assertIs(data['posts'][0]['private'],True)
        self.assertEqual(evolution.evolution_status(self.root,now=AT,public=True)['board'],[])
        self.assertEqual(len(evolution.evolution_status(self.root,now=AT)['board']),1)

    def test_omitted_flag_is_stored_private(self):
        post(self.root)
        data=json.loads(self.board_doc().read_text())
        self.assertIs(data['posts'][0]['private'],True)

    def test_legacy_false_cannot_be_published(self):
        post(self.root,private_flag=False)
        doc=self.board_doc()
        data=json.loads(doc.read_text())
        data['posts'][0]['private']=False # prior Writer bug in canonical state
        doc.write_text(json.dumps(data),encoding='utf-8')
        self.assertEqual(evolution.evolution_status(self.root,now=AT,public=True)['board'],[])
        self.assertEqual(len(evolution.evolution_status(self.root,now=AT)['board']),1)

    def test_legacy_missing_flag_cannot_be_published(self):
        post(self.root)
        doc=self.board_doc()
        data=json.loads(doc.read_text())
        data['posts'][0].pop('private')
        doc.write_text(json.dumps(data),encoding='utf-8')
        self.assertEqual(evolution.evolution_status(self.root,now=AT,public=True)['board'],[])

    def test_public_guard_even_without_board_document(self):
        self.assertEqual(evolution.evolution_status(self.root,now=AT,public=True)['board'],[])

    def test_private_view_still_expires(self):
        post(self.root)
        self.assertEqual(len(evolution.evolution_status(self.root,now=AT)['board']),1)
        late=datetime(2026,10,12,18,36,tzinfo=timezone.utc)
        self.assertEqual(evolution.evolution_status(self.root,now=late)['board'],[])

    def test_resolution_still_hides_private_board(self):
        post(self.root)
        doc=self.board_doc()
        post_id=json.loads(doc.read_text())['posts'][0]['id']
        resolve={'kind':'BOARD_POST','source':'ENGINEER',
                 'created_at':'2026-10-08T18:35:30Z','payload':{'resolve':[post_id]}}
        result=apply_requests(self.root,proposal_to_requests(resolve,self.root))
        self.assertTrue(all(r.get('accepted',True) is not False for r in result))
        self.assertEqual(evolution.evolution_status(self.root,now=AT)['board'],[])

    def test_repeat_is_idempotent(self):
        p=post(self.root)
        again=proposal_to_requests(p,self.root)
        if again:
            apply_requests(self.root,again)
        self.assertEqual(len(json.loads(self.board_doc().read_text())['posts']),1)

    def test_projection_defense_if_evolution_regresses(self):
        fake={'charters':[{'id':'dummy'}], 'genome':{'genes':[]},'thoughts':[],
              'signal_clusters':[], 'incidents':[],
              'board':[{'id':'legacy','text':'Private PEER evidence', 'private':False}]}
        with patch.object(evolution,'evolution_status',return_value=fake) as mocked:
            projected=_load_evolution(self.root,'2026-10-08T18:36:00Z')
        self.assertIsNotNone(projected)
        self.assertEqual(projected['board'],[])
        self.assertEqual(mocked.call_args.kwargs['public'],True)

    def test_generated_writer_matches_updated_source(self):
        bundle=Path(__file__).resolve().parents[1]/'gpt/nexo_gpt_writer.py'
        data=bundle.read_text(encoding='utf-8')
        encoded=re.search(r'^_BUNDLE = "([A-Za-z0-9+/=]+)"$',data,re.M).group(1)
        with zipfile.ZipFile(io.BytesIO(base64.b64decode(encoded))) as z:
            for path in ('runtime/nexo_agent_api/evolution.py',
                         'runtime/nexo_agent_api/public_projection.py'):
                self.assertEqual(z.read(path),(bundle.parent.parent/path).read_bytes())

if __name__=='__main__':
    unittest.main()