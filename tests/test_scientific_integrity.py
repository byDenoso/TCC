"""Offline adversarial tests. Fixtures never modify Drive or scientific production data."""
import copy
import hashlib
import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from runtime.nexo_agent_api import evolution as e, scientific_integrity as s
from runtime.nexo_agent_api.gpt_writer import apply_to_tower, _fully_handled
from runtime.nexo_agent_api.inbox_apply import ProposalError, _result_request
from runtime.nexo_agent_api.live_tower import build_live_tower_payload, read_live_tower_bytes
from runtime.nexo_agent_api.tower_apply import apply_requests
from runtime.nexo_agent_api.tower_paths import entity_path, fs_path

NOW, END = '2026-09-30T10:00:00Z', '2026-09-30T10:01:00Z'


def save(root, relative, value):
    file = fs_path(root, relative)
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text(json.dumps(value), encoding='utf-8')


def fixture(test_id='TEST-A'):
    test = {'id':test_id, 'entity_version':1, 'kind':'TEST', 'domain':'SCIENCE', 'status':'READY', 'state':'READY',
            'question':'Is the generated mean bounded?', 'null':'Unbounded mean', 'rival':'Bounded mean',
            'method':'Seeded sample mean', 'dataset_and_selection':'Frozen generated sample',
            'success_criteria':'abs(mean)<1', 'kill_criteria':'abs(mean)>=1', 'roadmap_id':'RM-A',
            'frozen_at':NOW, 'recipe':'audit_recipe', 'recipe_params':{'seed':17},
            'data_binding':{'status':'BOUND','inputs':[{'name':'sample','kind':'generated', 'generator':'v1',
                'seed':17, 'sha256':'a'*64}]}}
    test['prereg_hash'] = e.prereg_hash(test_id, test)
    return test


def install_fixture_catalog(directory, monkeypatch, *names):
    """Local inert recipes used to exercise admission, never scientific data."""
    directory.mkdir(parents=True, exist_ok=True)
    for name in names:
        save(directory, 'smoke/' + name + '.json', {'fixture': True})
        (directory / (name + '.py')).write_text('# isolated admission fixture\nresult = 1\n')
    monkeypatch.setenv('NEXO_RECIPE_ROOT', str(directory))


def store_fixture_test(root, test_id, recipe='audit_recipe', params=None, **changes):
    test = fixture(test_id)
    test.update(recipe=recipe, recipe_params=params or {'seed': 17}, question='Fixture ' + test_id)
    test.update(changes)
    test['prereg_hash'] = e.prereg_hash(test_id, test)
    save(root, entity_path(root, 'test', test_id).relative_to(root).as_posix(), test)
    return test


def structured_fixture(test_id='TEST-STRUCTURED'):
    """A small declared contract with legacy readiness names omitted."""
    test = fixture(test_id)
    for key in ('question', 'null', 'rival', 'method', 'dataset_and_selection',
                'prereg_hash', 'prereg_ref', 'frozen_at'):
        test.pop(key, None)
    test.update({
        'scientific_question': 'Does the declared mechanism change the synthetic observable?',
        'mechanism': 'SYNTHETIC_MEAN_SHIFT',
        'contract_lock': True,
        'capability_resolution': {'scientific_definition_frozen_now': True},
        'null_contract': {'primary': 'The unchanged synthetic sample.'},
        'decision_contract': {'SHIFT': 'p < 0.05 and the declared effect has the expected sign.'},
        'input_contract': {
            'clustering_de_extension': {'framework': 'declared synthetic extension'},
            'observational_sampling': 'Use the complete synthetic sample.',
            'environment_template': 'Use the declared synthetic input.',
        },
        'estimator_contract': {'procedure': 'Apply the same estimator to both cases.'},
        'environment_operator_contract': {
            'observational_recovery': {
                'dataset': 'synthetic sample v1',
                'selection': 'include every generated row',
            },
            'primary_environment': {
                'product': 'synthetic field v1',
                'source': 'fixture generator v1',
            },
        },
    })
    return test


class ScientificIntegrityTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name) / 'tower'
        self.root.mkdir()
        self.recipes = Path(self.temporary.name) / 'recipes'
        save(self.recipes, 'smoke/audit_recipe.json', {'seed':17})
        (self.recipes / 'audit_recipe.py').write_text('result = 1\n')
        self.env = patch.dict(os.environ, {'NEXO_RECIPE_ROOT':str(self.recipes)})
        self.env.start()
        save(self.root, 'CONTROL.json', {'mode':'ACTIVE','truth_owner':'TOWER_V06@GOOGLE_DRIVE_PRIVATE'})
        self.test = fixture()
        self.put(self.test)

    def tearDown(self):
        self.env.stop()
        self.temporary.cleanup()

    def put(self, test):
        path = entity_path(self.root, 'test', test['id'])
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(test))

    def spec(self, bid='bat-audit-one'):
        return {'battery_id':bid,'tests':[{'test_id':self.test['id'],'recipe':'audit_recipe','params':{'seed':17}}]}

    def reserve(self):
        with redirect_stderr(io.StringIO()):
            receipts = apply_requests(self.root, e.battery_requests({'created_at':NOW}, self.spec(), self.root))
        self.assertTrue(all(r['accepted'] for r in receipts), receipts)
        return s.batteries(self.root)[0]

    def apply(self, items):
        raw = json.dumps(build_live_tower_payload(self.root)).encode()
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            result, report = apply_to_tower(raw, items)
        return read_live_tower_bytes(result or raw), report

    def test_valid_ready(self):
        self.assertTrue(s.readiness(self.root, self.test)['eligible'])

    def test_legacy_prereg_reference_is_not_fabricated_timestamp(self):
        self.test.pop('frozen_at'); self.test['prereg_ref'] = 'existing-immutable-preregistration'
        self.assertTrue(s.readiness(self.root, self.test)['eligible'])
        self.assertNotIn('frozen_at', self.test)

    def test_missing_recipe_and_data_are_not_ready(self):
        self.test['recipe'] = 'not_an_installed_recipe'; self.test.pop('data_binding')
        reasons = s.readiness(self.root, self.test)['reasons']
        self.assertIn('RECIPE_OR_SMOKE_MISSING', reasons)
        self.assertIn('INPUT_PROVENANCE_INCOMPLETE', reasons)

    def test_changed_frozen_design_is_detected(self):
        self.test['method'] = 'different'
        self.assertIn('FROZEN_DESIGN_CHANGED', s.readiness(self.root, self.test)['reasons'])

    def test_structured_readiness_normalizes_without_mutating_scientific_contract(self):
        structured = structured_fixture()
        before = copy.deepcopy(structured)

        result = s.readiness(self.root, structured)

        self.assertFalse(any(reason.startswith('MISSING_') for reason in result['reasons']), result)
        self.assertEqual(structured, before)

    def test_structured_readiness_still_blocks_when_rival_definition_is_missing(self):
        structured = structured_fixture()
        structured['input_contract'].pop('clustering_de_extension')

        reasons = s.readiness(self.root, structured)['reasons']

        self.assertIn('MISSING_RIVAL', reasons)

    def test_structured_contract_lock_does_not_replace_preregistration_proof(self):
        structured = structured_fixture()

        result = s.readiness(self.root, structured)

        self.assertFalse(any(reason.startswith('MISSING_') for reason in result['reasons']), result)
        self.assertIn('FROZEN_DESIGN_UNVERIFIED', result['reasons'])
        self.assertIn('STRUCTURED_DESIGN_UNVERIFIED', result['reasons'])
        self.assertFalse(result['eligible'])

    def test_hybrid_freeze_binds_all_structured_inputs_even_with_legacy_method(self):
        structured = structured_fixture()
        legacy = fixture()
        for key in ('null', 'rival', 'method', 'dataset_and_selection'):
            structured[key] = legacy[key]
        structured['prereg_ref'] = 'synthetic-hybrid-prereg'
        structured['prereg_hash'] = e.prereg_hash(structured['id'], s._readiness_contract_view(structured))
        self.assertTrue(s.readiness(self.root, structured)['eligible'])
        for key in ('scientific_question', 'mechanism', 'null_contract', 'input_contract',
                    'estimator_contract', 'environment_operator_contract', 'decision_contract'):
            with self.subTest(key=key):
                changed = copy.deepcopy(structured)
                if isinstance(changed[key], dict):
                    changed[key]['changed_after_freeze'] = 'different scientific declaration'
                else:
                    changed[key] += ' changed after freeze'
                before = copy.deepcopy(changed)
                result = s.readiness(self.root, changed)
                self.assertFalse(result['eligible'])
                self.assertIn('FROZEN_DESIGN_CHANGED', result['reasons'])
                self.assertEqual(changed, before)

    def test_structured_prereg_hash_binds_each_normalized_scientific_input(self):
        structured = structured_fixture()
        structured['prereg_hash'] = e.prereg_hash(
            structured['id'], s._readiness_contract_view(structured)
        )
        structured['prereg_ref'] = 'synthetic-structured-prereg'
        self.assertTrue(s.readiness(self.root, structured)['eligible'])

        mutations = {
            'question': lambda value: value.update(
                scientific_question='Changed structured question.'
            ),
            'null': lambda value: value['null_contract'].update(
                primary='Changed synthetic null.'
            ),
            'input': lambda value: value['input_contract']['clustering_de_extension'].update(
                framework='Changed synthetic rival.'
            ),
            'estimator': lambda value: value['estimator_contract'].update(
                procedure='Changed synthetic estimator.'
            ),
            'decision': lambda value: value['decision_contract'].update(
                SHIFT='p < 0.01 and the declared effect has the expected sign.'
            ),
            'operator': lambda value: value['environment_operator_contract']['primary_environment'].update(
                product='Changed synthetic field.'
            ),
        }
        for name, mutate in mutations.items():
            with self.subTest(field=name):
                changed = copy.deepcopy(structured)
                mutate(changed)
                before = copy.deepcopy(changed)

                result = s.readiness(self.root, changed)

                self.assertFalse(result['eligible'], result)
                self.assertIn('FROZEN_DESIGN_CHANGED', result['reasons'])
                self.assertEqual(changed, before)

    def test_unknown_binding_is_recorded_blocked(self):
        self.test.update(status='DRAFT',state='DRAFT'); self.test.pop('recipe'); self.test.pop('recipe_params')
        self.put(self.test)
        output, report = self.apply([{'kind':'RECIPE_BIND','created_at':NOW,'payload':{'test_id':self.test['id'],'recipe':'missing_recipe','params':{}}}])
        test = next(v['value'] for v in output['files'].values() if v.get('value',{}).get('id') == self.test['id'])
        self.assertEqual(test['status'], 'BLOCKED_INPUT')
        self.assertFalse(test['readiness']['eligible'])

    def test_terminal_cannot_be_reserved(self):
        self.test.update(status='DONE',state='DONE',verdict='PROMOTED',review_state='CONFIRMED',executed_at=END)
        self.put(self.test)
        with self.assertRaises(ProposalError):
            e.battery_requests({'created_at':NOW},self.spec(),self.root)

    def test_duplicate_members_rejected_before_mutation(self):
        body=self.spec(); body['tests'] *= 2
        with self.assertRaises(ProposalError):
            e.battery_requests({'created_at':NOW},body,self.root)
        self.assertEqual(s.batteries(self.root), [])

    def test_two_operators_cannot_reserve_one_test(self):
        self.reserve()
        with self.assertRaises(ProposalError):
            e.battery_requests({'created_at':NOW},self.spec('bat-audit-two'),self.root)
        self.assertEqual(s.entity(self.root,self.test['id'])['status'],'QUEUED')

    def test_equivalent_execution_with_different_test_id_is_rejected(self):
        self.reserve(); equivalent=fixture('TEST-B'); self.put(equivalent)
        body=self.spec('bat-audit-two'); body['tests'][0]['test_id']='TEST-B'
        with self.assertRaises(ProposalError):
            e.battery_requests({'created_at':NOW},body,self.root)

    def test_exact_retry_is_noop_and_conflicting_retry_rejected(self):
        self.reserve()
        self.assertEqual(e.battery_requests({'created_at':NOW},self.spec(),self.root),[])
        body=self.spec(); body['tests'][0]['params']['seed']=18
        with self.assertRaises(ProposalError):
            e.battery_requests({'created_at':NOW},body,self.root)

    def test_changed_dispatch_parameters_rejected(self):
        body=self.spec(); body['tests'][0]['params']['seed']=18
        with self.assertRaises(ProposalError):
            e.battery_requests({'created_at':NOW},body,self.root)

    def test_ambiguous_dispatch_is_not_running(self):
        self.reserve()
        requests=e.battery_status_requests(
            {'created_at': NOW, '_writer_dispatch_token': s.WRITER_DISPATCH_TOKEN},
            {'battery_id': 'bat-audit-one', 'status': 'DISPATCHED', 'run_ref': 'github-actions'},
            self.root,
            _result_request,
        )
        self.assertEqual(requests[0]['merge']['batteries'][0]['status'],'DISPATCH_PENDING')
        self.assertEqual(requests[1]['changes']['status'],'DISPATCH_PENDING')

    def test_external_writer_label_cannot_forge_internal_dispatch_pending(self):
        self.reserve()
        with self.assertRaisesRegex(ProposalError, 'WRITER_DISPATCH_CONTEXT_REQUIRED'):
            e.battery_status_requests(
                {'source': 'WRITER_ROBOT', '_inbox_name': 'robot-dispatch-bat-audit-one', 'created_at': NOW},
                {'battery_id': 'bat-audit-one', 'status': 'DISPATCHED', 'run_ref': 'github-actions'},
                self.root,
                _result_request,
            )
        self.assertEqual(s.batteries(self.root)[0]['status'], 'QUEUED')
        self.assertEqual(s.entity(self.root, 'TEST-A')['execution_phase'], 'QUEUED')

    def test_untrusted_runner_label_is_rejected(self):
        self.reserve()
        with self.assertRaises(ProposalError):
            e.battery_status_requests({'source':'WRITER_ROBOT','created_at':NOW},{'battery_id':'bat-audit-one','status':'RUNNING','run_ref':'actions/runs/123','started_tests':{'TEST-A':NOW}},self.root,_result_request)

    def test_running_requires_actual_step_timestamp(self):
        self.reserve()
        with self.assertRaises(ProposalError):
            e.battery_status_requests({'_inbox_source':'RUNNER_OBSERVATION','created_at':NOW},{'battery_id':'bat-audit-one','status':'RUNNING','run_ref':'actions/runs/123'},self.root,_result_request)

    def test_complete_valid_execution_path(self):
        battery=self.reserve(); spec=battery['tests'][0]
        item={'_inbox_source':'RUNNER_OBSERVATION','created_at':END}
        started={'battery_id':battery['id'],'status':'RUNNING','run_ref':'actions/runs/123','started_tests':{'TEST-A':NOW}}
        with redirect_stderr(io.StringIO()):
            receipts=apply_requests(self.root,e.battery_status_requests(item,started,self.root,_result_request))
        self.assertTrue(all(r['accepted'] for r in receipts),receipts)
        self.assertEqual(s.entity(self.root,'TEST-A')['status'],'RUNNING')
        completed={'battery_id':battery['id'],'status':'DONE','run_ref':'actions/runs/123','completed_at':END,'conclusion':'success',
                   'results':[{'test_id':'TEST-A','attempt_id':spec['attempt_id'],'recipe_sha256':spec['recipe_sha256'],
                               'executed_at':END,'ok':True,'result':{'verdict':'INCONCLUSIVE','decision':'SYNTHETIC_ONLY','summary':'Fixture'}}]}
        with redirect_stderr(io.StringIO()):
            receipts=apply_requests(self.root,e.battery_status_requests(item,completed,self.root,_result_request))
        self.assertTrue(all(r['accepted'] for r in receipts),receipts)
        completed_test = s.entity(self.root,'TEST-A')
        self.assertEqual(completed_test['verdict'],'INCONCLUSIVE')
        self.assertEqual(completed_test['executed_at'],END)
        self.assertEqual(completed_test['execution_phase'],'COMPLETED')
        readiness = s.readiness(self.root, completed_test)
        self.assertFalse(readiness['eligible'])
        self.assertIn('TERMINAL_TEST', readiness['reasons'])

    def test_advisor_cannot_close_execution_phase_without_a_result_proof(self):
        before = s.entity(self.root, 'TEST-A')
        receipt = apply_requests(self.root, [{
            'request_id': 'REQ-UNPROVEN-PHASE-CLOSE', 'entity_kind': 'test',
            'entity_name': 'TEST-A', 'expected_version': before['entity_version'],
            'writer_role': 'ADVISOR', 'event_type': 'TEST_PHASE_SET',
            'changes': {'execution_phase': 'COMPLETED'},
        }])[0]
        self.assertFalse(receipt['accepted'])
        self.assertEqual(receipt['issue']['code'], 'EXECUTION_PHASE_CLOSURE_REQUIRES_VERIFIED_RESULT')
        after = s.entity(self.root, 'TEST-A')
        self.assertEqual(after['status'], before['status'])
        self.assertEqual(after.get('execution_phase'), before.get('execution_phase'))
        self.assertNotIn('verdict', after)

    def test_ready_test_cannot_claim_running_phase_without_runner_observation(self):
        before = s.entity(self.root, 'TEST-A')
        requests = [
            {'request_id': 'REQ-UNPROVEN-PHASE-RUNNING', 'entity_kind': 'test',
             'entity_name': 'TEST-A', 'expected_version': before['entity_version'],
             'writer_role': 'ADVISOR', 'event_type': 'TEST_PHASE_SET',
             'changes': {'execution_phase': 'RUNNING'}},
            {'request_id': 'REQ-UNPROVEN-TEST-RUNNING', 'entity_kind': 'test',
             'entity_name': 'TEST-A', 'expected_version': before['entity_version'],
             'writer_role': 'EXECUTOR', 'event_type': 'TEST_RUNNING',
             'changes': {'status': 'RUNNING', 'state': 'RUNNING', 'execution_phase': 'RUNNING'}},
        ]
        receipts = apply_requests(self.root, requests)
        self.assertTrue(all(not receipt['accepted'] for receipt in receipts), receipts)
        after = s.entity(self.root, 'TEST-A')
        self.assertEqual(after['status'], before['status'])
        self.assertEqual(after.get('execution_phase'), before.get('execution_phase'))
        self.assertNotIn('started_at', after)

    def test_ready_test_cannot_accept_forged_terminal_result_or_phase_closure(self):
        before = s.entity(self.root, 'TEST-A')
        receipt = apply_requests(self.root, [{
            'request_id': 'REQ-FORGED-TERMINAL-RESULT', 'entity_kind': 'test',
            'entity_name': 'TEST-A', 'expected_version': before['entity_version'],
            'writer_role': 'EXECUTOR', 'event_type': 'TEST_RESULT_RECORDED',
            'changes': {'status': 'DONE', 'state': 'DONE', 'execution_phase': 'COMPLETED',
                        'verdict': 'INCONCLUSIVE', 'executed_at': END,
                        'run_ref': 'actions/runs/123'},
        }])[0]
        self.assertFalse(receipt['accepted'])
        self.assertEqual(receipt['issue']['code'], 'EXECUTION_PHASE_RESULT_PROOF_REQUIRED')
        after = s.entity(self.root, 'TEST-A')
        self.assertEqual(after['status'], before['status'])
        self.assertEqual(after.get('execution_phase'), before.get('execution_phase'))
        self.assertNotIn('verdict', after)
        self.assertNotIn('executed_at', after)

    def test_terminal_import_cannot_overwrite_queued_active_reservation(self):
        self.reserve()
        before = s.entity(self.root, 'TEST-A')
        receipt = apply_requests(self.root, [{
            'request_id': 'REQ-ACTIVE-MANUAL-RESULT', 'entity_kind': 'test',
            'entity_name': 'TEST-A', 'expected_version': before['entity_version'],
            'writer_role': 'EXECUTOR', 'event_type': 'TEST_RESULT_RECORDED',
            'changes': {'status': 'DONE', 'state': 'DONE', 'verdict': 'INCONCLUSIVE',
                        'executed_at': END},
        }])[0]
        self.assertFalse(receipt['accepted'])
        self.assertEqual(receipt['issue']['code'], 'EXECUTION_PHASE_RESULT_PROOF_REQUIRED')
        after = s.entity(self.root, 'TEST-A')
        self.assertEqual(after['status'], 'QUEUED')
        self.assertEqual(after.get('execution_phase'), 'QUEUED')
        self.assertNotIn('verdict', after)

    def test_raw_battery_document_cannot_forge_runner_completion_proof(self):
        battery = self.reserve()
        forged = dict(battery, status='DONE', run_ref='actions/runs/123',
                      completed_at=END, done_at=END,
                      execution_observation='GITHUB_RUN_AND_ARTIFACT',
                      conclusion='success', ok=1, failed=0)
        receipt = apply_requests(self.root, [{
            'request_id': 'REQ-RAW-BATTERY-DONE', 'document': 'evolution/batteries.json',
            'merge': {'batteries': [forged]}, 'list_merge': {'batteries': 'id'},
        }])[0]
        self.assertFalse(receipt['accepted'])
        self.assertEqual(receipt['issue']['code'], 'BATTERY_STATUS_WRITER_PROOF_REQUIRED')
        self.assertEqual(s.batteries(self.root)[0]['status'], 'QUEUED')

    def test_foreign_result_members_rejected(self):
        self.reserve()
        with self.assertRaises(ProposalError):
            e.battery_status_requests({'_inbox_source':'RUNNER_OBSERVATION'},{'battery_id':'bat-audit-one','status':'DONE','run_ref':'actions/runs/123','completed_at':END,'results':[{'test_id':'OTHER','ok':False}]},self.root,_result_request)

    def test_recipe_hash_mismatch_rejected(self):
        battery=self.reserve(); spec=battery['tests'][0]
        with self.assertRaises(ProposalError):
            e.battery_status_requests({'_inbox_source':'RUNNER_OBSERVATION'},{'battery_id':battery['id'],'status':'DONE','run_ref':'actions/runs/123','completed_at':END,
                'results':[{'test_id':'TEST-A','ok':True,'result':{'verdict':'PROMOTED'},'attempt_id':spec['attempt_id'],'recipe_sha256':'b'*64}]},self.root,_result_request)

    def test_ambiguous_external_run_not_blindly_repeated(self):
        save(self.root,e.BATTERIES_DOC,{'batteries':[{'id':'old','status':'DISPATCHED','dispatched_at':'2020-01-01T00:00:00Z'}]})
        self.assertEqual(e.pending_batteries(self.root),[])

    def test_full_family_bh_includes_negatives(self):
        tests=[{'id':str(i),'roadmap_id':'rm','verdict':'PROMOTED' if i<2 else 'REJECTED','statistics':{'p_value':p}}
               for i,p in enumerate([.04,.049]+[.9]*98)]
        result=s.fdr_annotations(tests)['0']
        self.assertEqual(result['q_value'],.9); self.assertEqual(result['n'],100); self.assertFalse(result['survives'])
        try:
            from scipy.stats import false_discovery_control
        except ImportError:
            return
        self.assertAlmostEqual(result['q_value'],false_discovery_control([.04,.049]+[.9]*98)[0])

    def test_incomplete_family_never_passes(self):
        result=s.fdr_annotations([{'id':'a','roadmap_id':'rm','statistics':{'p_value':.001}},{'id':'b','roadmap_id':'rm'}])['a']
        self.assertIsNone(result['q_value']); self.assertIsNone(result['survives']); self.assertEqual(result['n_missing'],1)

    def test_invalid_p_values_excluded(self):
        for value in (True,float('nan'),float('inf'),-1,2):
            self.assertIsNone(s.p_value({'statistics':{'p_value':value}}))

    def attack(self):
        attack=fixture('ATTACK-A'); attack.update(contests_test_id='TEST-A',status='DONE',state='DONE',verdict='PROMOTED',executed_at=END)
        attack['independence']={'axis':'data','evidence_refs':['entities/evidence/input-b.json'],'frozen_at':NOW,'on_pass':'CONFIRMED','on_fail':'REFUTED'}
        attack['independence_fingerprint']=s.digest(attack['independence'])
        save(self.root,'entities/evidence/input-b.json',{'id':'input-b','source':'synthetic_fixture'})
        return attack

    def test_same_data_attack_cannot_confirm(self):
        attack=self.attack(); self.assertIn('INDEPENDENT_AXIS_NOT_DISTINCT',s.independence(self.test,attack,self.root)['reasons'])
        self.test.update(status='DONE',state='DONE',verdict='PROMOTED',executed_at=NOW,review_state='CONTESTED')
        self.put(self.test); self.put(attack)
        requests=e.contest_chain_reconcile_requests(self.root)
        self.assertFalse(any(r.get('changes',{}).get('review_state')=='CONFIRMED' for r in requests))

    def test_independence_requires_resolved_provenance(self):
        attack=self.attack(); attack['dataset_and_selection']='different'
        attack['prereg_hash']=e.prereg_hash(attack['id'],attack)
        (self.root/'entities/evidence/input-b.json').unlink()
        self.assertIn('INDEPENDENCE_REFERENCE_UNRESOLVED',s.independence(self.test,attack,self.root)['reasons'])

    def test_distinct_frozen_declaration_with_polarity(self):
        attack=self.attack(); attack['dataset_and_selection']='Independent generated sample B'
        attack['prereg_hash']=e.prereg_hash(attack['id'],attack)
        self.assertTrue(s.independence(self.test,attack,self.root)['eligible'])
        attack['independence'].update(on_pass='REFUTED',on_fail='CONFIRMED')
        attack['independence_fingerprint']=s.digest(attack['independence'])
        self.test.update(status='DONE',state='DONE',verdict='PROMOTED',executed_at=NOW,review_state='CONTESTED')
        self.put(self.test); self.put(attack)
        requests=e.contest_chain_reconcile_requests(self.root)
        self.assertEqual(requests[0]['changes']['review_state'],'REFUTED')

    def test_mutated_independence_commitment_detected(self):
        attack=self.attack(); attack['independence']['on_pass']='REFUTED'
        self.assertIn('INDEPENDENCE_COMMITMENT_UNVERIFIED',s.independence(self.test,attack,self.root)['reasons'])

    def test_new_child_does_not_inherit_result(self):
        self.test.update(status='DONE',state='DONE',verdict='PROMOTED',executed_at=NOW,semantic={'domain_id':'science','result_meaning':'Parent passed','verdict_plain':'Passed'})
        self.put(self.test); seen=[]
        def hypothesis(item,body,root):
            seen.append(body); return []
        e.contest_requests({'created_at':NOW},{'test_id':'TEST-A','contest_test':{'question':'Attack'}},self.root,hypothesis)
        self.assertNotIn('result_meaning',seen[0]['semantic']); self.assertNotIn('verdict_plain',seen[0]['semantic'])

    def test_guard_rejects_raw_terminal_reopening(self):
        self.test.update(status='DONE',state='DONE',verdict='PROMOTED',executed_at=END)
        self.put(self.test)
        self.assertFalse(s.guard_transition(self.root,{'entity_kind':'test','entity_name':'TEST-A','changes':{'status':'READY','state':'READY'}})['accepted'])

    def test_state_alias_mismatch_is_rejected(self):
        refusal=s.guard_transition(self.root,{'entity_kind':'test','entity_name':'TEST-A','changes':{'state':'RUNNING'}})
        self.assertFalse(refusal['accepted'])

    def test_public_metrics_exclude_private_and_nominal_throughput(self):
        private=fixture('PRIVATE'); private['private']=True
        report=s.public_execution_summary(self.root,[self.test,private])
        self.assertEqual(report['counts']['ready_unverified'],1)
        self.assertNotIn('PRIVATE',json.dumps(report)); self.assertIsNone(report['throughput_per_hour'])

    def test_timestamps_are_timezone_aware(self):
        self.assertEqual(s.timestamp('2026-09-30T07:00:00-03:00'),s.timestamp(NOW))
        self.assertIsNone(s.timestamp('2026-09-30T10:00:00'))

    def test_partial_batch_does_not_acknowledge_parent(self):
        items=[{'kind':'BATCH','_inbox_name':'batch-a','payload':{'items':[{},{}]}}]
        self.assertFalse(_fully_handled('batch-a',items,{'batch-a-0'}))
        self.assertTrue(_fully_handled('batch-a',items,{'batch-a-0','batch-a-1'}))

    def test_protected_identity_yields_structured_refusal(self):
        refusal = s.guard_transition(self.root, {'entity_kind':'test', 'entity_name':'TEST-A', 'changes':{'id':'other'}})
        self.assertFalse(refusal['accepted'])

    def test_transient_http_errors_do_not_spend_scientific_attempts(self):
        for log in ('HTTP 429', 'HTTP 502', 'HTTP 503', 'HTTP 504'):
            self.assertEqual(e.classify_failure(log), 'TRANSIENT')

    def test_late_collection_preserves_actual_completion_time(self):
        battery = self.reserve(); spec = battery['tests'][0]
        item = {'_inbox_source':'RUNNER_OBSERVATION', 'created_at':'2026-09-30T12:00:00Z'}
        started = {'battery_id':battery['id'], 'status':'RUNNING', 'run_ref':'actions/runs/123',
                   'started_tests':{'TEST-A':NOW}}
        with redirect_stderr(io.StringIO()):
            start_receipts = apply_requests(self.root, e.battery_status_requests(item, started, self.root, _result_request))
        self.assertTrue(all(r['accepted'] for r in start_receipts), start_receipts)
        payload = {'battery_id':battery['id'], 'status':'DONE', 'run_ref':'actions/runs/123', 'completed_at':END,
            'conclusion':'success',
            'results':[{'test_id':'TEST-A', 'attempt_id':spec['attempt_id'], 'recipe_sha256':spec['recipe_sha256'],
                'ok':True, 'result':{'verdict':'INCONCLUSIVE','summary':'Fixture'}}]}
        with redirect_stderr(io.StringIO()):
            receipts = apply_requests(self.root, e.battery_status_requests(item, payload, self.root, _result_request))
        self.assertTrue(all(r['accepted'] for r in receipts), receipts)
        self.assertEqual(s.batteries(self.root)[0]['completed_at'], END)

if __name__ == '__main__':
    unittest.main()
