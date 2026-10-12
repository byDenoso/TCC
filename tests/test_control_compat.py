import copy
import json
import tempfile
import unittest
from pathlib import Path

from runtime.nexo_agent_api import autonomy
from runtime.nexo_agent_api.control_compat import (
    AUTHORITY_PATH,POLICY_PATH,ControlCompatibilityError,control_from_bundle,
    prepare_migration,read_control_compat,inventory_consumers)
from runtime.nexo_agent_api.live_tower import build_live_tower_payload,materialize_live_tower,verify_live_tower
from runtime.nexo_agent_api.memory import Snapshot,SourceError
from runtime.nexo_agent_api.service import AgentService
from runtime.nexo_agent_api.tower_apply import apply_document


def raw_tower():
    with tempfile.TemporaryDirectory() as work:
        root=Path(work)
        control={'truth_owner':'TOWER_V06@GOOGLE_DRIVE_PRIVATE','mode':'ACTIVE',
                 'write_model':'IN_PLACE_FILE_REVISION_CAS_READBACK','github_actions_science_role':'DISABLED_BUDGET_EXHAUSTED',
                 'autonomy_mandate':{'schema':autonomy.SCHEMA,'id':'MID-A','revision':1,'status':'ACTIVE',
                                    'domain':'OBSERVATIONAL_COSMOLOGY','public_data_only':True,'no_additional_cost':True,
                                    'runner':'GITHUB_ACTIONS_STANDARD_PUBLIC'},'revoked_autonomy_mandates':['MID-OLD'],
                 'historical_migration_note':'preserve this exact data'}
        (root/'CONTROL.json').write_text(json.dumps(control))
        bundle=build_live_tower_payload(root,updated_at='2026-10-12T00:00:00Z')
        bundle['files']['entities/test/T.json']={'encoding':'json','value':{'id':'T','result':[1,2,3],'contract':{'alpha':0.01}}}
        data=json.dumps(bundle['files'],sort_keys=True,separators=(',',':')).encode()
        import hashlib
        revision='sha256:'+hashlib.sha256(data).hexdigest()
        bundle.update(file_count=len(bundle['files']),revision=revision,state_fingerprint=revision)
        return json.dumps(bundle,sort_keys=True).encode()


