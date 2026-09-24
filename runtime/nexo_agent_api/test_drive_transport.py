from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from runtime.nexo_agent_api.drive_transport import DriveTower, TowerConflict, TowerReadbackMismatch
from runtime.nexo_agent_api.live_tower import (
    LIVE_TOWER_NAME,
    build_live_tower_payload,
    materialize_live_tower,
    publish_live_tower,
    read_live_tower_bytes,
    verify_live_tower,
)
from runtime.nexo_agent_api.tower_paths import entity_path


class _Response:
    def __init__(self, status: int, body: bytes = b"", payload: dict | None = None) -> None:
        self.status_code = status
        self.content = body
        self.text = body.decode("utf-8", "replace")
        self._payload = payload

    def json(self) -> dict:
        return self._payload if self._payload is not None else json.loads(self.content)


class FakeDrive:
    """In-memory Drive file with a revision counter; ``foreign_write`` simulates a race."""

    def __init__(self, raw: bytes) -> None:
        self.raw = raw
        self.revision = 1
        self.foreign_write: bytes | None = None
        self.corrupt_readback = False

    def _meta(self) -> dict:
        return {"headRevisionId": str(self.revision), "md5Checksum": str(hash(self.raw)), "size": str(len(self.raw))}

    def get(self, url, params=None, timeout=None):
        if (params or {}).get("alt") == "media":
            body = b'{"state_fingerprint":"sha256:bogus"}' if self.corrupt_readback else self.raw
            return _Response(200, body)
        if self.foreign_write is not None:
            self.raw, self.foreign_write = self.foreign_write, None
            self.revision += 1
        return _Response(200, payload=self._meta())

    def patch(self, url, params=None, data=None, headers=None, timeout=None):
        self.raw = data
        self.revision += 1
        return _Response(200, payload=self._meta())


def _tower(root: Path) -> dict:
    (root / "entities" / "test").mkdir(parents=True)
    (root / "CONTROL.json").write_text(json.dumps({"truth_owner": "TOWER_V06@GOOGLE_DRIVE_PRIVATE"}))
    entity_path(root, "test", "TEST::A").write_text(json.dumps({"id": "TEST::A", "status": "READY"}))
    return build_live_tower_payload(root, updated_at="2026-09-23T00:00:00Z")


def _raw(payload: dict) -> bytes:
    return json.dumps(payload, sort_keys=True).encode("utf-8")


class DriveTransportTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.base = _tower(Path(self.tmp.name) / "seed")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _changed(self) -> dict:
        root, _ = materialize_live_tower(_raw(self.base), Path(self.tmp.name) / "work")
        entity_path(root, "test", "TEST::A").write_text(json.dumps({"id": "TEST::A", "status": "RESULT"}))
        publish_live_tower(root)
        return read_live_tower_bytes((root / LIVE_TOWER_NAME).read_bytes())

    def test_compare_and_swap_writes_same_file_and_reads_back(self):
        fake = FakeDrive(_raw(self.base))
        tower = DriveTower("FILE", session=fake)
        _, head = tower.download()
        changed = self._changed()
        receipt = tower.compare_and_swap(head, _raw(changed))
        self.assertEqual(receipt["readback"], "PASS")
        self.assertEqual(read_live_tower_bytes(fake.raw)["state_fingerprint"], changed["state_fingerprint"])

    def test_foreign_write_between_read_and_write_is_refused(self):
        fake = FakeDrive(_raw(self.base))
        tower = DriveTower("FILE", session=fake)
        _, head = tower.download()
        fake.foreign_write = b'{"other":"writer"}'
        with self.assertRaises(TowerConflict):
            tower.compare_and_swap(head, _raw(self._changed()))
        self.assertEqual(fake.raw, b'{"other":"writer"}')

    def test_readback_mismatch_is_reported(self):
        fake = FakeDrive(_raw(self.base))
        tower = DriveTower("FILE", session=fake)
        _, head = tower.download()
        fake.corrupt_readback = True
        with self.assertRaises(TowerReadbackMismatch):
            tower.compare_and_swap(head, _raw(self._changed()))

    def test_repack_preserves_files_outside_scanned_surfaces(self):
        base = dict(self.base)
        files = dict(base["files"])
        files["contracts/X.json"] = {"encoding": "json", "value": {"keep": True}}
        files["governance/NOTE.md"] = {"encoding": "text", "data": "keep me"}
        base = build_live_tower_payload(Path(self.tmp.name) / "seed", updated_at="t", base={"files": files})
        verify_live_tower(base)
        changed_root, _ = materialize_live_tower(_raw(base), Path(self.tmp.name) / "work2")
        publish_live_tower(changed_root)
        repacked = read_live_tower_bytes((changed_root / LIVE_TOWER_NAME).read_bytes())
        self.assertIn("contracts/X.json", repacked["files"])
        self.assertEqual(repacked["files"]["governance/NOTE.md"]["data"], "keep me")
        self.assertIn("entities/test/TEST::A.json", repacked["files"])
        self.assertEqual(repacked["state_fingerprint"], base["state_fingerprint"])

    def test_repack_of_unchanged_tower_is_identity(self):
        root, _ = materialize_live_tower(_raw(self.base), Path(self.tmp.name) / "work3")
        publish_live_tower(root)
        again = read_live_tower_bytes((root / LIVE_TOWER_NAME).read_bytes())
        self.assertEqual(again["state_fingerprint"], self.base["state_fingerprint"])


