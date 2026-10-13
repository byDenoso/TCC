from __future__ import annotations

import json
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from runtime.nexo_agent_api.drive_transport import (DriveHead, DriveTower, TowerConflict,
                                                    TowerReadbackMismatch, TowerTransportError)
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

    def test_http_409_is_a_recoverable_tower_conflict(self):
        class ConflictUpload(FakeDrive):
            def patch(self, url, params=None, data=None, headers=None, timeout=None):
                return _Response(409, b"head moved")

        fake = ConflictUpload(_raw(self.base))
        tower = DriveTower("FILE", session=fake)
        base = DriveHead.from_meta(fake._meta())
        with self.assertRaises(TowerConflict):
            tower.compare_and_swap(base, _raw(self._changed()))

    def test_timeout_before_upload_is_retryable_transport(self):
        class TimeoutRead:
            def get(self, *args, **kwargs):
                raise TimeoutError("private transport detail")

        with self.assertRaises(TowerTransportError) as caught:
            DriveTower("FILE", session=TimeoutRead()).download(cache=False)
        self.assertEqual(caught.exception.retry_condition, "AFTER_TRANSPORT_RECOVERY")
        self.assertNotIn("private transport detail", str(caught.exception))

    def test_timeout_after_upload_requires_fresh_readback_reconciliation(self):
        class TimeoutAfterWrite(FakeDrive):
            def patch(self, url, params=None, data=None, headers=None, timeout=None):
                super().patch(url, params=params, data=data, headers=headers, timeout=timeout)
                raise TimeoutError("server response lost")

        fake = TimeoutAfterWrite(_raw(self.base))
        tower = DriveTower("FILE", session=fake)
        base = DriveHead.from_meta(fake._meta())
        changed = _raw(self._changed())
        with self.assertRaises(TowerTransportError) as caught:
            tower.compare_and_swap(base, changed)
        self.assertEqual(caught.exception.retry_condition, "AFTER_TRANSPORT_RECOVERY")
        observed, _ = DriveTower("FILE", session=fake).download(cache=False)
        self.assertEqual(read_live_tower_bytes(observed)["state_fingerprint"],
                         read_live_tower_bytes(changed)["state_fingerprint"])

    def test_401_and_403_require_operator_reauthorization_without_escalation(self):
        class BlockedRead:
            def __init__(self, status):
                self.status = status

            def get(self, *args, **kwargs):
                return _Response(self.status, b"private permission response")

        for status in (401, 403):
            with self.subTest(status=status), self.assertRaises(TowerTransportError) as caught:
                DriveTower("FILE", session=BlockedRead(status)).download(cache=False)
            self.assertEqual(caught.exception.status_code, status)
            self.assertEqual(caught.exception.retry_condition, "OPERATOR_REAUTHORIZATION")
            self.assertNotIn("private permission response", str(caught.exception))

    def test_two_independent_writers_can_both_pass_precheck_before_unconditional_patch(self):
        class RacingDrive:
            def __init__(self, raw):
                import hashlib
                self.raw = raw
                self.revision = 1
                self.lock = threading.Lock()
                self.barrier = threading.Barrier(2)
                self.initial_reads = 0
                self.uploads = []

            def _meta(self):
                import hashlib
                return {"headRevisionId": str(self.revision), "md5Checksum": hashlib.md5(self.raw).hexdigest(),
                        "size": str(len(self.raw))}

            def get(self, url, params=None, timeout=None):
                if (params or {}).get("alt") == "media":
                    with self.lock:
                        return _Response(200, self.raw)
                with self.lock:
                    first_pair = self.initial_reads < 2
                    payload = self._meta()
                    if first_pair:
                        self.initial_reads += 1
                if first_pair:
                    self.barrier.wait(timeout=5)
                return _Response(200, payload=payload)

            def patch(self, url, params=None, data=None, headers=None, timeout=None):
                with self.lock:
                    self.raw = data
                    self.revision += 1
                    self.uploads.append({"headers": dict(headers or {}), "params": dict(params or {})})
                    payload = self._meta()
                return _Response(200, payload=payload)

        drive = RacingDrive(_raw(self.base))
        base = DriveHead.from_meta(drive._meta())
        second_root, _ = materialize_live_tower(_raw(self.base), Path(self.tmp.name) / "racer-two")
        entity_path(second_root, "test", "TEST::A").write_text(json.dumps({"id": "TEST::A", "status": "BLOCKED"}))
        publish_live_tower(second_root)
        updates = [read_live_tower_bytes(_raw(self._changed())),
                   read_live_tower_bytes((second_root / LIVE_TOWER_NAME).read_bytes())]
        raw_updates = [_raw(row) for row in updates]
        self.assertEqual(len({row["state_fingerprint"] for row in updates}), 2)

        def write(raw):
            try:
                return DriveTower("FILE", session=drive).compare_and_swap(base, raw)["status"]
            except (TowerConflict, TowerReadbackMismatch) as exc:
                return type(exc).__name__

        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(write, raw_updates))
        self.assertEqual(drive.initial_reads, 2)
        self.assertEqual(len(drive.uploads), 2)
        self.assertTrue(all("If-Match" not in write["headers"] for write in drive.uploads))
        self.assertIn(read_live_tower_bytes(drive.raw)["state_fingerprint"],
                      {row["state_fingerprint"] for row in updates})
        # The fake explicitly schedules both base checks before either PATCH;
        # local compare+readback is observability, not a remote atomic CAS.
        self.assertEqual(len(outcomes), 2)

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
    def test_raw_json_inbox_file_reads_alt_media_without_doc_export(self):
        from runtime.nexo_agent_api.drive_transport import DriveInbox

        class RawSession:
            def __init__(self):
                self.calls = []

            def get(self, url, params=None, timeout=None):
                self.calls.append((url, dict(params or {})))
                return _Response(200, b'{"kind":"BOARD_POST","payload":{"to":"EXECUTOR","text":"ok"}}')

        session = RawSession()
        inbox = DriveInbox(session=session)
        raw = inbox._content({"id": "RAW-ID", "mimeType": "application/json"})
        self.assertEqual(json.loads(raw)["kind"], "BOARD_POST")
        self.assertEqual(session.calls, [
            ("https://www.googleapis.com/drive/v3/files/RAW-ID", {"alt": "media"})
        ])

    def test_doc_export_with_fence_and_bom_is_parsed(self):
        from runtime.nexo_agent_api.drive_transport import _parse_proposal

        raw = '﻿Proposta\n```json\n{"kind": "LEARNING_SIGNAL", "payload": {"a": 1}}\n```\n'.encode("utf-8")
        self.assertEqual(_parse_proposal(raw)["kind"], "LEARNING_SIGNAL")

    def test_garbage_is_none(self):
        from runtime.nexo_agent_api.drive_transport import _parse_proposal

        self.assertIsNone(_parse_proposal(b"no json here"))


class ContractOverlayTests(unittest.TestCase):
    def test_local_contract_edit_wins_over_base(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = _tower(Path(tmp) / "seed")
            base["files"]["contracts/X.json"] = {"encoding": "json", "value": {"v": 1}}
            base["file_count"] = len(base["files"])
            root, _ = materialize_live_tower(_raw(base), Path(tmp) / "work")
            (root / "contracts").mkdir(exist_ok=True)
            (root / "contracts" / "X.json").write_text(json.dumps({"v": 2}))
            packed = build_live_tower_payload(root, base=base)
            self.assertEqual(packed["files"]["contracts/X.json"]["value"], {"v": 2})
