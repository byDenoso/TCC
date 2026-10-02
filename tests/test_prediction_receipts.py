"""Prospective receipt/CAS tests over isolated local records, never live data."""
import copy
import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from runtime.nexo_agent_api import prediction_receipts as receipts
from runtime.nexo_agent_api.gpt_writer import apply_to_tower
from runtime.nexo_agent_api.live_tower import build_live_tower_payload, read_live_tower_bytes
from runtime.nexo_agent_api.public_projection import _public_prereg, build_public_projection
from runtime.nexo_agent_api.inbox_apply import proposal_to_requests
from runtime.nexo_agent_api.tower_apply import apply_requests
from runtime.nexo_agent_api.tower_paths import entity_path
from tests.test_scientific_integrity import fixture, save

OBSERVED = datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)


class PredictionReceiptTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        save(self.root, 'CONTROL.json', {'mode': 'ACTIVE', 'truth_owner': 'TOWER_V06@GOOGLE_DRIVE_PRIVATE'})
        self.test = fixture('TEST-PRED')
        self.test.update(status='DRAFT', state='DRAFT')
        self.put(self.test)

    def tearDown(self):
        self.tmp.cleanup()

    def put(self, test):
        save(self.root, entity_path(self.root, 'test', test['id']).relative_to(self.root).as_posix(), test)

    def current(self):
        return json.loads(entity_path(self.root, 'test', 'TEST-PRED').read_text())

    def mutate(self, changes, version=None):
        current = self.current()
        request = {'request_id': 'REQ-PRED-' + str(current['entity_version']), 'entity_kind': 'test', 'entity_name': 'TEST-PRED',
                   'expected_version': current['entity_version'] if version is None else version,
                   'writer_role': 'ADVISOR', 'event_type': 'TEST_ENRICHED', 'changes': changes}
        with patch.object(receipts, 'datetime') as clock, redirect_stderr(io.StringIO()):
            clock.now.return_value = OBSERVED
            return apply_requests(self.root, [request])[0]

    def prediction(self):
        return {'p_promoted': .7, 'expected_effect': 'Frozen forecast'}

    def test_receipt_uses_writer_clock_not_supplied_dates(self):
        prediction = {**self.prediction(), 'recorded_at': '2000-01-01T00:00:00Z'}
        self.assertTrue(self.mutate({'prediction': prediction})['accepted'])
        test = self.current(); receipt = test['prediction_receipt']
        self.assertEqual(receipt['received_at'], '2026-10-01T12:00:00Z')
        self.assertEqual(receipt['prediction_hash'], receipts.prediction_hash('TEST-PRED', prediction))
        self.assertEqual(receipt['classification'], 'PROSPECTIVE')
        self.assertEqual(_public_prereg(test)['prediction']['recorded_at'], receipt['received_at'])

    def test_receipt_exact_replay_preserves_first_observation(self):
        self.mutate({'prediction': self.prediction()})
        original = self.current()['prediction_receipt']
        self.assertTrue(self.mutate({'prediction': self.prediction()})['accepted'])
        self.assertEqual(self.current()['prediction_receipt'], original)

    def test_registered_prediction_cannot_be_revised(self):
        self.mutate({'prediction': self.prediction()})
        before = self.current()
        result = self.mutate({'prediction': {**self.prediction(), 'p_promoted': .9}})
        self.assertFalse(result['accepted'])
        self.assertEqual(result['issue']['code'], 'RECORDED_PREDICTION_IMMUTABLE')
        self.assertEqual(self.current(), before)

    def test_python_numeric_equality_cannot_change_committed_json(self):
        self.mutate({'prediction': {'p_promoted': 1}})
        original = self.current()
        for value in (1.0, True):
            with self.subTest(value=value):
                result = self.mutate({'prediction': {'p_promoted': value}})
                self.assertFalse(result['accepted'])
                self.assertEqual(self.current(), original)
        self.assertIn('recorded_at', _public_prereg(self.current())['prediction'])

    def test_caller_cannot_forge_or_backdate_receipt(self):
        result = self.mutate({'prediction': self.prediction(), 'prediction_receipt': {'received_at': '2000-01-01T00:00:00Z'}})
        self.assertFalse(result['accepted'])
        self.assertEqual(result['issue']['code'], 'PREDICTION_RECEIPT_WRITER_OWNED')
        self.assertNotIn('prediction_receipt', self.current())

    def test_legacy_prediction_is_not_backfilled_by_unrelated_mutation(self):
        self.test['prediction'] = self.prediction(); self.put(self.test)
        self.mutate({'semantic': {'question_plain': 'Existing question'}})
        self.assertNotIn('prediction_receipt', self.current())
        self.assertNotIn('recorded_at', _public_prereg(self.current())['prediction'])

    def test_prediction_supplied_with_result_is_retrospective(self):
        for status in ('DRAFT', 'READY'):
            with self.subTest(status=status):
                self.put({**self.test, 'status': status, 'state': status})
                item = {
                    'kind': 'MUTATION_PROPOSAL',
                    'created_at': '2026-10-01T11:00:00Z',
                    '_inbox_name': f'prediction-with-result-{status}.json',
                    'payload': {
                        'test_id': 'TEST-PRED',
                        'prediction': self.prediction(),
                        'result': {'verdict': 'INCONCLUSIVE', 'summary': 'Retrospective fixture result.'},
                    },
                }
                requests = proposal_to_requests(item, self.root)
                self.assertEqual(requests[0]['event_type'], 'TEST_RESULT_RECORDED')
                with patch.object(receipts, 'datetime') as clock, redirect_stderr(io.StringIO()):
                    clock.now.return_value = OBSERVED
                    applied = apply_requests(self.root, requests)[0]
                self.assertTrue(applied['accepted'], applied)
                test = self.current()
                self.assertEqual(test['executed_at'], '2026-10-01T11:00:00Z')
                self.assertEqual(test['verdict'], 'INCONCLUSIVE')
                self.assertEqual(test['prediction_receipt']['classification'], 'AFTER_EXECUTION_OR_RESERVATION')
                self.assertNotIn('recorded_at', _public_prereg(test)['prediction'])

    def test_prediction_after_reservation_is_not_prospective(self):
        self.test.update(status='QUEUED', state='QUEUED'); self.put(self.test)
        self.assertTrue(self.mutate({'prediction': self.prediction()})['accepted'])
        self.assertEqual(self.current()['prediction_receipt']['classification'], 'AFTER_EXECUTION_OR_RESERVATION')
        self.assertNotIn('recorded_at', _public_prereg(self.current())['prediction'])

    def test_same_mutation_cannot_hide_previous_reservation_or_legacy_state(self):
        self.test.update(status='QUEUED', state='QUEUED'); self.put(self.test)
        refused = self.mutate({'status': 'DRAFT', 'state': 'DRAFT', 'prediction': self.prediction()})
        self.assertFalse(refused['accepted'])
        self.assertEqual(refused['issue']['code'], 'EXECUTION_PHASE_TRANSITION_REQUIRED')
        self.assertEqual(self.current()['status'], 'QUEUED')
        self.assertNotIn('prediction', self.current())
        self.assertTrue(self.mutate({'prediction': self.prediction()})['accepted'])
        self.assertEqual(self.current()['prediction_receipt']['classification'], 'AFTER_EXECUTION_OR_RESERVATION')
        legacy = fixture('TEST-PRED-LEGACY-RUNNING')
        legacy.update(status='DRAFT', state='RUNNING')
        self.put(legacy)
        request = {
            'request_id': 'REQ-PRED-LEGACY-RUNNING',
            'entity_kind': 'test',
            'entity_name': legacy['id'],
            'expected_version': legacy['entity_version'],
            'writer_role': 'ADVISOR',
            'event_type': 'TEST_ENRICHED',
            'changes': {'prediction': self.prediction()},
        }
        with patch.object(receipts, 'datetime') as clock, redirect_stderr(io.StringIO()):
            clock.now.return_value = OBSERVED
            applied = apply_requests(self.root, [request])[0]
        self.assertTrue(applied['accepted'], applied)
        legacy_after = json.loads(entity_path(self.root, 'test', legacy['id']).read_text())
        self.assertEqual(legacy_after['prediction_receipt']['classification'], 'AFTER_EXECUTION_OR_RESERVATION')

    def test_ready_retry_with_prior_attempt_is_not_a_new_prospective_observation(self):
        self.test.update(attempt_id='earlier-attempt', battery_id='finished-battery')
        self.put(self.test)
        self.assertTrue(self.mutate({'prediction': self.prediction()})['accepted'])
        self.assertEqual(self.current()['prediction_receipt']['classification'], 'AFTER_EXECUTION_OR_RESERVATION')

    def test_finished_registry_reservation_is_not_forgotten_when_test_fields_are_absent(self):
        save(self.root, 'evolution/batteries.json', {'batteries': [{'id': 'previous', 'status': 'DONE', 'tests': [{'test_id': 'TEST-PRED'}]}]})
        self.assertTrue(self.mutate({'prediction': self.prediction()})['accepted'])
        self.assertEqual(self.current()['prediction_receipt']['classification'], 'AFTER_EXECUTION_OR_RESERVATION')

    def test_terminal_test_can_record_late_forecast_without_temporal_claim(self):
        self.test.update(status='DONE', state='DONE', verdict='INCONCLUSIVE', executed_at='2026-09-30T10:00:00Z'); self.put(self.test)
        self.assertTrue(self.mutate({'prediction': self.prediction()})['accepted'])
        self.assertNotIn('recorded_at', _public_prereg(self.current())['prediction'])

    def test_tampered_prediction_and_other_test_identity_do_not_verify(self):
        self.mutate({'prediction': self.prediction()}); test = self.current()
        self.assertIsNone(receipts.public_receipt('OTHER', test['prediction'], test['prediction_receipt']))
        test['prediction']['p_promoted'] = .9
        self.assertNotIn('recorded_at', _public_prereg(test)['prediction'])

    def test_public_receipt_has_only_small_allowlisted_metadata(self):
        self.mutate({'prediction': self.prediction()}); test = self.current()
        test['prediction_receipt']['private_inbox_ref'] = 'must-not-leak'
        public = _public_prereg(test)['prediction']
        self.assertEqual(set(public), {'p_promoted', 'expected_effect', 'recorded_at', 'receipt_contract', 'prediction_hash'})
        self.assertNotIn('must-not-leak', json.dumps(public))

    def test_complete_projection_carries_receipt_without_changing_scientific_hash(self):
        original_hash = self.current()['prereg_hash']
        self.mutate({'prediction': self.prediction()})
        projection = build_public_projection(self.root, tower_revision='sha256:' + 'a' * 64)
        self.assertEqual(projection['tests'][0]['prereg']['prediction']['recorded_at'], '2026-10-01T12:00:00Z')
        self.assertEqual(self.current()['prereg_hash'], original_hash)

    def test_later_import_of_earlier_execution_cannot_become_prospective(self):
        self.mutate({'prediction': self.prediction()})
        test = self.current(); test['executed_at'] = '2026-10-01T11:00:00Z'
        self.assertNotIn('recorded_at', _public_prereg(test)['prediction'])
        test['executed_at'] = '2026-10-01T13:00:00Z'
        self.assertIn('recorded_at', _public_prereg(test)['prediction'])

    def test_invalid_probabilities_do_not_get_receipts(self):
        for value in (True, -1, 1.1, float('nan'), float('inf'), '0.5', 10**400):
            with self.subTest(value=value):
                result = self.mutate({'prediction': {'p_promoted': value}})
                self.assertFalse(result['accepted'])
                self.assertNotIn('prediction_receipt', self.current())

    def test_cas_conflict_cannot_replace_prediction_or_receipt(self):
        before = self.current()
        result = self.mutate({'prediction': self.prediction()}, version=0)
        self.assertFalse(result['accepted'])
        self.assertEqual(self.current(), before)

    def test_nonfinite_nested_payload_is_a_structured_rejection(self):
        result = self.mutate({'prediction': {**self.prediction(), 'extra': {'value': float('nan')}}})
        self.assertFalse(result['accepted'])
        self.assertEqual(result['issue']['code'], 'PREDICTION_PAYLOAD_NOT_CANONICAL_JSON')
        self.assertNotIn('prediction_receipt', self.current())

    def test_outbox_result_import_cannot_get_receipt_from_temporary_registration(self):
        raw = json.dumps(build_live_tower_payload(self.root)).encode()
        item = {'kind': 'MUTATION_PROPOSAL', '_inbox_name': 'late-result', 'created_at': '2026-09-30T10:00:00Z',
                'payload': {'test_id': 'META-IMPORTED', 'prediction': self.prediction(),
                            'result': {'verdict': 'INCONCLUSIVE', 'summary': 'Historical import'}}}
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            output, report = apply_to_tower(raw, [item])
        self.assertFalse(report['rejected'], report)
        files = read_live_tower_bytes(output)['files']
        test = files['entities/test/META-IMPORTED.json']['value']
        self.assertEqual(test['prediction_receipt']['classification'], 'AFTER_EXECUTION_OR_RESERVATION')
        self.assertNotIn('recorded_at', _public_prereg(test)['prediction'])


if __name__ == '__main__':
    unittest.main()