if __name__ == "__main__":
    unittest.main()


class _Md5Drive(FakeDrive):
    """FakeDrive with a real md5 and a media-download counter."""

    def __init__(self, raw: bytes) -> None:
        super().__init__(raw)
        self.media_calls = 0

    def _meta(self) -> dict:
        import hashlib

        return {"headRevisionId": str(self.revision), "md5Checksum": hashlib.md5(self.raw).hexdigest(), "size": str(len(self.raw))}

    def get(self, url, params=None, timeout=None):
        if (params or {}).get("alt") == "media":
            self.media_calls += 1
        return super().get(url, params=params, timeout=timeout)


class ReaderCacheTests(unittest.TestCase):
    def setUp(self) -> None:
        import os

        self.tmp = tempfile.TemporaryDirectory()
        self._home = os.environ.get("NEXO_HOME")
        os.environ["NEXO_HOME"] = self.tmp.name
        self.raw = _raw(_tower(Path(self.tmp.name) / "seed"))

    def tearDown(self) -> None:
        import os

        if self._home is None:
            os.environ.pop("NEXO_HOME", None)
        else:
            os.environ["NEXO_HOME"] = self._home
        self.tmp.cleanup()

    def test_reader_reuses_copy_while_head_md5_is_unchanged(self):
        drive = _Md5Drive(self.raw)
        tower = DriveTower(session=drive)
        self.assertEqual(tower.download()[0], self.raw)
        self.assertEqual(tower.download()[0], self.raw)
        self.assertEqual(drive.media_calls, 1)

    def test_changed_head_is_downloaded_again(self):
        drive = _Md5Drive(self.raw)
        tower = DriveTower(session=drive)
        tower.download()
        drive.raw = self.raw.replace(b"READY", b"RESULT")
        self.assertIn(b"RESULT", tower.download()[0])
        self.assertEqual(drive.media_calls, 2)

    def test_writer_never_uses_the_cache(self):
        drive = _Md5Drive(self.raw)
        DriveTower(session=drive).download()
        DriveTower(session=drive, write=True).download()
        self.assertEqual(drive.media_calls, 2)


class ProposalParsingTests(unittest.TestCase):
    def test_doc_export_with_fence_and_bom_is_parsed(self):
        from runtime.nexo_agent_api.drive_transport import _parse_proposal

        raw = '﻿Proposta\n```json\n{"kind": "LEARNING_SIGNAL", "payload": {"a": 1}}\n```\n'.encode("utf-8")
        self.assertEqual(_parse_proposal(raw)["kind"], "LEARNING_SIGNAL")

    def test_garbage_is_none(self):
        from runtime.nexo_agent_api.drive_transport import _parse_proposal

        self.assertIsNone(_parse_proposal(b"no json here"))
