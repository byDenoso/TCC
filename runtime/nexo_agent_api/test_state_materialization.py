from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from .views import materialize_role_views


class StateMaterializationTests(unittest.TestCase):
    def test_reconciles_state_cursor_and_ai_roi_snapshot(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            for rel in (
                "indexes",
                "entities/work",
                "snapshot",
                "manifests",
                "events/2026-09-14",
                "events/migration",
                "mutations/receipts",
            ):
                (root / rel).mkdir(parents=True)
            (root / "CONTROL.json").write_text(json.dumps({"mode": "ACTIVE", "schema_version": "0.6"}))
            (root / "snapshot/latest.json").write_text(json.dumps({"schema_version": "0.6", "event_cursor": "EVT-TOWER-V06-CUTOVER", "counts": {"active_work": 999}}))
            (root / "manifests/capabilities.json").write_text(json.dumps({"capabilities": {}}))
            (root / "manifests/artifacts.json").write_text(json.dumps({"artifacts": {}}))
            (root / "indexes/active-work.json").write_text(json.dumps({
                "count": 3,
                "schema_version": "0.6",
                "source": "GITHUB_TOWER_HOT_SET",
                "policy": "hot",
                "work": [
                    {"id": "W1", "entity_version": 1, "status": "READY", "owner_role": "ADVISOR", "kind": "RESEARCH"},
                    {"id": "LEGACY", "entity_version": 1, "status": "READY", "owner_role": "EXECUTOR", "kind": "RESEARCH"},
                    {"id": "W3", "entity_version": 2, "status": "READY", "kind": "RESEARCH"},
                ],
            }))
            (root / "entities/work/W1.json").write_text(json.dumps({
                "id": "W1", "entity_version": 2, "status": "RUNNING", "owner_role": "ADVISOR", "kind": "RESEARCH"
            }))
            (root / "entities/work/W2.json").write_text(json.dumps({
                "id": "W2", "entity_version": 1, "status": "READY", "owner_role": "ADVISOR", "kind": "RESEARCH"
            }))
            (root / "entities/work/W3.json").write_text(json.dumps({
                "id": "W3", "entity_version": 3, "status": "DONE", "owner_role": "ADVISOR", "kind": "RESEARCH"
            }))
            (root / "events/migration/ZZZ.json").write_text(json.dumps({"event_id": "EVT-TOWER-V06-CUTOVER"}))
            runtime_event = "20260914T042812842429Z-e6dbcab6"
            (root / f"events/2026-09-14/{runtime_event}.json").write_text(json.dumps({
                "event_id": runtime_event,
                "event_type": "WORK_VERIFIED_TO_ADVISOR",
                "writer_role": "EXECUTOR",
                "material": True,
            }))
            (root / "mutations/receipts/R1.json").write_text(json.dumps({
                "accepted": True,
                "readback": "PASS",
                "event_id": runtime_event,
            }))

            materialize_role_views(root)

            active = json.loads((root / "indexes/active-work.json").read_text())
            snapshot = json.loads((root / "snapshot/latest.json").read_text())
            roi = json.loads((root / "snapshot/ai-roi.json").read_text())
            by_id = {item["id"]: item for item in active["work"]}

            self.assertEqual(active["count"], 2)
            self.assertEqual(set(by_id), {"W1", "LEGACY"})
            self.assertNotIn("W2", by_id)
            self.assertNotIn("W3", by_id)
            self.assertEqual((by_id["W1"]["entity_version"], by_id["W1"]["status"]), (2, "RUNNING"))
            self.assertEqual(snapshot["counts"]["active_work"], 2)
            self.assertEqual(snapshot["event_cursor"], runtime_event)
            self.assertEqual(roi["source_event_cursor"], runtime_event)
            self.assertEqual(roi["active_work"]["count"], 2)
            self.assertEqual(roi["flow"]["executor_ready"], 1)
            self.assertEqual(roi["events"]["runtime_total"], 1)
            self.assertEqual(roi["events"]["verified"], 1)
            self.assertEqual(roi["mutations"]["accepted"], 1)
            self.assertEqual(roi["mutations"]["readback_pass"], 1)
            self.assertEqual(roi["roi"]["mode"], "PROXY_ONLY_NO_COST_DATA")


if __name__ == "__main__":
    unittest.main()
