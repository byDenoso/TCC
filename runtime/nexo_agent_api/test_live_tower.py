from __future__ import annotations

import gzip
import json
import tempfile
import unittest
from pathlib import Path

from scripts.build_public_projection import materialize_live_tower_root
from .public_projection import build_public_projection, verify_projection
from .test_public_projection import _tower
from .live_tower import (
    LIVE_TOWER_FILE_ID,
    LIVE_TOWER_NAME,
    build_live_tower_payload,
    publish_live_tower,
)
from runtime.nexo_agent_api.tower_paths import entity_path


class LiveTowerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "TOWER_V06"
        (self.root / "entities" / "work").mkdir(parents=True)
        (self.root / "indexes").mkdir(parents=True)
        (self.root / "projections" / "public").mkdir(parents=True)
        (self.root / "CONTROL.json").write_text(json.dumps({"mode": "ACTIVE"}), encoding="utf-8")
        (entity_path(self.root, "work", "W1")).write_text(
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
        path = entity_path(self.root, "work", "W1")
        work = json.loads(path.read_text(encoding="utf-8"))
        work["status"] = "RUNNING"
        path.write_text(json.dumps(work), encoding="utf-8")
        after = build_live_tower_payload(self.root)["revision"]
        self.assertNotEqual(before, after)

    def test_public_projection_materializes_directly_from_live_tower(self) -> None:
        source = _tower(Path(self.tmp.name) / "projection-source")
        control_path = source / "CONTROL.json"
        control = json.loads(control_path.read_text(encoding="utf-8"))
        control["truth_owner"] = "TOWER_V06@GOOGLE_DRIVE_PRIVATE"
        control["write_model"] = "IN_PLACE_FILE_REVISION_CAS_READBACK"
        control_path.write_text(json.dumps(control), encoding="utf-8")

        payload = build_live_tower_payload(source, updated_at="2026-09-23T12:00:00Z")
        bundle = Path(self.tmp.name) / "NEXO_TOWER_LIVE_SOURCE.json.gz"
        with gzip.open(bundle, "wt", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, sort_keys=True)

        root, metadata = materialize_live_tower_root(
            bundle,
            Path(self.tmp.name) / "materialized" / "TOWER_V06",
        )
        self.assertFalse((root / "CURRENT.json").exists())

        projection = build_public_projection(
            root,
            tower_revision=str(metadata["tower_revision"]),
            tower_file_id=str(metadata["tower_file_id"]),
            generated_at="2026-09-23T12:01:00Z",
        )
        ok, detail = verify_projection(projection)
        self.assertTrue(ok, detail)
        self.assertEqual(
            projection["manifest"]["tower_file_id"],
            LIVE_TOWER_FILE_ID,
        )
        self.assertEqual(
            projection["manifest"]["tower_revision"],
            payload["revision"],
        )

    def test_projection_materializes_plain_json_live_tower(self) -> None:
        """O objeto vivo atual no Drive é JSON puro; o builder da projeção lê direto."""
        source = _tower(Path(self.tmp.name) / "plain-source")
        control_path = source / "CONTROL.json"
        control = json.loads(control_path.read_text(encoding="utf-8"))
        control["truth_owner"] = "TOWER_V06@GOOGLE_DRIVE_PRIVATE"
        control["write_model"] = "IN_PLACE_FILE_REVISION_CAS_READBACK"
        control_path.write_text(json.dumps(control), encoding="utf-8")

        published = publish_live_tower(source, updated_at="2026-09-23T12:00:00Z")
        live = source / LIVE_TOWER_NAME
        self.assertEqual(live.read_bytes()[:1], b"{")

        root, metadata = materialize_live_tower_root(live, Path(self.tmp.name) / "plain-materialized" / "TOWER_V06")
        self.assertEqual(metadata["tower_revision"], published["revision"])
        self.assertTrue((root / "CONTROL.json").exists())

    def test_publish_replaces_same_local_file_and_readbacks(self) -> None:
        first = publish_live_tower(self.root, updated_at="2026-09-23T12:00:00Z")
        path = self.root / LIVE_TOWER_NAME
        self.assertTrue(path.exists())

        self.assertNotEqual(path.read_bytes()[:2], b"\x1f\x8b")  # JSON puro, igual ao objeto no Drive
        decoded = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(decoded["stable_file_id"], LIVE_TOWER_FILE_ID)
        self.assertEqual(decoded["revision"], first["revision"])

        work_path = entity_path(self.root, "work", "W1")
        work = json.loads(work_path.read_text(encoding="utf-8"))
        work["status"] = "DONE"
        work_path.write_text(json.dumps(work), encoding="utf-8")

        second = publish_live_tower(self.root, updated_at="2026-09-23T12:05:00Z")
        self.assertNotEqual(second["revision"], first["revision"])
        self.assertEqual(second["path"], first["path"])


if __name__ == "__main__":
    unittest.main()

