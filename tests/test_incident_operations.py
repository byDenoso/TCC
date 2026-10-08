"""Offline canonical incident linkage, accountability, validation and privacy."""
import copy
import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from unittest.mock import patch

from runtime.nexo_agent_api import AgentService, evolution as e, execution_recovery as r
from runtime.nexo_agent_api import incident_operations as ops, scientific_integrity as s
from runtime.nexo_agent_api.service import TowerAgentIssue
from runtime.nexo_agent_api.tower_apply import apply_requests
from tests.test_scientific_integrity import fixture, save


class IncidentOperationsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / 'tower'
        recipes = Path(self.tmp.name) / 'recipes'
        save(recipes, 'smoke/audit_recipe.json', {})
        (recipes / 'audit_recipe.py').write_text('result = 1\n')
        self.env = patch.dict(os.environ, {'NEXO_RECIPE_ROOT': str(recipes)})
        self.env.start(); self.addCleanup(self.env.stop)
        save(self.root, 'CONTROL.json', {'mode': 'ACTIVE'})
        self.test = fixture()
        self.binding = self.test.pop('data_binding')
        self.put('test', self.test)
        self.incident = {'incident_id': 'INC-TEST', 'signal_code': 'INPUT_PROVENANCE_INCOMPLETE',
                         'signal_test_ids': [self.test['id']], 'state': 'OBSERVED', 'next_owner': 'LEARNER'}
        self.reconcile()

    def put(self, kind, value):
        # `save` accepts a logical Tower path and applies Windows escaping.
        # Passing entity_path() here would escape the already escaped path a
        # second time, creating a duplicate entity file on Windows.
        save(self.root, f"entities/{kind}/{value['id']}.json", value)

    def reconcile(self):
        with redirect_stderr(io.StringIO()):
            receipts = apply_requests(self.root, r.reconcile_requests(self.root))
        self.assertTrue(all(x['accepted'] for x in receipts), receipts)

    def work(self):
        return r._entities(self.root, 'work')[0]

    def view(self, public=False):
        return ops.project(self.root, self.incident, public=public)

    def complete(self):
        test = s.entity(self.root, self.test['id']); test['data_binding'] = self.binding
        self.put('test', test); self.reconcile()

    def test_exact_existing_work_route_is_separate_from_learning(self):
        before = copy.deepcopy(self.test)
        view = self.view()
        self.assertEqual(view['work_ids'], [self.work()['id']])
        self.assertEqual(view['items'][0]['current_owner'], 'ADVISOR')
        self.assertEqual(view['items'][0]['assigned_to'], 'EXECUTOR')
        self.assertFalse(view['items'][0]['accepted'])
        self.assertEqual(view['items'][0]['ownership_state'], 'ASSIGNED_UNACCEPTED')
        public = e._public_incidents(self.root, [self.incident])[0]
        self.assertEqual(public['next_owner'], 'LEARNER')
        self.assertEqual(public['learning_state'], 'OBSERVED')
        self.assertEqual(public['operational'], self.view(public=True))
        self.assertEqual({k: s.entity(self.root, self.test['id']).get(k) for k in s.FROZEN},
                         {k: before.get(k) for k in s.FROZEN})

    def test_cause_routes_definition_recipe_and_inputs(self):
        for reasons, expected in [(['FROZEN_DESIGN_CHANGED'], 'LEARNER'),
                                  (['CONFLICTING_RECORDED_DATA_BINDING'], 'LEARNER'),
                                  (['RECIPE_BINDING_MISSING'], 'EXECUTOR'),
                                  (['PREFLIGHT_INVALID'], 'EXECUTOR'),
                                  (['INPUT_PROVENANCE_INCOMPLETE'], 'EXECUTOR')]:
            self.assertEqual(r._route(reasons)[0], expected)
        self.assertEqual(r._route(['RECIPE_BINDING_MISSING'], domain='ENGINEERING')[0], 'ADVISOR')
        self.assertEqual(r._route(['RECIPE_BINDING_MISSING'], domain='OLYMPUS')[0], 'ADVISOR')
        for code, expected in ops.CAUSE_OWNER.items():
            self.incident['signal_code'] = code
            self.incident['signal_test_ids'] = []
            self.assertEqual(self.view()['suggested_owner'], expected)

    def test_ack_requires_current_recipient_and_route(self):
        r.ensure_handoffs(self.root)
        service = AgentService(self.root)
        event = service.inbox_for('EXECUTOR')[0]
        with self.assertRaises(TowerAgentIssue):
            service.transition_handoff(event['handoff_id'], state='ACK', writer_role='LEARNER')
        self.assertFalse(self.view()['items'][0]['accepted'])
        service.transition_handoff(event['handoff_id'], state='ACK', writer_role='EXECUTOR')
        item = self.view()['items'][0]
        self.assertTrue(item['accepted']); self.assertEqual(item['current_owner'], 'EXECUTOR')
        work = self.work(); work['recovery']['route_generation'] += 1
        work['recovery']['ownership_state'] = 'ASSIGNED_UNACCEPTED'; self.put('work', work)
        with self.assertRaises(TowerAgentIssue):
            service.transition_handoff(event['handoff_id'], state='ACK', writer_role='EXECUTOR')
        self.assertFalse(self.view()['items'][0]['accepted'])

    def test_forged_acceptance_label_without_canonical_ack_is_not_accepted(self):
        work = self.work(); work['recovery']['ownership_state'] = 'ACCEPTED'
        work['recovery']['acceptance_source'] = {'handoff_id': 'invented'}
        self.put('work', work)
        self.assertFalse(self.view()['items'][0]['accepted'])

    def test_done_without_evidence_cannot_resolve(self):
        work = self.work(); work['status'] = 'DONE'; self.put('work', work)
        self.assertEqual(self.view()['state'], 'OPEN')
        self.assertEqual(self.view()['items'][0]['validation_state'], 'EVIDENCE_REQUIRED')

    def test_readiness_resolution_is_separate_and_revalidated(self):
        self.complete()
        self.assertEqual(self.view()['state'], 'RESOLVED')
        self.assertEqual(self.view()['scientific_effect'], 'NONE')
        self.assertEqual(self.incident['state'], 'OBSERVED')
        test = s.entity(self.root, self.test['id']); test['data_binding'] = None; self.put('test', test)
        self.assertEqual(self.view()['state'], 'OPEN')
        self.assertEqual(self.view()['items'][0]['validation_state'], 'REVALIDATION_REQUIRED')

    def test_terminal_test_does_not_reopen_verified_prerequisite_repair(self):
        self.complete()
        test = s.entity(self.root, self.test['id']); test.update(status='DONE', verdict='INCONCLUSIVE')
        self.put('test', test)
        self.assertEqual(self.view()['state'], 'RESOLVED')
        test['data_binding'] = None; self.put('test', test)
        self.assertEqual(self.view()['state'], 'OPEN')

    def test_wrong_prereg_or_recipe_hash_cannot_resolve(self):
        self.complete(); original = self.work()
        for key in ('prereg_hash', 'recipe_sha256', 'test_id'):
            work = copy.deepcopy(original); work['completion_evidence'][key] = 'wrong'; self.put('work', work)
            self.assertEqual(self.view()['state'], 'OPEN')

    def test_five_historical_causes_cannot_close_from_prerequisites_or_promoted(self):
        self.complete()
        for code in ops.CAUSE_OWNER:
            self.incident['signal_code'] = code
            self.assertEqual(self.view()['state'], 'OPEN', code)
            self.assertEqual(self.view()['next_action_code'], 'VERIFY_INCIDENT_CRITERION')
        test = s.entity(self.root, self.test['id']); test.update(status='DONE', verdict='PROMOTED', run_ref='36369882601')
        self.put('test', test)
        self.assertEqual(self.view()['state'], 'OPEN')

    def test_all_references_required_and_no_topic_link_guessing(self):
        self.complete()
        self.incident['signal_test_ids'].append('unresolved-test')
        self.assertEqual(self.view()['state'], 'OPEN')
        self.incident['signal_test_ids'] = []
        self.incident['topic_id'] = self.test.get('topic_id')
        self.assertEqual(self.view()['state'], 'UNLINKED')
        self.assertEqual(len(r._entities(self.root, 'work')), 1)

    def test_private_work_test_and_handoff_data_never_leak(self):
        r.ensure_handoffs(self.root)
        work = self.work(); work['next_action'] = 'SECRET ACTION'
        work['recovery']['candidate_artifact_refs'] = ['SECRET ARTIFACT']; self.put('work', work)
        payload = json.dumps(e._public_incidents(self.root, [self.incident]))
        for text in ('SECRET', 'acceptance_source', 'handoff_id', 'candidate_artifact_refs', 'unresolved_refs'):
            self.assertNotIn(text, payload)
        work['private'] = True; self.put('work', work)
        self.assertEqual(self.view(public=True)['work_ids'], [])
        self.assertNotIn(work['id'], json.dumps(self.view(public=True)))
        work['private'] = False; self.put('work', work)
        test = s.entity(self.root, self.test['id']); test['private'] = True; self.put('test', test)
        self.assertEqual(self.view(public=True)['work_ids'], [])

    def test_private_test_to_public_work_edge_is_not_disclosed(self):
        work = {'id': 'WORK-PUBLIC', 'owner_role': 'ADVISOR', 'status': 'OPEN'}
        self.put('work', work)
        test = s.entity(self.root, self.test['id']); test['private'] = True
        test['work_id'] = work['id']; self.put('test', test)
        self.assertEqual(self.view(public=True)['work_ids'], [])
        self.assertNotIn(work['id'], json.dumps(self.view(public=True)))
        # A separate explicit public link is allowed; the private TEST stays out.
        self.incident['signal_work_ids'] = [work['id']]
        self.assertEqual(self.view(public=True)['work_ids'], [work['id']])
        self.assertNotIn(self.test['id'], json.dumps(self.view(public=True)))
        self.assertNotEqual(self.view(public=True)['state'], 'RESOLVED')

    def test_superseded_offer_without_ack_cannot_fabricate_acceptance(self):
        from runtime.nexo_agent_api.handoff import _latest_by_handoff
        r.ensure_handoffs(self.root)
        event = AgentService(self.root).inbox_for('EXECUTOR')[0]
        self.complete(); r.ensure_handoffs(self.root)
        self.assertEqual(_latest_by_handoff(self.root)[event['handoff_id']]['state'], 'SUPERSEDED')
        work = self.work(); work['owner_role'] = event['to_role']
        work['recovery']['ownership_state'] = 'ACCEPTED'
        work['recovery']['acceptance_source'] = {k: event[k] for k in
                                                ('handoff_id', 'request_id', 'from_role', 'to_role')}
        self.put('work', work)
        self.assertFalse(self.view()['items'][0]['accepted'])

    def test_real_ack_remains_accepted_after_verified_completion(self):
        r.ensure_handoffs(self.root)
        service = AgentService(self.root)
        event = service.inbox_for('EXECUTOR')[0]
        service.transition_handoff(event['handoff_id'], state='ACK', writer_role='EXECUTOR')
        self.complete(); r.ensure_handoffs(self.root)
        self.assertTrue(self.view()['items'][0]['accepted'])
        self.assertEqual(self.view()['state'], 'RESOLVED')

    def test_ack_from_another_work_cannot_accept_this_work(self):
        r.ensure_handoffs(self.root)
        service = AgentService(self.root)
        event = service.inbox_for('EXECUTOR')[0]
        service.transition_handoff(event['handoff_id'], state='ACK', writer_role='EXECUTOR')
        other = copy.deepcopy(self.work()); other['id'] = 'WORK-OTHER'
        self.put('work', other)
        self.assertFalse(ops._accepted(self.root, other))

    def test_incident_reconcile_replay_is_noop(self):
        for aid in ('A', 'B'):
            save(self.root, 'entities/artifact/' + aid + '.json', {'id': aid, 'kind': 'LEARNING_SIGNAL',
                 'source': 'CHATGPT_TASK_EXECUTOR', 'payload': {'signals': [{'code': self.incident['signal_code'],
                 'topic_id': 'engineering.nexo_runtime.state_integrity', 'work_id': self.work()['id']}]}})
        with redirect_stderr(io.StringIO()):
            receipts = apply_requests(self.root, e.incident_reconcile_requests(self.root))
        self.assertTrue(receipts and all(x['accepted'] for x in receipts))
        self.assertEqual(e.incident_reconcile_requests(self.root), [])
        self.assertEqual(len(r._entities(self.root, 'work')), 1)

    def test_legacy_signal_refs_are_backfilled_without_duplicate_work(self):
        self.incident.update(topic_id='engineering.nexo_runtime.state_integrity', evidence_refs=['A', 'B'])
        save(self.root, e.INCIDENTS_DOC, {'incidents': [self.incident]})
        for aid in ('A', 'B'):
            save(self.root, 'entities/artifact/' + aid + '.json', {'id': aid, 'kind': 'LEARNING_SIGNAL',
                 'source': 'CHATGPT_TASK_EXECUTOR', 'payload': {'signals': [{'code': self.incident['signal_code'],
                 'topic_id': self.incident['topic_id'], 'work_id': self.work()['id']}]}})
        candidate = e._incident_candidates(self.root)[0]
        self.assertEqual(candidate['signal_work_ids'], [self.work()['id']])
        before = sorted(p.as_posix() for p in self.root.rglob('*'))
        self.assertEqual(ops.project(self.root, candidate), ops.project(self.root, candidate))
        self.assertEqual(before, sorted(p.as_posix() for p in self.root.rglob('*')))
        self.assertEqual(len(r._entities(self.root, 'work')), 1)


if __name__ == '__main__':
    unittest.main()