class ControlCompatTests(unittest.TestCase):
    def test_rehearsal_preserves_science_full_history_and_mandate_semantics(self):
        raw=raw_tower();old=json.loads(raw)
        result,report=prepare_migration(raw)
        actual=json.loads(result)
        self.assertEqual(report['status'],'REHEARSAL_NOT_ACTIVE')
        self.assertNotIn('CONTROL.json',actual['files'])
        self.assertEqual(actual['files'][report['retained_history']],old['files']['CONTROL.json'])
        self.assertEqual(actual['files']['entities/test/T.json'],old['files']['entities/test/T.json'])
        with tempfile.TemporaryDirectory() as work:
            root,_=materialize_live_tower(result,work)
            self.assertTrue(autonomy.active(root))
            self.assertEqual(read_control_compat(root)['revoked_autonomy_mandates'],['MID-OLD'])
            self.assertEqual(read_control_compat(root)['github_actions_science_role'],'DISABLED_BUDGET_EXHAUSTED')
            repacked=build_live_tower_payload(root,base=actual)
            self.assertNotIn('CONTROL.json',repacked['files'])
            self.assertNotIn('LIVE_TOWER_HEADER_LOCAL.json',repacked['files'])
            self.assertEqual(verify_live_tower(repacked),actual['revision'])

    def test_generic_requests_cannot_edit_authority_and_revocation_uses_new_target(self):
        result,_=prepare_migration(raw_tower())
        with tempfile.TemporaryDirectory() as work:
            root,_=materialize_live_tower(result,work)
            forged={'document':AUTHORITY_PATH,'merge':{'autonomy_mandate':{'status':'REVOKED'}}}
            self.assertFalse(apply_document(root,forged)['accepted'])
            item={'kind':'OPERATOR_INTENT','source':'DENER','created_at':'2026-10-12T00:01:00Z',
                  '_autonomy_human_authority':autonomy.HUMAN_AUTHORITY,'payload':{}}
            body={'action':'REVOKE_AUTONOMY_MANDATE','mandate_id':'MID-A','expected_revision':1,'approval_ref':'authenticated-human'}
            requests=autonomy.operator_requests(item,body,root)
            self.assertEqual(requests[0]['document'],AUTHORITY_PATH)
            self.assertTrue(apply_document(root,requests[0])['accepted'])
            self.assertFalse(autonomy.active(root))
            self.assertIn('MID-A',read_control_compat(root)['revoked_autonomy_mandates'])
            stale={**requests[0],'document':'CONTROL.json'}
            self.assertFalse(apply_document(root,stale)['accepted'])

    def test_missing_component_dual_authority_or_bad_identity_fails_closed(self):
        result,_=prepare_migration(raw_tower());bundle=json.loads(result)
        with tempfile.TemporaryDirectory() as work:
            root,_=materialize_live_tower(result,work)
            (root/AUTHORITY_PATH).unlink()
            with self.assertRaises(ControlCompatibilityError):read_control_compat(root)
        dual=copy.deepcopy(bundle);dual['files']['CONTROL.json']=json.loads(raw_tower())['files']['CONTROL.json']
        with self.assertRaises(ControlCompatibilityError):control_from_bundle(dual)
        bad=copy.deepcopy(bundle);bad['stable_file_id']='different-source'
        with self.assertRaises(ControlCompatibilityError):control_from_bundle(bad)

    def test_source_reader_accepts_migrated_snapshot_and_rejects_incomplete_authority(self):
        result,_=prepare_migration(raw_tower())
        with tempfile.TemporaryDirectory() as work:
            path=Path(work)/'snapshot.json';path.write_bytes(result)
            snapshot=Snapshot.read(path)
            self.assertEqual(snapshot.revision,json.loads(result)['revision'])

    def test_static_inventory_never_calls_absent_keys_unused(self):
        with tempfile.TemporaryDirectory() as work:
            root=Path(work);(root/'consumer.py').write_text("value=control.get('mode')\n")
            result=inventory_consumers(raw_tower(),[root])
            keys={row['key']:row for row in result['keys']}
            self.assertTrue(keys['mode']['static_hints'])
            self.assertFalse(keys['historical_migration_note']['retirement_authorized'])
            self.assertFalse(result['complete_consumer_coverage'])


    def test_reused_materialization_retires_only_known_unedited_control(self):
        raw=raw_tower();result,_=prepare_migration(raw)
        with tempfile.TemporaryDirectory() as work:
            root,_=materialize_live_tower(raw,work)
            materialize_live_tower(result,root)
            self.assertFalse((root/'CONTROL.json').exists())
            self.assertEqual(read_control_compat(root)['mode'],'ACTIVE')
        with tempfile.TemporaryDirectory() as work:
            root,_=materialize_live_tower(raw,work)
            (root/'CONTROL.json').write_text('local unpublished edit')
            with self.assertRaisesRegex(ValueError,'LOCAL_CHANGES_PRESENT'):
                materialize_live_tower(result,root)
            self.assertEqual((root/'CONTROL.json').read_text(),'local unpublished edit')

    def test_malformed_migration_leaves_reused_materialization_byte_identical(self):
        raw = raw_tower(); migrated, _ = prepare_migration(raw_tower())
        bundle = json.loads(migrated); bundle['files'].pop(POLICY_PATH)
        import hashlib
        revision = 'sha256:' + hashlib.sha256(json.dumps(bundle['files'],ensure_ascii=False,
            sort_keys=True,separators=(',', ':')).encode()).hexdigest()
        bundle.update(revision=revision,state_fingerprint=revision,file_count=len(bundle['files']))
        invalid = json.dumps(bundle).encode()
        with tempfile.TemporaryDirectory() as work:
            root, _ = materialize_live_tower(raw, work)
            before = {str(p.relative_to(root)):p.read_bytes() for p in root.rglob('*') if p.is_file()}
            with self.assertRaises(ControlCompatibilityError): materialize_live_tower(invalid, root)
            after = {str(p.relative_to(root)):p.read_bytes() for p in root.rglob('*') if p.is_file()}
            self.assertEqual(before, after)
