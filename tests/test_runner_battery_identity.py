"""Synthetic runner observations: ordering is not an execution identity."""
from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from runtime.nexo_agent_api import operation_receipts as receipts
from runtime.nexo_agent_api.gpt_writer import _runner_battery_updates, apply_to_tower
from runtime.nexo_agent_api.inbox_apply import ProposalError
from runtime.nexo_agent_api.live_tower import build_live_tower_payload


class RunnerBatteryIdentityTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        (self.root / 'CONTROL.json').write_text(json.dumps({
            'mode': 'ACTIVE', 'truth_owner': 'TOWER_V06@GOOGLE_DRIVE_PRIVATE'}))
        self.update = {'kind': 'BATTERY_STATUS', 'source': 'WRITER_ROBOT', 'payload': {
            'battery_id': 'bat-synthetic', 'status': 'DONE', 'run_ref': 'actions/runs/123',
            'completed_at': '2026-01-01T00:02:00Z', 'conclusion': 'success', 'results': [{
                'test_id': 'TEST-SYNTHETIC', 'attempt_id': 'attempt-1',
                'started_at': '2026-01-01T00:01:00Z', 'executed_at': '2026-01-01T00:02:00Z',
                'ok': True, 'result': {'value': 1}}]}}

    def load(self, updates):
        path = self.root / 'updates.json'
        path.write_text(json.dumps(updates))
        return _runner_battery_updates(str(path))

    def raw(self):
        # The collector file is not part of the canonical Tower snapshot.
        (self.root / 'updates.json').unlink(missing_ok=True)
        return json.dumps(build_live_tower_payload(self.root)).encode()

    def seed(self, item, *, outcome='DEFERRED_DEPENDENCY', condition='SOURCE_REVISION_CHANGED',
             legacy=True, envelope=True, position=19):
        intent = f'runner:battery:{position}:bat-synthetic' if legacy else item['_inbox_id']
        source = receipts.dependency_context_revision(self.root, item)
        row = receipts.build_receipt(
            intent=intent, payload_sha256=receipts.payload_hash(item, trusted_transport=True),
            effect=(receipts.envelope_effect_id(intent) if envelope else
                    receipts.effect_id({}, intent=intent, index=0)), outcome=outcome,
            source_revision=source, result_revision=source,
            reason_code='BATTERY_NOT_FOUND' if outcome == 'DEFERRED_DEPENDENCY' else 'SYNTHETIC_REASON',
            retry_condition={'kind': condition, 'source_revision': source}
            if outcome in {'DEFERRED_DEPENDENCY', 'RETRYABLE_TRANSPORT'} else None)
        receipts.persist_receipt(self.root, row)
        return row

    def test_outer_reorder_insertion_and_duplicates_keep_identity(self):
        other = copy.deepcopy(self.update)
        other['payload']['battery_id'] = 'bat-other'
        first = self.load([self.update])[0]
        shuffled = self.load([other, self.update, self.update])
        self.assertEqual(first['_inbox_id'], shuffled[1]['_inbox_id'])
        self.assertEqual(first['_inbox_name'], shuffled[1]['_inbox_name'])
        self.assertEqual(first['_inbox_id'], shuffled[2]['_inbox_id'])
        self.assertNotEqual(first['_inbox_id'], shuffled[0]['_inbox_id'])
        self.assertEqual(receipts.payload_hash(first, trusted_transport=True),
                         receipts.payload_hash(shuffled[1], trusted_transport=True))

    def test_distinct_run_attempt_artifact_and_phase_remain_distinct(self):
        original = self.load([self.update])[0]['_inbox_id']
        for key, value in [('run_ref', 'actions/runs/124'), ('run_attempt', 2),
                           ('artifact_id', 42), ('completed_at', '2026-01-01T00:03:00Z'),
                           ('status', 'RUNNING')]:
            with self.subTest(key=key):
                update = copy.deepcopy(self.update)
                update['payload'][key] = value
                self.assertNotEqual(original, self.load([update])[0]['_inbox_id'])
        update = copy.deepcopy(self.update)
        update['payload']['results'][0]['attempt_id'] = 'attempt-2'
        self.assertNotEqual(original, self.load([update])[0]['_inbox_id'])

    def test_changed_result_bytes_do_not_mint_identity(self):
        changed = copy.deepcopy(self.update)
        changed['payload']['results'][0]['result']['value'] = 999
        first, second = self.load([self.update, changed])
        self.assertEqual(first['_inbox_id'], second['_inbox_id'])
        self.assertNotEqual(receipts.payload_hash(first, trusted_transport=True),
                            receipts.payload_hash(second, trusted_transport=True))

    def test_duplicate_and_reordered_deferred_observation_does_not_retry(self):
        item = self.load([self.update])[0]
        with patch('runtime.nexo_agent_api.gpt_writer.proposal_to_requests',
                   side_effect=ProposalError('BATTERY_NOT_FOUND')) as convert:
            packed, first = apply_to_tower(self.raw(), [item, item])
            self.assertEqual(convert.call_count, 1)
            self.assertIsNotNone(packed)
            other = copy.deepcopy(self.update)
            other['payload']['battery_id'] = 'bat-other'
            reordered = self.load([other, self.update])[1]
            second, report = apply_to_tower(packed, [reordered])
            self.assertEqual(convert.call_count, 1)
            self.assertIsNone(second)
            self.assertEqual(report['deferred'][0]['outcome'], 'DEFERRED_DEPENDENCY')

    def test_legacy_envelope_and_conversion_receipts_are_bound_once(self):
        for envelope in (True, False):
            with self.subTest(envelope=envelope):
                item = self.load([self.update])[0]
                prior = self.seed(item, envelope=envelope)
                with patch('runtime.nexo_agent_api.gpt_writer.proposal_to_requests') as convert:
                    packed, report = apply_to_tower(self.raw(), [item])
                    convert.assert_not_called()
                    self.assertIsNotNone(packed)
                    [row] = report['operation_receipts']
                    self.assertEqual(row['supersedes'], prior['receipt_id'])
                    self.assertEqual(row['retry_condition'], prior['retry_condition'])
                    self.assertEqual(row['source_revision'], prior['source_revision'])
                    self.assertEqual(row['occurred_at'], prior['occurred_at'])
                    second, report = apply_to_tower(packed, [item])
                    convert.assert_not_called()
                    self.assertIsNone(second)

    def test_changed_dependency_retries_migrated_observation(self):
        item = self.load([self.update])[0]
        self.seed(item)
        directory = self.root / 'evolution'
        directory.mkdir()
        (directory / 'batteries.json').write_text(json.dumps({'batteries': []}))
        with patch('runtime.nexo_agent_api.gpt_writer.proposal_to_requests',
                   side_effect=ProposalError('BATTERY_NOT_FOUND')) as convert:
            packed, report = apply_to_tower(self.raw(), [item])
            convert.assert_called_once()
            self.assertIsNotNone(packed)
            self.assertEqual(report['operation_receipts'][-1]['outcome'], 'DEFERRED_DEPENDENCY')

    def test_legacy_applied_and_terminal_receipts_do_not_reexecute(self):
        item = self.load([self.update])[0]
        for outcome in ('APPLIED', 'REJECTED_TERMINAL'):
            with self.subTest(outcome=outcome):
                self.seed(item, outcome=outcome)
                with patch('runtime.nexo_agent_api.gpt_writer.proposal_to_requests') as convert:
                    packed, report = apply_to_tower(self.raw(), [item])
                    convert.assert_not_called()
                    self.assertTrue(report['handled'])
                    self.assertEqual(report['operation_receipts'][0]['outcome'],
                                     'ALREADY_APPLIED' if outcome == 'APPLIED' else outcome)

    def test_terminal_guard_survives_migration_and_changed_payload(self):
        item = self.load([self.update])[0]
        self.seed(item, outcome='REJECTED_TERMINAL')
        packed, _ = apply_to_tower(self.raw(), [item])
        changed = copy.deepcopy(self.update)
        changed['payload']['results'][0]['result']['value'] = 999
        with patch('runtime.nexo_agent_api.gpt_writer.proposal_to_requests') as convert:
            _, report = apply_to_tower(packed, self.load([changed]))
            convert.assert_not_called()
            self.assertEqual(report['rejected'][0]['reason'], 'TERMINAL_PAYLOAD_CHANGED_WITHOUT_NEW_IDENTITY')

    def test_new_attempt_is_not_suppressed_by_legacy_receipt(self):
        item = self.load([self.update])[0]
        self.seed(item, outcome='REJECTED_TERMINAL')
        changed = copy.deepcopy(self.update)
        changed['payload']['results'][0]['attempt_id'] = 'attempt-2'
        with patch('runtime.nexo_agent_api.gpt_writer.proposal_to_requests',
                   side_effect=ProposalError('BATTERY_NOT_FOUND')) as convert:
            _, report = apply_to_tower(self.raw(), self.load([changed]))
            convert.assert_called_once()
            self.assertFalse(report['rejected'])

    def test_transport_recovery_policy_is_preserved(self):
        item = self.load([self.update])[0]
        for condition, expected in [('AFTER_TRANSPORT_RECOVERY', 1), ('OPERATOR_REAUTHORIZATION', 0),
                                    ('RECONCILE_TOWER_BEFORE_REAPPLY', 0)]:
            with self.subTest(condition=condition):
                for path in (self.root / 'operations' / 'receipts').glob('*.json'):
                    path.unlink()
                self.seed(item, outcome='RETRYABLE_TRANSPORT', condition=condition)
                with patch('runtime.nexo_agent_api.gpt_writer.proposal_to_requests',
                           side_effect=ProposalError('BATTERY_NOT_FOUND')) as convert:
                    apply_to_tower(self.raw(), [item])
                    self.assertEqual(convert.call_count, expected)

    def test_malformed_results_do_not_abort_following_observations(self):
        for results in (1, True, {}, 'bad', None):
            with self.subTest(results=results):
                malformed = copy.deepcopy(self.update)
                malformed['payload']['results'] = results
                loaded = self.load([malformed, self.update])
                self.assertEqual(len(loaded), 1)
                self.assertEqual(loaded[0]['payload'], self.update['payload'])

    def test_missing_and_nonfinite_source_metadata_is_conservative(self):
        missing = {'kind': 'BATTERY_STATUS', 'source': 'WRITER_ROBOT',
                   'payload': {'battery_id': 'bat-synthetic', 'status': 'DONE'}}
        changed = copy.deepcopy(missing)
        changed['payload']['conclusion'] = 'different'
        first, second = self.load([missing, changed])
        self.assertEqual(first['_inbox_id'], second['_inbox_id'])
        nonfinite = copy.deepcopy(self.update)
        nonfinite['payload']['run_attempt'] = float('nan')
        self.assertEqual(len(self.load([nonfinite, self.update])), 1)

    def test_real_legacy_writer_roundtrip_preserves_terminal_receipt(self):
        item = self.load([self.update])[0]
        legacy = {**item, '_inbox_id': 'runner:battery:19:bat-synthetic',
                  '_inbox_name': 'battery-update-19-bat-synthetic'}
        packed, first = apply_to_tower(self.raw(), [legacy])
        self.assertEqual(first['operation_receipts'][-1]['outcome'], 'REJECTED_TERMINAL')
        migrated, report = apply_to_tower(packed, [item])
        self.assertEqual(report['receipts'], [])
        self.assertEqual(report['operation_receipts'][0]['supersedes'],
                         first['operation_receipts'][-1]['receipt_id'])
        second, report = apply_to_tower(migrated, [item])
        self.assertIsNone(second)
        self.assertEqual(report['receipts'], [])

    def test_wrong_origin_and_extra_fields_are_not_collector_observations(self):
        wrong = {**self.update, 'source': 'CHATGPT'}
        forged = {**self.update, '_inbox_id': 'forged'}
        self.assertEqual(self.load([wrong, forged]), [])


if __name__ == '__main__':
    unittest.main()
