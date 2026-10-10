from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from runtime.nexo_agent_api.frontier import _lifecycle, _resume_evidence, roadmap_frontier
from runtime.nexo_agent_api.tower_paths import entity_path


class FrontierEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        for folder in ['indexes', 'roadmaps', 'entities/test', 'evolution']:
            (self.root / folder).mkdir(parents=True, exist_ok=True)
        self._write('indexes/active-roadmaps.json', {'items': [
            {'roadmap_id': 'RM-A', 'state': 'ACTIVE', 'priority': 'P0'}]})
        self._write('roadmaps/RM-A.json', {'roadmap_id': 'RM-A', 'frontier_refs': ['T-A']})

    def _write(self, relative, value):
        (self.root / relative).write_text(json.dumps(value), encoding='utf-8')

    def _test(self, value):
        entity_path(self.root, 'test', value['id']).write_text(json.dumps(value), encoding='utf-8')

    @staticmethod
    def _started(state='RUNNING'):
        return {'id': 'T-A', 'state': state, 'execution_observation': 'GITHUB_JOB_STEP',
                'started_at': '2026-10-04T12:00:00Z', 'run_ref': 'actions/runs/123'}

    def test_missing_record_is_missing_not_ready(self):
        self.assertEqual(_lifecycle(None), 'MISSING')

    def test_record_without_lifecycle_is_unknown(self):
        self.assertEqual(_lifecycle({'id': 'T-A'}), 'UNKNOWN')

    def test_indexed_unknown_record_does_not_enter_batch(self):
        self._test({'id': 'T-A'})
        value = roadmap_frontier(self.root)
        self.assertEqual(value['ready'], [])
        self.assertEqual(value['batch'], [])
        self.assertEqual(value['waiting'][0]['reason'], 'NOT_READY_UNKNOWN')

    def test_explicit_ready_and_dependencies_are_preserved(self):
        self._test({'id': 'T-A', 'state': 'READY', 'depends_on': ['T-B']})
        self._test({'id': 'T-B', 'state': 'DONE'})
        self.assertEqual(roadmap_frontier(self.root)['next']['test_id'], 'T-A')

    def test_unknown_dependency_is_not_terminal(self):
        self._test({'id': 'T-A', 'state': 'READY', 'depends_on': ['T-B']})
        self._test({'id': 'T-B'})
        self.assertEqual(roadmap_frontier(self.root)['waiting'][0]['waiting_on'], ['T-B'])

    def test_legacy_checkpoint_is_visible_but_not_authorized(self):
        self._test({'id': 'T-A', 'state': 'CHECKPOINTED'})
        value = roadmap_frontier(self.root)
        self.assertEqual(value['resumable'][0]['test_id'], 'T-A')
        evidence = value['resume_evidence_missing'][0]['resume_evidence']
        self.assertEqual(evidence['missing_evidence'],
                         ['EXECUTION_START_EVIDENCE_MISSING', 'CHECKPOINT_REFERENCE_MISSING'])
        self.assertEqual(evidence['action'], 'RECONCILE_EVIDENCE')
        self.assertFalse(evidence['execution_authorized'])

    def test_materialized_checkpoint_gets_same_evidence_annotation(self):
        self._test({'id': 'T-A', 'state': 'DONE'})
        self._test({'id': 'T-ORPHAN', 'state': 'CHECKPOINTED', 'roadmap_id': 'RM-A'})
        value = roadmap_frontier(self.root)
        self.assertEqual(value['resume_evidence_missing'][0]['test_id'], 'T-ORPHAN')

    def test_recorded_running_proof_uses_existing_integrity_convention(self):
        evidence = _resume_evidence(self._started())
        self.assertTrue(evidence['recorded_start_verified'])
        self.assertEqual(evidence['missing_evidence'], [])
        self.assertFalse(evidence['execution_authorized'])

    def test_checkpoint_reference_does_not_claim_artifact_validation(self):
        evidence = _resume_evidence({**self._started('CHECKPOINTED'), 'checkpoint_ref': 'artifact:checkpoint-1'})
        self.assertTrue(evidence['checkpoint_reference_recorded'])
        self.assertEqual(evidence['action'], 'VERIFY_RUNTIME_BEFORE_RESUME')
        self.assertFalse(evidence['execution_authorized'])

    def test_missing_timezone_or_invalid_run_does_not_prove_start(self):
        for change in [{'started_at': '2026-10-04T12:00:00'}, {'run_ref': 'actions/runs/0'},
                       {'run_ref': 'https://example.com/actions/runs/123'}, {'execution_observation': 'QUEUED'}]:
            with self.subTest(change=change):
                self.assertFalse(_resume_evidence({**self._started(), **change})['recorded_start_verified'])

    def test_blank_and_non_string_checkpoint_are_not_references(self):
        for checkpoint in ['', '  ', None, {}, 123]:
            with self.subTest(checkpoint=checkpoint):
                evidence = _resume_evidence({**self._started('CHECKPOINTED'), 'checkpoint_ref': checkpoint})
                self.assertIn('CHECKPOINT_REFERENCE_MISSING', evidence['missing_evidence'])

    def test_inspection_does_not_mutate_canonical_files(self):
        entity = self._started('CHECKPOINTED')
        before = copy.deepcopy(entity)
        self._test(entity)
        raw_before = entity_path(self.root, 'test', 'T-A').read_bytes()
        roadmap_frontier(self.root)
        self.assertEqual(entity_path(self.root, 'test', 'T-A').read_bytes(), raw_before)
        self.assertEqual(entity, before)


if __name__ == '__main__':
    unittest.main()
