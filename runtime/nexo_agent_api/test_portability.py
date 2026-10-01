import base64
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from runtime.nexo_agent_api.live_tower import build_live_tower_payload, _canonical
from runtime.nexo_agent_api.portability import (
    _publish_directory_noclobber,
    digest,
    export_tower,
    restore_export,
    verify_export,
)


class PortableTowerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        seed = self.root / 'seed'
        seed.mkdir()
        (seed / 'CONTROL.json').write_text(json.dumps({'truth_owner': 'TOWER_V06@GOOGLE_DRIVE_PRIVATE'}))
        self.bundle = build_live_tower_payload(seed, base={'files': {
            'runtime/tool.bin': {'encoding': 'base64', 'data': base64.b64encode(b'\x00\xffbinary').decode()},
            'mutations/inbox/applied.json': {'encoding': 'json', 'value': {'id': 'REQ::1', 'status': 'APPLIED'}}}})
        self.raw = _canonical(self.bundle)

    def tearDown(self):
        for p in self.root.rglob('*'):
            p.chmod(0o700 if p.is_dir() else 0o600)
        self.tmp.cleanup()

    def test_roundtrip_offline_all_bytes_no_replay(self):
        out = self.root / 'export'
        result = export_tower(self.raw, out)
        self.assertEqual(result['completeness'], 'INCOMPLETE_EXTERNAL_BYTES')
        with self.assertRaisesRegex(ValueError, 'INCOMPLETE_EXPORT'):
            restore_export(out, self.root / 'fail')
        with patch('socket.socket', side_effect=AssertionError('network forbidden')):
            restore_export(out, self.root / 'restored', allow_incomplete=True)
        self.assertEqual((self.root / 'restored/runtime/tool.bin').read_bytes(), b'\x00\xffbinary')
        self.assertEqual((self.root / 'restored/NEXO_TOWER_LIVE.json').read_bytes(), self.raw)
        self.assertEqual(json.loads((self.root / 'restored/mutations/inbox/applied.json').read_text())['status'], 'APPLIED')
        self.assertFalse(json.loads((self.root / 'restored/.nexo-isolated.json').read_text())['proposal_replay'])
        self.assertEqual((self.root / 'restored/runtime/tool.bin').stat().st_mode & 0o777, 0o400)
        self.assertEqual(verify_export(self.root / 'restored/.nexo-export')['source_sha256'], digest(self.raw))
        with self.assertRaises(FileExistsError):
            restore_export(out, self.root / 'restored', allow_incomplete=True)

    def test_stale_header_rejected(self):
        self.bundle['revision'] = 'sha256:stale'
        with self.assertRaisesRegex(ValueError, 'SOURCE_DECLARED_HASH_MISMATCH'):
            export_tower(_canonical(self.bundle), self.root / 'out')

    def test_corrupt_source_and_manifest_rejected(self):
        out = self.root / 'export'
        result = export_tower(self.raw, out)
        (out / 'source.bin').chmod(0o600)
        (out / 'source.bin').write_bytes(self.raw + b' ')
        with self.assertRaisesRegex(ValueError, 'SOURCE_BYTES_MISMATCH'):
            verify_export(out)
        with self.assertRaisesRegex(ValueError, 'MANIFEST_HASH_MISMATCH'):
            verify_export(out, expected_manifest_sha256='0' * 64)
        self.assertEqual(len(result['manifest_sha256']), 64)

    def test_external_manifest_digest_does_not_bypass_corrupt_sidecar(self):
        out = self.root / 'export'
        result = export_tower(self.raw, out)
        sidecar = out / 'manifest.sha256'
        sidecar.chmod(0o600)
        sidecar.write_text('0' * 64 + '\n')
        with self.assertRaisesRegex(ValueError, 'MANIFEST_HASH_MISMATCH'):
            verify_export(out, expected_manifest_sha256=result['manifest_sha256'])

    def test_noncanonical_tower_identity_is_rejected_without_claiming_authentication(self):
        self.bundle['stable_file_id'] = 'different-private-file'
        with self.assertRaisesRegex(ValueError, 'SOURCE_CANONICAL_FILE_ID_MISMATCH'):
            export_tower(_canonical(self.bundle), self.root / 'out')

        result = export_tower(self.raw, self.root / 'local')
        manifest = verify_export(self.root / 'local', expected_manifest_sha256=result['manifest_sha256'])
        self.assertEqual(manifest['source_authentication'], 'LOCAL_BYTES_UNAUTHENTICATED')

    def test_windows_path_collisions_and_reserved_names_fail_before_export(self):
        bad_file_sets = [
            {
                'runtime/Result.json': {'encoding': 'json', 'value': {}},
                'runtime/result.json': {'encoding': 'json', 'value': {}},
            },
            {'runtime/NUL.txt': {'encoding': 'text', 'data': 'reserved'}},
            {'runtime/trailing.': {'encoding': 'text', 'data': 'normalizes on Windows'}},
            {
                'runtime/prefix': {'encoding': 'text', 'data': 'file'},
                'runtime/prefix/child': {'encoding': 'text', 'data': 'cannot have a file parent'},
            },
        ]
        for index, files in enumerate(bad_file_sets):
            with self.subTest(index=index):
                bundle = build_live_tower_payload(self.root / 'seed', base={'files': files})
                destination = self.root / f'bad-{index}'
                with self.assertRaisesRegex(ValueError, 'Windows|collision'):
                    export_tower(_canonical(bundle), destination)
                self.assertFalse(destination.exists())

    def test_publish_never_replaces_destination_created_after_initial_check(self):
        staging = self.root / 'staging'
        destination = self.root / 'destination'
        staging.mkdir()
        (staging / 'manifest.json').write_text('{}')
        destination.mkdir()
        sentinel = destination / 'keep'
        sentinel.write_text('pre-existing')

        with self.assertRaises(FileExistsError):
            _publish_directory_noclobber(staging, destination)

        self.assertEqual(sentinel.read_text(), 'pre-existing')
        self.assertTrue((staging / 'manifest.json').exists())

    def test_unsafe_and_unknown_encoding_rejected_before_export(self):
        for name, entry in [('../escape', {'encoding': 'text', 'data': 'bad'}),
                            ('runtime/unknown', {'encoding': 'other', 'data': 'bad'})]:
            bundle = build_live_tower_payload(self.root / 'seed', base={'files': {name: entry}})
            with self.assertRaises(ValueError):
                export_tower(_canonical(bundle), self.root / 'bad')
            self.assertFalse((self.root / 'bad').exists())

    def test_pinned_dependency_and_tamper(self):
        data = b'private runtime fixture, not credentials'
        artifact = self.root / 'archive'
        artifact.write_bytes(data)
        dep = {'id': 'fixture', 'ref': 'private', 'sha256': digest(data), 'status': 'MISSING_BYTES', 'reason': 'absent'}
        with patch('runtime.nexo_agent_api.portability._dependencies', return_value=[dep]):
            out = self.root / 'complete'
            export_tower(self.raw, out, attachments={'fixture': artifact})
            self.assertEqual(verify_export(out)['completeness'], 'COMPLETE_KNOWN_DEPENDENCIES')
            restore_export(out, self.root / 'complete-restored')
            obj = out / 'objects' / digest(data)
            obj.chmod(0o600)
            obj.write_bytes(b'wrong')
            with self.assertRaisesRegex(ValueError, 'DEPENDENCY_BYTES_MISMATCH'):
                verify_export(out)

    def test_wrong_dependency_hash_fails_without_partial_export(self):
        artifact = self.root / 'wrong'
        artifact.write_bytes(b'wrong CAMB archive')
        with self.assertRaisesRegex(ValueError, 'DEPENDENCY_HASH_MISMATCH'):
            export_tower(self.raw, self.root / 'bad', attachments={'peer.camb.exact_v2': artifact})
        self.assertFalse((self.root / 'bad').exists())


if __name__ == '__main__':
    unittest.main()
