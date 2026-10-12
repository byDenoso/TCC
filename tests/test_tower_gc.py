"""GC must retain evidence and rehearse recovery without canonical writes."""
import copy
import hashlib
import io
import json
import os
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from runtime.nexo_agent_api import tower_gc as gc
from runtime.nexo_agent_api import tower_gc_cli
from runtime.nexo_agent_api.gpt_writer import _run_optional_gc
from runtime.nexo_agent_api.live_tower import build_live_tower_payload, materialize_live_tower, verify_live_tower


def encode(bundle):
    bundle = copy.deepcopy(bundle)
    raw = json.dumps(bundle['files'], ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()
    revision = 'sha256:' + hashlib.sha256(raw).hexdigest()
    bundle.update(file_count=len(bundle['files']), revision=revision, state_fingerprint=revision)
    return json.dumps(bundle, ensure_ascii=False, sort_keys=True, indent=2).encode() + b'\n'


def snapshot():
    with tempfile.TemporaryDirectory() as work:
        root = Path(work)
        (root / 'CONTROL.json').write_text(json.dumps({'truth_owner': 'TOWER_V06@GOOGLE_DRIVE_PRIVATE'}))
        bundle = build_live_tower_payload(root, updated_at='2026-10-12T00:00:00Z')
    entries = {
        'entities/test/TEST::A.json': {'id': 'TEST::A', 'artifact': 'artifacts/data.json', 'result': [1.2, 3.4]},
        'artifacts/data.json': {'bytes': 'frozen'},
        'authorizations/revoked.json': {'state': 'REVOKED'},
        'events/a.json': {'to': 'events/b.json'},
        'events/b.json': {'to': 'events/a.json'},
        'cache/a.json': {'derived': True, 'text': 'same' * 300},
        'cache/b.json': {'derived': True, 'text': 'same' * 300},
        'cache/c.json': {'derived': True},
        'events/uses-cache.json': {'ref': 'cache/c.json'},
        'unknown/new.json': {'ref': 'TEST::MISSING'},
    }
    bundle['files'].update({path: {'encoding': 'json', 'value': value} for path, value in entries.items()})
    return encode(bundle)


class TowerGCTests(unittest.TestCase):
    def setUp(self):
        self.raw = snapshot()
        self.bundle = json.loads(self.raw)

    def test_dry_run_is_deterministic_and_retains_all_science_authority_unknowns(self):
        first = gc.plan_gc(self.raw)
        self.assertEqual(first, gc.plan_gc(self.raw))
        rows = {row['path']: row for row in first['items']}
        self.assertEqual(rows['entities/test/TEST::A.json']['class'], 'KEEP_SCIENCE')
        self.assertEqual(rows['authorizations/revoked.json']['class'], 'KEEP_AUTHORITY')
        self.assertEqual(rows['unknown/new.json']['class'], 'UNRESOLVED_REF')
        self.assertTrue(rows['unknown/new.json']['reasons'])
        self.assertEqual(rows['cache/c.json']['class'], 'KEEP_ACTIVE_OR_AUDIT')
        self.assertFalse(any(row['eligible_for_removal'] for row in first['items']))
        self.assertEqual(self.raw, snapshot())

    def test_cycles_key_references_aliases_and_unknown_consumers_are_retained(self):
        self.bundle['files']['entities/work/W.json'] = {'encoding': 'json', 'value': {'cache/a.json': True, 'ref': 'TEST::A#part'}}
        plan = gc.plan_gc(encode(self.bundle))
        rows = {row['path']: row for row in plan['items']}
        self.assertEqual(rows['cache/a.json']['class'], 'KEEP_ACTIVE_OR_AUDIT')
        self.assertIn('entities/test/TEST::A.json', rows['entities/work/W.json']['refs'])
        self.assertIn('events/b.json', rows['events/a.json']['refs'])
        self.assertEqual(plan['summary']['consumer_coverage'], 'UNVERIFIED')

    def test_archive_shares_bytes_but_restores_every_identity(self):
        selected = ['cache/a.json', 'cache/b.json', 'entities/test/TEST::A.json']
        packed, receipt = gc.prepare_archive(self.raw, selected)
        actual = gc.verify_archive(packed, receipt)
        self.assertEqual(set(actual), set(selected))
        self.assertEqual(actual, {p: self.bundle['files'][p] for p in selected})
        self.assertLess(receipt['unique_entry_bytes'], receipt['original_entry_bytes'])
        self.assertEqual((packed, receipt), gc.prepare_archive(self.raw, selected[::-1]))
        with zipfile.ZipFile(io.BytesIO(packed)) as archive:
            self.assertEqual(len([n for n in archive.namelist() if n.startswith('blobs/')]), 2)

    def test_archive_hash_collision_is_never_deduplicated(self):
        with patch.object(gc, '_hash', return_value='sha256:' + 'a' * 64):
            with self.assertRaisesRegex(gc.TowerGCError, 'HASH_COLLISION'):
                gc.prepare_archive(self.raw, ['cache/a.json', 'entities/test/TEST::A.json'])

    def test_archive_corruption_missing_member_and_tampered_manifest_fail_closed(self):
        packed, receipt = gc.prepare_archive(self.raw, ['cache/a.json'])
        with self.assertRaises(gc.TowerGCError):
            gc.verify_archive(packed[:-20], receipt)
        forged = copy.deepcopy(receipt)
        forged['items'][0]['path'] = 'entities/test/TEST::A.json'
        with self.assertRaisesRegex(gc.TowerGCError, 'MANIFEST_MISMATCH'):
            gc.verify_archive(packed, forged)
        removed = io.BytesIO()
        with zipfile.ZipFile(io.BytesIO(packed)) as source, zipfile.ZipFile(removed, 'w') as dest:
            dest.writestr('manifest.json', source.read('manifest.json'))
        forged = {**receipt, 'archive_bytes': len(removed.getvalue()), 'archive_sha256': gc._hash(removed.getvalue())}
        with self.assertRaises(gc.TowerGCError):
            gc.verify_archive(removed.getvalue(), forged)

    def test_exact_backup_roundtrip_and_truncation_detection(self):
        packed, receipt = gc.prepare_backup(self.raw)
        self.assertEqual(gc.restore_backup(packed, receipt), self.raw)
        self.assertEqual(gc.prepare_backup(self.raw), (packed, receipt))
        with self.assertRaises(gc.TowerGCError):
            gc.restore_backup(packed[:-1], receipt)

    def test_rollback_on_latest_revision_preserves_new_science_and_revocation(self):
        packed, receipt = gc.prepare_archive(self.raw, ['cache/a.json'])
        current = copy.deepcopy(self.bundle)
        current['files'].pop('cache/a.json')
        current['files']['entities/result/NEW.json'] = {'encoding': 'json', 'value': {'id': 'NEW', 'result': 7}}
        current['files']['authorizations/revoked.json']['value']['revision'] = 'newer-revocation'
        raw = encode(current)
        expected = verify_live_tower(json.loads(raw))
        restored, report = gc.restore_entries(raw, packed, receipt, expected_revision=expected)
        actual = json.loads(restored)
        self.assertEqual(actual['files']['cache/a.json'], self.bundle['files']['cache/a.json'])
        self.assertEqual(actual['files']['entities/result/NEW.json'], current['files']['entities/result/NEW.json'])
        self.assertEqual(actual['files']['authorizations/revoked.json'], current['files']['authorizations/revoked.json'])
        self.assertEqual(report['status'], 'PREPARED_NOT_COMMITTED')
        again, replay = gc.restore_entries(restored, packed, receipt, expected_revision=report['after'])
        self.assertEqual(again, restored)
        self.assertEqual(replay['status'], 'NO_OP')

    def test_restore_rejects_stale_revision_changed_path_and_other_tower(self):
        packed, receipt = gc.prepare_archive(self.raw, ['cache/a.json'])
        with self.assertRaisesRegex(gc.TowerGCError, 'CAS_CONFLICT'):
            gc.restore_entries(self.raw, packed, receipt, expected_revision='old')
        current = copy.deepcopy(self.bundle)
        current['files']['cache/a.json']['value']['text'] = 'new accepted value'
        raw = encode(current)
        with self.assertRaisesRegex(gc.TowerGCError, 'PATH_CONFLICT'):
            gc.restore_entries(raw, packed, receipt, expected_revision=verify_live_tower(json.loads(raw)))
        current['stable_file_id'] = 'other'
        raw = encode(current)
        with self.assertRaisesRegex(gc.TowerGCError, 'IDENTITY_MISMATCH'):
            gc.restore_entries(raw, packed, receipt, expected_revision=verify_live_tower(json.loads(raw)))

    def test_repack_excludes_both_scanned_and_carried_base_records(self):
        self.bundle['files']['cache/unscanned.txt'] = {'encoding': 'text', 'data': 'keep for rollback'}
        raw = encode(self.bundle)
        with tempfile.TemporaryDirectory() as work:
            root, _ = materialize_live_tower(raw, work)
            excluded = frozenset({'cache/unscanned.txt', 'events/a.json'})
            candidate = build_live_tower_payload(root, base=json.loads(raw), excluded_paths=excluded)
            self.assertFalse(set(candidate['files']) & excluded)
            normal = build_live_tower_payload(root, base=json.loads(raw))
            self.assertTrue(excluded <= normal['files'].keys())
            with self.assertRaises(ValueError):
                build_live_tower_payload(root, base=self.bundle, excluded_paths=frozenset({'../evil.json'}))

    def test_unsafe_paths_refused(self):
        for path in ['../escape.json', '/abs.json', 'bad\\path.json', 'a//b.json']:
            with self.subTest(path=path), self.assertRaises(gc.TowerGCError):
                gc.prepare_archive(self.raw, [path])

    def test_continuous_dry_run_is_budgeted_cached_and_has_private_permissions(self):
        with tempfile.TemporaryDirectory() as work:
            path = Path(work) / 'dry-run.json'
            self.assertEqual(gc.opportunistic_dry_run(self.raw, path, max_bytes=0)['status'], 'SKIPPED_BUDGET')
            self.assertFalse(path.exists())
            gc.opportunistic_dry_run(self.raw, path, max_bytes=len(self.raw))
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            with patch.object(gc, 'plan_gc', side_effect=AssertionError('repeated scan')):
                self.assertEqual(gc.opportunistic_dry_run(self.raw, path, max_bytes=len(self.raw))['status'], 'CACHED_DRY_RUN')
            cached = json.loads(path.read_bytes())
            cached['summary']['physical_removals'] = 77
            path.write_text(json.dumps(cached))
            self.assertEqual(gc.opportunistic_dry_run(self.raw, path, max_bytes=len(self.raw))['status'], 'DRY_RUN')

    def test_optional_gc_failure_never_interrupts_writer_and_default_is_off(self):
        report = {}
        with patch.dict(os.environ, {}, clear=True), patch.object(gc, 'opportunistic_dry_run') as call:
            _run_optional_gc(self.raw, report)
            call.assert_not_called()
        with patch.dict(os.environ, {'NEXO_TOWER_GC_DRY_RUN': '1', 'NEXO_TOWER_GC_MAX_BYTES': 'bad'}, clear=True):
            _run_optional_gc(self.raw, report)
            self.assertEqual(report['gc']['status'], 'GC_FAILED')

    def test_cli_dry_run_does_not_overwrite_tower_or_report(self):
        with tempfile.TemporaryDirectory() as work:
            tower = Path(work) / 'tower.json'
            output = Path(work) / 'report.json'
            tower.write_bytes(self.raw)
            self.assertEqual(tower_gc_cli.main(['dry-run', str(tower), str(output)]), 0)
            self.assertEqual(tower.read_bytes(), self.raw)
            self.assertEqual(tower_gc_cli.main(['dry-run', str(tower), str(tower)]), 2)
            self.assertEqual(tower.read_bytes(), self.raw)
