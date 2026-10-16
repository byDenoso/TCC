"""Local regressions: compatibility and evaluator reuse, no remote operations."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from runtime.nexo_agent_api import control_compat as c, execution_recovery as r, scientific_integrity as s
from runtime.nexo_agent_api.live_tower import build_live_tower_payload, materialize_live_tower
from tests.test_scientific_integrity import fixture, save

class RuntimeReviewRepairs(unittest.TestCase):
    def test_migrated_direct_route_preserves_policy_without_removing_provenance(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'original'
            save(root,'CONTROL.json',{'truth_owner':'TOWER_V06@GOOGLE_DRIVE_PRIVATE',
                 'execution_routing':'LEAN_NO_CONTRACT_DIRECT_RUNTIME',
                 'scientific_runtime':'CHATGPT_RUNTIME','lean_execution_policy':{'no_extra_gates':True}})
            raw=json.dumps(build_live_tower_payload(root)).encode()
            migrated,_=c.prepare_migration(raw)
            target,_=materialize_live_tower(migrated,Path(tmp)/'migrated')
            self.assertEqual(c.read_control_compat(target)['lean_execution_policy'],{'no_extra_gates':True})
            self.assertTrue(s._direct_scientific_route(target,{}))
            self.assertFalse(s._direct_scientific_route(target,{'execution':'GITHUB_ACTIONS_BATTERY'}))
            test=fixture();test.pop('recipe');test.pop('recipe_params');test.pop('data_binding')
            self.assertIn('INPUT_PROVENANCE_INCOMPLETE',s.readiness(target,test)['reasons'])

    def test_evaluator_created_once_per_reconciliation(self):
        for factory_outcome in ('callable','none','exception'):
            with self.subTest(factory_outcome=factory_outcome), tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp)
                save(root,'CONTROL.json',{'mode':'ACTIVE'})
                for ident in ('T-1','T-2'):
                    save(root,'entities/test/'+ident+'.json',fixture(ident))
                evaluator=lambda root,test,baseline: baseline()
                kwargs={'side_effect':ValueError('unavailable')} if factory_outcome=='exception' else {'return_value':evaluator if factory_outcome=='callable' else None}
                with patch('runtime.nexo_agent_api.operational_canary.make_tower_readiness_evaluator',**kwargs) as factory:
                    r.reconcile_requests(root)
                    self.assertEqual(factory.call_count,1)

    def test_injected_evaluator_does_not_construct_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);save(root,'CONTROL.json',{'mode':'ACTIVE'})
            save(root,'entities/test/T.json',fixture('T'))
            with patch('runtime.nexo_agent_api.operational_canary.make_tower_readiness_evaluator') as factory:
                r.reconcile_requests(root,readiness_evaluator=lambda root,test,baseline:baseline())
                factory.assert_not_called()

    def test_baseline_failure_is_not_retried_when_factory_unavailable(self):
        with patch('runtime.nexo_agent_api.operational_canary.make_tower_readiness_evaluator',return_value=None), patch.object(s,'readiness',side_effect=[ValueError('bad input'),{'eligible':True}]) as baseline:
            with self.assertRaises(ValueError):
                r.evaluate_readiness(Path('/unused'),{})
            self.assertEqual(baseline.call_count,1)

    def test_missing_or_invalid_control_cannot_enable_direct_route(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            self.assertFalse(s._direct_scientific_route(root,{}))
            save(root,'CONTROL.json',{'execution_routing':'LEAN_NO_CONTRACT_DIRECT_RUNTIME','scientific_runtime':'CHATGPT_RUNTIME'})
            save(root,c.POLICY_PATH,{})
            with self.assertRaises(c.ControlCompatibilityError):
                s._direct_scientific_route(root,{})
            (root/c.POLICY_PATH).unlink()
            (root/'CONTROL.json').write_text('invalid json')
            with self.assertRaises(c.ControlCompatibilityError):
                s._direct_scientific_route(root,{})
