from __future__ import annotations

import gzip
import json
import tempfile
import unittest
from pathlib import Path

from .live_tower import (
    LIVE_TOWER_FILE_ID,
    LIVE_TOWER_NAME,
    build_live_tower_payload,
    publish_live_tower,
)


class LiveTowerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "TOWER_V06"
        (self.root / "entities" / "work").mkdir(parents=True)
        (self.root / "indexes").mkdir(parents=True)
        (self.root / "projections" / "public").mkdir(parents=True)
        (self.root / "CONTROL.json").write_text(json.dumps({"mode": "ACTIVE"}), encoding="utf-8")
        (self.root / "entities" / "work" / "W1.json").write_text(
            json.dumps({"id": "W1", "status": "READY", "entity_version": 1}),
            encoding="utf-8",
        )
        (self.root / "projections" / "public" / "latest.json").write_text(
            json.dumps({"derived": True}),
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_live_tower_has_stable_identity_and_state_revision(self) -> None:
        payload = build_live_tower_payload(self.root, updated_at="2026-09-23T12:00:00Z")
        self.assertEqual(payload["contract"], "NEXO_TOWER_LIVE_V1")
        self.assertEqual(payload["stable_file_id"], LIVE_TOWER_FILE_ID)
        self.assertEqual(payload["revision"], payload["state_fingerprint"])
        self.assertIn("CONTROL.json", payload["files"])
        self.assertIn("entities/work/W1.json", payload["files"])
        self.assertNotIn("projections/public/latest.json", payload["files"])

    def test_timestamp_does_not_change_state_revision(self) -> None:
        first = build_live_tower_payload(self.root, updated_at="2026-09-23T12:00:00Z")
        later = build_live_tower_payload(self.root, updated_at="2026-09-23T13:00:00Z")
        self.assertEqual(first["revision"], later["revision"])

    def test_material_change_changes_revision(self) -> None:
        before = build_live_tower_payload(self.root)["revision"]
        path = self.root / "entities" / "work" / "W1.json"
        work = json.loads(path.read_text(encoding="utf-8"))
        work["status"] = "RUNNING"
        path.write_text(json.dumps(work), encoding="utf-8")
        after = build_live_tower_payload(self.root)["revision"]
        self.assertNotEqual(before, after)

    def test_publish_replaces_same_local_file_and_readbacks(self) -> None:
        first = publish_live_tower(self.root, updated_at="2026-09-23T12:00:00Z")
        path = self.root / LIVE_TOWER_NAME
        self.assertTrue(path.exists())

        decoded = json.loads(gzip.decompress(path.read_bytes()).decode("utf-8"))
        self.assertEqual(decoded["stable_file_id"], LIVE_TOWER_FILE_ID)
        self.assertEqual(decoded["revision"], first["revision"])

        work_path = self.root / "entities" / "work" / "W1.json"
        work = json.loads(work_path.read_text(encoding="utf-8"))
        work["status"] = "DONE"
        work_path.write_text(json.dumps(work), encoding="utf-8")

        second = publish_live_tower(self.root, updated_at="2026-09-23T12:05:00Z")
        self.assertNotEqual(second["revision"], first["revision"])
        self.assertEqual(second["path"], first["path"])


if __name__ == "__main__":
    unittest.main()
