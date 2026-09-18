from __future__ import annotations

import hashlib
import json
import tarfile
import tempfile
import unittest
from pathlib import Path

from runtime.portable_camb.runtime import PortableCambError, prepare_portable_camb


class PortableCambRuntimeTests(unittest.TestCase):
    def _make_payload(self, root: Path, *, camblib: bytes = b"canonical-camblib") -> Path:
        payload = root / "payload"
        (payload / "lib").mkdir(parents=True)
        (payload / "python").mkdir()
        (payload / "cosmorec").mkdir()
        launcher = payload / "peer-camb-python"
        launcher.write_text("#!/usr/bin/env bash\nexec python3 \"$@\"\n", encoding="utf-8")
        launcher.chmod(0o755)
        (payload / "lib" / "camblib.so").write_bytes(camblib)
        return payload

    def _write_manifest(self, root: Path, *, archive_sha: str, camblib_sha: str) -> Path:
        manifest = root / "PORT_MANIFEST.v2.json"
        manifest.write_text(
            json.dumps(
                {
                    "schema": "peer-camb-platform-port-2",
                    "archive_sha256": archive_sha,
                    "camblib_sha256": camblib_sha,
                    "camb_version": "1.6.6",
                    "cosmorec_version": "2.0.3",
                }
            ),
            encoding="utf-8",
        )
        return manifest

    def test_missing_runtime_source_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            self._write_manifest(root, archive_sha="0" * 64, camblib_sha="1" * 64)
            with self.assertRaisesRegex(PortableCambError, "no portable CAMB source"):
                prepare_portable_camb(env={}, runtime_root=root)

    def test_bad_archive_hash_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            source = root / "source"
            source.mkdir()
            payload = self._make_payload(source)
            archive = root / "payload.tar.gz"
            with tarfile.open(archive, "w:gz") as handle:
                handle.add(payload, arcname="payload")
            camblib_sha = hashlib.sha256((payload / "lib" / "camblib.so").read_bytes()).hexdigest()
            self._write_manifest(root, archive_sha="f" * 64, camblib_sha=camblib_sha)
            with self.assertRaisesRegex(PortableCambError, "archive SHA256 mismatch"):
                prepare_portable_camb(env={"NEXO_PEER_CAMB_ARCHIVE": str(archive)}, runtime_root=root)

    def test_verified_expanded_payload_exports_launcher_and_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            payload = self._make_payload(root)
            camblib_sha = hashlib.sha256((payload / "lib" / "camblib.so").read_bytes()).hexdigest()
            self._write_manifest(root, archive_sha="a" * 64, camblib_sha=camblib_sha)
            result = prepare_portable_camb(env={}, runtime_root=root)
            self.assertEqual(result["NEXO_CAPABILITY_PEER_CAMB_EXACT_V2"], "READY")
            self.assertEqual(result["NEXO_PEER_CAMB_VERSION"], "1.6.6")
            self.assertEqual(result["NEXO_PEER_COSMOREC_VERSION"], "2.0.3")
            self.assertEqual(result["NEXO_PEER_CAMB_CAMBLIB_SHA256"], camblib_sha)
            self.assertEqual(Path(result["NEXO_CAPABILITY_PEER_CAMB_EXACT_V2_LAUNCHER"]), payload / "peer-camb-python")

    def test_verified_expanded_archive_layout_exports_python_camb_library(self) -> None:
        with tempfile.TemporaryDirectory() as raw:

            root = Path(raw)
            payload = root / "payload"
            (payload / "python" / "camb").mkdir(parents=True)
            (payload / "cosmorec").mkdir()
            launcher = payload / "peer-camb-python"
            launcher.write_text("#!/usr/bin/env bash\nexec python3 \"$@\"\n", encoding="utf-8")
            launcher.chmod(0o755)
            camblib = payload / "python" / "camb" / "camblib.so"
            camblib.write_bytes(b"archive-layout-camblib")
            camblib_sha = hashlib.sha256(camblib.read_bytes()).hexdigest()
            self._write_manifest(root, archive_sha="a" * 64, camblib_sha=camblib_sha)
            result = prepare_portable_camb(env={}, runtime_root=root)
            self.assertEqual(result["NEXO_CAPABILITY_PEER_CAMB_EXACT_V2"], "READY")
            self.assertEqual(result["NEXO_PEER_CAMB_CAMBLIB_SHA256"], camblib_sha)
            self.assertEqual(Path(result["NEXO_CAPABILITY_PEER_CAMB_EXACT_V2_LAUNCHER"]), launcher)


if __name__ == "__main__":
    unittest.main()
