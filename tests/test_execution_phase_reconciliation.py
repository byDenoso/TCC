from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from runtime.nexo_agent_api import evolution, scientific_integrity as integrity
from runtime.nexo_agent_api.execution_phase_reconciliation import build_reconciliation_plan
from runtime.nexo_agent_api.gpt_writer import apply_to_tower
from runtime.nexo_agent_api.inbox_apply import _result_request, proposal_to_requests
from runtime.nexo_agent_api.live_tower import (
    build_live_tower_payload,
    materialize_live_tower,
    read_live_tower_bytes,
    verify_live_tower,
)
from runtime.nexo_agent_api.tower_apply import apply_requests
from runtime.nexo_agent_api.tower_paths import entity_path, fs_path

NOW = '2026-09-30T10:00:00Z'
END = '2026-09-30T10:01:00Z'
TEST_ID = 'PHASE-D01-SANITIZED'
BATTERY_ID = 'bat-phase-sanitized'
RUN_REF = 'actions/runs/123'


def _save(root: Path, relative: str, value: dict) -> None:
    path = fs_path(root, relative)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding='utf-8')


def _item(raw: bytes, items: list[dict]) -> tuple[bytes, dict]:
    before = verify_live_tower(read_live_tower_bytes(raw))
    with tempfile.TemporaryDirectory() as temporary:
        root, _ = materialize_live_tower(raw, Path(temporary) / 'writer-root')
        receipts = []
        rejected = []
        for item in items:
            requests = ([item] if isinstance(item, dict) and item.get('event_type')
                        else proposal_to_requests(item, root))
            for request in requests:
                result = apply_requests(root, [request])[0]
                receipts.append(result)
                if not result.get('accepted', True) or result.get('issue'):
                    rejected.append({'item': item.get('_inbox_name'), 'reason': result.get('issue')})
        after = build_live_tower_payload(root)
        output = json.dumps(after, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')
        after_revision = verify_live_tower(read_live_tower_bytes(output))
    return output, {'before': before, 'after': after_revision, 'receipts': receipts,
                    'rejected': rejected, 'status': 'NO_OP' if before == after_revision else 'READY_TO_UPLOAD'}


def _entity_from_bundle(raw: bytes, test_id: str = TEST_ID) -> dict:
    bundle = read_live_tower_bytes(raw)
    return bundle['files'][f'entities/test/{test_id}.json']['value']


class ExecutionPhaseReconciliationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.temp_root = Path(self.temporary.name)
        self.root = self.temp_root / 'tower'
        self.root.mkdir()
        self.recipes = self.temp_root / 'recipes'
        (self.recipes / 'smoke').mkdir(parents=True)
        (self.recipes / 'audit_recipe.py').write_text('# inert admission fixture\nresult = 1\n', encoding='utf-8')
        _save(self.recipes, 'smoke/audit_recipe.json', {'fixture': True})
        self.env = patch.dict('os.environ', {'NEXO_RECIPE_ROOT': str(self.recipes)})
        self.env.start()
        _save(self.root, 'CONTROL.json', {'truth_owner': 'TOWER_V06@GOOGLE_DRIVE_PRIVATE'})
        self.test = {
            'id': TEST_ID,
            'entity_version': 1,
            'kind': 'TEST',
            'domain': 'SCIENCE',
            'status': 'READY',
            'state': 'READY',
            'question': 'Does the synthetic fixture remain bounded?',
            'null': 'The fixture is unbounded.',
            'rival': 'The fixture is bounded.',
            'method': 'Seeded synthetic sample.',
            'dataset_and_selection': 'Frozen generated fixture.',
            'success_criteria': 'abs(mean) < 1',
            'kill_criteria': 'abs(mean) >= 1',
            'claim_boundary': 'Synthetic test only.',
            'frozen_at': NOW,
            'recipe': 'audit_recipe',
            'recipe_params': {'seed': 17},
            'data_binding': {'status': 'BOUND', 'inputs': [{
                'name': 'sample', 'kind': 'generated', 'generator': 'fixture-v1',
                'seed': 17, 'sha256': 'a' * 64,
            }]},
        }
        self.test['prereg_hash'] = evolution.prereg_hash(TEST_ID, self.test)
        _save(self.root, f'entities/test/{TEST_ID}.json', self.test)

    def tearDown(self):
        self.env.stop()
        self.temporary.cleanup()

    def _initial_bundle(self) -> bytes:
        return json.dumps(build_live_tower_payload(self.root), ensure_ascii=False).encode('utf-8')

    def _battery_items(self) -> dict:
        return {'kind': 'TEST_BATTERY', '_inbox_source': 'WRITER_ROBOT',
                '_inbox_name': 'sanitized-battery', 'created_at': NOW,
                'payload': {'battery_id': BATTERY_ID,
                            'tests': [{'test_id': TEST_ID, 'recipe': 'audit_recipe',
                                       'params': {'seed': 17}, 'timeout_min': 10,
                                       'scientific_note': {'fixture_scope': 'synthetic'}}]}}

    def _running_item(self) -> dict:
        return {'kind': 'BATTERY_STATUS', '_inbox_source': 'RUNNER_OBSERVATION',
                '_inbox_name': 'sanitized-running', 'created_at': END,
                'payload': {'battery_id': BATTERY_ID, 'status': 'RUNNING',
                            'run_ref': RUN_REF, 'started_tests': {TEST_ID: NOW}}}

    def _completed_item(self, root: Path) -> dict:
        battery = integrity.batteries(root)[0]
        spec = battery['tests'][0]
        return {'kind': 'BATTERY_STATUS', '_inbox_source': 'RUNNER_OBSERVATION',
                '_inbox_name': 'sanitized-result', 'created_at': END,
                'payload': {'battery_id': BATTERY_ID, 'status': 'DONE',
                            'run_ref': RUN_REF, 'completed_at': END,
                            'conclusion': 'success', 'results': [{
                                'test_id': TEST_ID, 'attempt_id': spec['attempt_id'],
                                'recipe_sha256': spec['recipe_sha256'], 'executed_at': END,
                                'ok': True, 'result': {'verdict': 'INCONCLUSIVE',
                                                       'decision': 'SYNTHETIC_ONLY',
                                                       'summary': 'Sanitized fixture result.'},
                            }]}}

    def _successful_writer_bundle(self) -> bytes:
        raw = self._initial_bundle()
        raw, report = _item(raw, [self._battery_items()])
        self.assertFalse(report['rejected'], report)
        raw, report = _item(raw, [self._running_item()])
        self.assertFalse(report['rejected'], report)
        with tempfile.TemporaryDirectory() as current_dir:
            current_root, _ = materialize_live_tower(raw, Path(current_dir) / 'running')
            completed = self._completed_item(current_root)
            [test_request] = [request for request in proposal_to_requests(completed, current_root)
                              if request.get('entity_kind') == 'test']
        self.assertEqual(test_request['changes']['execution_phase'], 'COMPLETED')
        raw, report = _item(raw, [completed])
        self.assertFalse(report['rejected'], report)
        return raw

    def _legacy_terminal_root(self, raw: bytes, parent: Path) -> tuple[Path, dict]:
        root, _ = materialize_live_tower(raw, parent / 'legacy')
        test_path = entity_path(root, 'test', TEST_ID)
        test = json.loads(test_path.read_text(encoding='utf-8'))
        test['execution_phase'] = 'RUNNING'
        test_path.write_text(json.dumps(test), encoding='utf-8')
        battery_path = fs_path(root, evolution.BATTERIES_DOC)
        battery_doc = json.loads(battery_path.read_text(encoding='utf-8'))
        # Model a historical reservation written before exact source specs were
        # retained beside its canonical submission fingerprint.
        battery_doc['batteries'][0].pop('submitted_specs', None)
        battery_path.write_text(json.dumps(battery_doc), encoding='utf-8')
        return root, battery_doc

    def _source_proof(self, repo: Path, *, duplicate_envelope: bool = False) -> dict:
        source_item = self._battery_items()
        envelope = {
            'kind': 'TEST_BATTERY',
            'source': 'WRITER_ROBOT',
            'created_at': NOW,
            'payload': copy.deepcopy(source_item['payload']),
        }
        document = {'records': [envelope, copy.deepcopy(envelope)] if duplicate_envelope else [envelope]}
        source_bytes = json.dumps(document, ensure_ascii=False, sort_keys=True,
                                  separators=(',', ':')).encode('utf-8')
        inbox_path = repo / 'inbox' / 'original.json'
        inbox_path.parent.mkdir(parents=True, exist_ok=True)
        inbox_path.write_bytes(source_bytes)
        subprocess.run(['git', '-C', str(repo), 'init', '-q'], check=True,
                       capture_output=True)
        subprocess.run(['git', '-C', str(repo), 'add', '--', 'inbox/original.json'], check=True,
                       capture_output=True)
        subprocess.run(['git', '-C', str(repo), '-c', 'user.name=Fixture',
                        '-c', 'user.email=fixture@example.invalid', 'commit', '-q', '-m',
                        'sanitized source submission'], check=True, capture_output=True)
        commit = subprocess.run(['git', '-C', str(repo), 'rev-parse', 'HEAD'], check=True,
                                capture_output=True, text=True).stdout.strip()
        object_id = subprocess.run(['git', '-C', str(repo), 'rev-parse',
                                    'HEAD:inbox/original.json'], check=True,
                                   capture_output=True, text=True).stdout.strip()
        subprocess.run(['git', '-C', str(repo), 'update-ref',
                        'refs/remotes/origin/nexo-inbox', commit], check=True,
                       capture_output=True)
        specs = source_item['payload']['tests']
        return {
            'contract': integrity.EXECUTION_PHASE_SOURCE_PROOF_CONTRACT,
            'battery_id': BATTERY_ID,
            'submission_fingerprint': integrity.digest(specs),
            'submitted_specs': specs,
            'source_artifacts': [{
                'repository': 'TCC',
                'git_ref': 'refs/remotes/origin/nexo-inbox',
                'commit': commit,
                'object_id': object_id,
                'path': 'inbox/original.json',
                'source_sha256': hashlib.sha256(source_bytes).hexdigest(),
            }],
        }

    def test_terminal_result_closes_phase_in_real_writer_and_readiness(self):
        raw = self._successful_writer_bundle()
        completed = _entity_from_bundle(raw)
        self.assertEqual(completed['status'], 'DONE')
        self.assertEqual(completed['execution_phase'], 'COMPLETED')
        self.assertEqual(completed['executed_at'], END)
        self.assertIsNone(completed.get('review_state'))
        for key in ('prereg_hash', 'question', 'null', 'rival', 'method',
                    'dataset_and_selection', 'success_criteria', 'kill_criteria',
                    'claim_boundary'):
            self.assertEqual(completed[key], self.test[key], key)
        self.assertTrue(completed['attempt_id'].startswith('attempt-'))
        self.assertEqual(completed['execution_recipe_sha256'], completed['reproducibility']['recipe_sha256'])

        with tempfile.TemporaryDirectory() as output_dir:
            after_root, _ = materialize_live_tower(raw, Path(output_dir) / 'readback')
            readback = integrity.entity(after_root, TEST_ID)
            readiness = integrity.readiness(after_root, readback)
        self.assertFalse(readiness['eligible'])
        self.assertIn('TERMINAL_TEST', readiness['reasons'])

    def test_dry_run_requires_matching_attempt_and_writer_repair_is_idempotent(self):
        raw = self._successful_writer_bundle()
        with tempfile.TemporaryDirectory() as legacy_dir:
            legacy_root, _ = materialize_live_tower(raw, Path(legacy_dir) / 'legacy')
            path = entity_path(legacy_root, 'test', TEST_ID)
            before = json.loads(path.read_text(encoding='utf-8'))
            before['execution_phase'] = 'RUNNING'  # sanitized copy of the legacy defect
            path.write_text(json.dumps(before), encoding='utf-8')
            source_before = copy.deepcopy(before)

            report = build_reconciliation_plan(legacy_root, source_revision='sha256:' + 'b' * 64)
            self.assertEqual(report['mode'], 'DRY_RUN')
            self.assertEqual(report['summary']['proposal_count'], 1, report['conflicts'])
            self.assertEqual(report['summary']['conflict_count'], 0)
            self.assertEqual(json.loads(path.read_text(encoding='utf-8')), source_before)
            request = report['requests'][0]
            self.assertEqual(request['expected_version'], source_before['entity_version'])
            self.assertEqual(request['event_type'], 'TEST_EXECUTION_PHASE_RECONCILED')
            self.assertEqual(request['changes']['execution_phase'], 'COMPLETED')

            legacy_bundle = json.dumps(build_live_tower_payload(legacy_root), ensure_ascii=False).encode('utf-8')
            applied, writer_report = _item(legacy_bundle, [request])
            self.assertFalse(writer_report['rejected'], writer_report)
            after = _entity_from_bundle(applied)
            self.assertEqual(after['execution_phase'], 'COMPLETED')
            self.assertEqual(after['execution_phase_reconciliation']['policy'],
                             integrity.EXECUTION_PHASE_RECONCILIATION_POLICY)
            self.assertEqual(after['entity_version'], source_before['entity_version'] + 1)
            for key in ('prereg_hash', 'question', 'null', 'rival', 'method',
                        'dataset_and_selection', 'success_criteria', 'kill_criteria',
                        'claim_boundary', 'verdict', 'result_summary', 'statistics',
                        'review_state', 'executed_at', 'battery_id', 'attempt_id',
                        'execution_recipe_sha256'):
                self.assertEqual(after.get(key), source_before.get(key), key)

            replayed, replay_report = _item(applied, [request])
            self.assertEqual(replay_report['status'], 'NO_OP')
            self.assertEqual(replay_report['receipts'][0]['reason'],
                             'EXECUTION_PHASE_RECONCILIATION_ALREADY_APPLIED')
            self.assertEqual(read_live_tower_bytes(replayed)['state_fingerprint'],
                             read_live_tower_bytes(applied)['state_fingerprint'])
            with tempfile.TemporaryDirectory() as applied_dir:
                applied_root, _ = materialize_live_tower(applied, Path(applied_dir) / 'applied')
                repeated_plan = build_reconciliation_plan(applied_root)
            self.assertEqual(repeated_plan['summary']['proposal_count'], 0)
            events = [entry['value'] for name, entry in read_live_tower_bytes(applied)['files'].items()
                      if name.startswith('events/') and entry['value'].get('event_type') == request['event_type']]
            self.assertEqual(len(events), 1)

    def test_writer_maintenance_applies_only_proven_phase_reconciliation(self):
        raw = self._successful_writer_bundle()
        with tempfile.TemporaryDirectory() as legacy_dir:
            root, _ = materialize_live_tower(raw, Path(legacy_dir) / 'legacy')
            path = entity_path(root, 'test', TEST_ID)
            test = json.loads(path.read_text(encoding='utf-8'))
            test['execution_phase'] = 'RUNNING'
            path.write_text(json.dumps(test), encoding='utf-8')
            legacy_bundle = json.dumps(build_live_tower_payload(root), ensure_ascii=False).encode('utf-8')

        repaired, report = apply_to_tower(legacy_bundle, [])
        self.assertIsNotNone(repaired)
        phase = report['execution_phase_reconciliation']
        self.assertEqual(phase, {'terminal_running': 1, 'proposed': 1, 'applied': 1, 'conflicts': 0})
        self.assertEqual(_entity_from_bundle(repaired)['execution_phase'], 'COMPLETED')

        replayed, replay_report = apply_to_tower(repaired, [])
        self.assertEqual(replay_report['execution_phase_reconciliation']['proposed'], 0)
        self.assertEqual(replay_report['execution_phase_reconciliation']['applied'], 0)
        stable = replayed or repaired
        events = [entry['value'] for name, entry in read_live_tower_bytes(stable)['files'].items()
                  if name.startswith('events/')
                  and entry['value'].get('event_type') == 'TEST_EXECUTION_PHASE_RECONCILED']
        self.assertEqual(len(events), 1)

    def test_writer_maintenance_preserves_unproven_terminal_running_conflict(self):
        test = dict(self.test, status='DONE', state='DONE', verdict='INCONCLUSIVE',
                    executed_at=END, execution_phase='RUNNING')
        _save(self.root, f'entities/test/{TEST_ID}.json', test)
        raw = self._initial_bundle()

        changed, report = apply_to_tower(raw, [])
        after = changed or raw
        self.assertEqual(_entity_from_bundle(after)['execution_phase'], 'RUNNING')
        self.assertEqual(report['execution_phase_reconciliation']['proposed'], 0)
        self.assertEqual(report['execution_phase_reconciliation']['applied'], 0)
        self.assertEqual(report['execution_phase_reconciliation']['conflicts'], 1)

    def test_malformed_legacy_phase_evidence_fails_closed_without_blocking_independent_item(self):
        raw = self._successful_writer_bundle()
        with tempfile.TemporaryDirectory() as legacy_dir:
            root, _ = materialize_live_tower(raw, Path(legacy_dir) / 'legacy')
            test_path = entity_path(root, 'test', TEST_ID)
            test = json.loads(test_path.read_text(encoding='utf-8'))
            test['execution_phase'] = 'RUNNING'
            test_path.write_text(json.dumps(test), encoding='utf-8')
            battery_path = fs_path(root, evolution.BATTERIES_DOC)
            document = json.loads(battery_path.read_text(encoding='utf-8'))
            document['batteries'][0]['submitted_specs'][0]['test_id'] = []
            battery_path.write_text(json.dumps(document), encoding='utf-8')
            malformed = json.dumps(build_live_tower_payload(root), ensure_ascii=False).encode('utf-8')

        board = {'kind': 'BOARD_POST', 'source': 'ENGINEER', 'created_at': END,
                 '_inbox_name': 'independent-board.json',
                 'payload': {'to': 'GUARDIAO', 'text': 'Independent item survives phase conflict.'}}
        changed, report = apply_to_tower(malformed, [board])
        self.assertIsNotNone(changed)
        phase = report['execution_phase_reconciliation']
        self.assertEqual(phase['proposed'], 0)
        self.assertEqual(phase['applied'], 0)
        self.assertEqual(phase['error_type'], 'TypeError')
        self.assertEqual(_entity_from_bundle(changed)['execution_phase'], 'RUNNING')
        with tempfile.TemporaryDirectory() as readback_dir:
            readback, _ = materialize_live_tower(changed, Path(readback_dir) / 'readback')
            posts = json.loads(fs_path(readback, evolution.BOARD_DOC).read_text(encoding='utf-8'))['posts']
        self.assertEqual([post['text'] for post in posts], ['Independent item survives phase conflict.'])

    def test_malformed_binding_shape_fails_closed_at_writer_boundary(self):
        raw = self._successful_writer_bundle()
        with tempfile.TemporaryDirectory() as legacy_dir:
            root, _ = materialize_live_tower(raw, Path(legacy_dir) / 'legacy')
            test_path = entity_path(root, 'test', TEST_ID)
            test = json.loads(test_path.read_text(encoding='utf-8'))
            test.update(execution_phase='RUNNING', data_binding=[1])
            test_path.write_text(json.dumps(test), encoding='utf-8')
            malformed = json.dumps(build_live_tower_payload(root), ensure_ascii=False).encode('utf-8')

        board = {'kind': 'BOARD_POST', 'source': 'ENGINEER', 'created_at': END,
                 '_inbox_name': 'independent-binding-board.json',
                 'payload': {'to': 'GUARDIAO', 'text': 'Independent binding item survives.'}}
        changed, report = apply_to_tower(malformed, [board])
        self.assertIsNotNone(changed)
        phase = report['execution_phase_reconciliation']
        self.assertEqual(phase['error_type'], 'AttributeError')
        self.assertEqual(_entity_from_bundle(changed)['execution_phase'], 'RUNNING')
        with tempfile.TemporaryDirectory() as readback_dir:
            readback, _ = materialize_live_tower(changed, Path(readback_dir) / 'readback')
            posts = json.loads(fs_path(readback, evolution.BOARD_DOC).read_text(encoding='utf-8'))['posts']
        self.assertEqual([post['text'] for post in posts], ['Independent binding item survives.'])

    def test_partial_phase_failure_reports_zero_applied_after_rollback(self):
        raw = self._initial_bundle()
        planned = [
            {'request_id': 'REQ-PHASE-A', 'entity_kind': 'test', 'entity_name': TEST_ID,
             'expected_version': 1, 'writer_role': 'EXECUTOR',
             'event_type': 'TEST_EXECUTION_PHASE_RECONCILED', 'changes': {'execution_phase': 'COMPLETED'}},
            {'request_id': 'REQ-PHASE-B', 'entity_kind': 'test', 'entity_name': TEST_ID,
             'expected_version': 2, 'writer_role': 'EXECUTOR',
             'event_type': 'TEST_EXECUTION_PHASE_RECONCILED', 'changes': {'execution_phase': 'COMPLETED'}},
        ]
        fake_plan = {'summary': {'terminal_running': 2, 'conflict_count': 0}, 'requests': planned}
        from runtime.nexo_agent_api.tower_apply import apply_requests as real_apply_requests

        def partial(root, requests):
            if requests is planned:
                return [
                    {'request_id': 'REQ-PHASE-A', 'accepted': True, 'readback': 'PASS'},
                    {'request_id': 'REQ-PHASE-B', 'accepted': False,
                     'issue': {'code': 'EXECUTION_PHASE_RECONCILIATION_INVALID'}},
                ]
            return real_apply_requests(root, requests)

        with patch('runtime.nexo_agent_api.execution_phase_reconciliation.build_reconciliation_plan',
                   return_value=fake_plan), \
             patch('runtime.nexo_agent_api.gpt_writer.apply_requests', side_effect=partial):
            changed, report = apply_to_tower(raw, [])

        phase = report['execution_phase_reconciliation']
        self.assertEqual(phase['proposed'], 2)
        self.assertEqual(phase['applied'], 0)
        self.assertEqual(phase['rolled_back'], 1)
        self.assertTrue(all(receipt['rolled_back'] for receipt in report['receipts'][:2]))
        after = changed or raw
        self.assertEqual(_entity_from_bundle(after)['status'], 'READY')

    def test_legacy_battery_without_source_submission_remains_a_conflict(self):
        raw = self._successful_writer_bundle()
        with tempfile.TemporaryDirectory() as legacy_dir:
            root, _ = self._legacy_terminal_root(raw, Path(legacy_dir))
            report = build_reconciliation_plan(root)

        self.assertEqual(report['summary']['proposal_count'], 0)
        self.assertEqual(report['summary']['conflict_count'], 1)
        self.assertIn('BATTERY_ORIGINAL_SUBMISSION_PROOF_REQUIRED', report['conflicts'][0]['reasons'])

    def test_historical_source_proof_is_revalidated_and_writer_preserves_battery(self):
        raw = self._successful_writer_bundle()
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            root, battery_before = self._legacy_terminal_root(raw, base)
            repo = base / 'source'
            repo.mkdir()
            proof = self._source_proof(repo)
            with patch.object(integrity, '_trusted_source_git_root', return_value=repo):
                report = build_reconciliation_plan(root, submission_proofs={BATTERY_ID: proof})
                self.assertEqual(report['summary']['proposal_count'], 1, report['conflicts'])
                self.assertEqual(report['summary']['conflict_count'], 0)
                request = report['requests'][0]
                self.assertEqual(request['changes']['execution_phase'], 'COMPLETED')
                source_proof = request['changes']['execution_phase_reconciliation']['evidence']['source_submission_proof']
                self.assertEqual(source_proof['source_artifacts'][0]['repository'], 'TCC')
                current_bundle = json.dumps(build_live_tower_payload(root), ensure_ascii=False).encode('utf-8')
                applied, writer_report = _item(current_bundle, [request])

            self.assertFalse(writer_report['rejected'], writer_report)
            after = _entity_from_bundle(applied)
            self.assertEqual(after['execution_phase'], 'COMPLETED')
            self.assertIn('source_submission_proof', after['execution_phase_reconciliation']['evidence'])
            battery_after = read_live_tower_bytes(applied)['files'][evolution.BATTERIES_DOC]['value']
            self.assertEqual(battery_after, battery_before)
            with tempfile.TemporaryDirectory() as after_dir:
                after_root, _ = materialize_live_tower(applied, Path(after_dir) / 'applied')
                repeat = build_reconciliation_plan(after_root)
            self.assertEqual(repeat['summary']['proposal_count'], 0)

    def test_historical_proof_rejects_bad_identity_fingerprint_and_ambiguity(self):
        raw = self._successful_writer_bundle()
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            root, _ = self._legacy_terminal_root(raw, base)
            repo = base / 'source'
            repo.mkdir()
            proof = self._source_proof(repo)
            with patch.object(integrity, '_trusted_source_git_root', return_value=repo):
                wrong_identity = copy.deepcopy(proof)
                wrong_identity['battery_id'] = 'different-battery'
                report = build_reconciliation_plan(root, submission_proofs={BATTERY_ID: wrong_identity})
                self.assertIn('BATTERY_SOURCE_PROOF_IDENTITY_INVALID', report['conflicts'][0]['reasons'])

                wrong_fingerprint = copy.deepcopy(proof)
                wrong_fingerprint['submitted_specs'][0]['scientific_note']['fixture_scope'] = 'altered'
                report = build_reconciliation_plan(root, submission_proofs={BATTERY_ID: wrong_fingerprint})
                self.assertIn('BATTERY_SOURCE_PROOF_FINGERPRINT_MISMATCH', report['conflicts'][0]['reasons'])

                wrong_source_hash = copy.deepcopy(proof)
                wrong_source_hash['source_artifacts'][0]['source_sha256'] = '0' * 64
                report = build_reconciliation_plan(root, submission_proofs={BATTERY_ID: wrong_source_hash})
                self.assertIn('BATTERY_SOURCE_PROOF_BLOB_HASH_MISMATCH', report['conflicts'][0]['reasons'])

                ambiguous_locator = copy.deepcopy(proof)
                ambiguous_locator['source_artifacts'].append(copy.deepcopy(proof['source_artifacts'][0]))
                report = build_reconciliation_plan(root, submission_proofs={BATTERY_ID: ambiguous_locator})
                self.assertIn('BATTERY_SOURCE_PROOF_AMBIGUOUS', report['conflicts'][0]['reasons'])

            duplicate_repo = base / 'duplicate-source'
            duplicate_repo.mkdir()
            duplicate_proof = self._source_proof(duplicate_repo, duplicate_envelope=True)
            with patch.object(integrity, '_trusted_source_git_root', return_value=duplicate_repo):
                report = build_reconciliation_plan(root, submission_proofs={BATTERY_ID: duplicate_proof})
            self.assertIn('BATTERY_SOURCE_PROOF_ENVELOPE_NOT_UNIQUE', report['conflicts'][0]['reasons'])

    def test_source_ref_removed_after_dry_run_denies_writer_reconciliation(self):
        raw = self._successful_writer_bundle()
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            root, _ = self._legacy_terminal_root(raw, base)
            repo = base / 'source'
            repo.mkdir()
            proof = self._source_proof(repo)
            with patch.object(integrity, '_trusted_source_git_root', return_value=repo):
                plan = build_reconciliation_plan(root, submission_proofs={BATTERY_ID: proof})
                self.assertEqual(plan['summary']['proposal_count'], 1, plan['conflicts'])
                current_bundle = json.dumps(build_live_tower_payload(root), ensure_ascii=False).encode('utf-8')
                subprocess.run(['git', '-C', str(repo), 'update-ref', '-d',
                                'refs/remotes/origin/nexo-inbox'], check=True, capture_output=True)
                unchanged, writer_report = _item(current_bundle, [plan['requests'][0]])

        self.assertTrue(writer_report['rejected'], writer_report)
        self.assertEqual(_entity_from_bundle(unchanged)['execution_phase'], 'RUNNING')

    def test_submission_fingerprint_and_evidence_are_revalidated(self):
        raw = self._successful_writer_bundle()
        with tempfile.TemporaryDirectory() as legacy_dir:
            root, _ = materialize_live_tower(raw, Path(legacy_dir) / 'legacy')
            test_path = entity_path(root, 'test', TEST_ID)
            test = json.loads(test_path.read_text(encoding='utf-8'))
            test['execution_phase'] = 'RUNNING'
            test_path.write_text(json.dumps(test), encoding='utf-8')
            battery_path = fs_path(root, evolution.BATTERIES_DOC)
            document = json.loads(battery_path.read_text(encoding='utf-8'))
            document['batteries'][0]['submitted_specs'][0]['scientific_note']['fixture_scope'] = 'changed'
            battery_path.write_text(json.dumps(document), encoding='utf-8')
            mismatch = build_reconciliation_plan(root)
            self.assertEqual(mismatch['summary']['proposal_count'], 0)
            self.assertIn('BATTERY_SUBMISSION_FINGERPRINT_MISMATCH', mismatch['conflicts'][0]['reasons'])

            document['batteries'][0]['submitted_specs'][0]['scientific_note']['fixture_scope'] = 'synthetic'
            battery_path.write_text(json.dumps(document), encoding='utf-8')
            plan = build_reconciliation_plan(root)
            self.assertEqual(plan['summary']['proposal_count'], 1, plan['conflicts'])
            request = plan['requests'][0]

            # The entity version has not changed, but the battery proof has.
            document['batteries'][0]['conclusion'] = 'failure'
            battery_path.write_text(json.dumps(document), encoding='utf-8')
            concurrent_bundle = json.dumps(build_live_tower_payload(root), ensure_ascii=False).encode('utf-8')

        unchanged, report = _item(concurrent_bundle, [request])
        self.assertEqual(report['rejected'][0]['reason']['code'], 'EXECUTION_PHASE_RECONCILIATION_INVALID')
        self.assertEqual(_entity_from_bundle(unchanged)['execution_phase'], 'RUNNING')

    def test_done_without_terminal_attempt_proof_is_a_conflict(self):
        test = dict(self.test, status='DONE', state='DONE', verdict='INCONCLUSIVE',
                    executed_at=END, execution_phase='RUNNING')
        _save(self.root, f'entities/test/{TEST_ID}.json', test)
        report = build_reconciliation_plan(self.root)
        self.assertEqual(report['summary']['proposal_count'], 0)
        self.assertEqual(report['summary']['conflict_count'], 1)
        self.assertIn('BATTERY_ID_REQUIRED', report['conflicts'][0]['reasons'])

    def test_protected_camb_mcmc_scope_is_never_proposed(self):
        raw = self._successful_writer_bundle()
        with tempfile.TemporaryDirectory() as legacy_dir:
            root, _ = materialize_live_tower(raw, Path(legacy_dir) / 'legacy')
            test = integrity.entity(root, TEST_ID)
            test.update(domain='COSMOLOGY', execution_phase='RUNNING')
            path = entity_path(root, 'test', TEST_ID)
            path.write_text(json.dumps(test), encoding='utf-8')
            report = build_reconciliation_plan(root)
        self.assertEqual(report['summary']['proposal_count'], 0)
        self.assertEqual(report['summary']['protected_camb_mcmc_count'], 1)
        self.assertIn('PROTECTED_CAMB_MCMC_SCOPE', report['conflicts'][0]['reasons'])

    def test_stale_entity_version_cannot_apply_reconciliation(self):
        raw = self._successful_writer_bundle()
        with tempfile.TemporaryDirectory() as legacy_dir:
            root, _ = materialize_live_tower(raw, Path(legacy_dir) / 'legacy')
            path = entity_path(root, 'test', TEST_ID)
            test = json.loads(path.read_text(encoding='utf-8'))
            test['execution_phase'] = 'RUNNING'
            path.write_text(json.dumps(test), encoding='utf-8')
            plan = build_reconciliation_plan(root)
            self.assertEqual(plan['summary']['proposal_count'], 1, plan['conflicts'])
            request = plan['requests'][0]
            test['entity_version'] += 1  # concurrent Writer mutation after planning
            path.write_text(json.dumps(test), encoding='utf-8')
            concurrent_bundle = json.dumps(build_live_tower_payload(root), ensure_ascii=False).encode('utf-8')

        unchanged, report = _item(concurrent_bundle, [request])
        self.assertEqual(report['rejected'][0]['reason']['code'],
                         'EXECUTION_PHASE_RECONCILIATION_INVALID')
        self.assertEqual(_entity_from_bundle(unchanged)['execution_phase'], 'RUNNING')


if __name__ == '__main__':
    unittest.main()
