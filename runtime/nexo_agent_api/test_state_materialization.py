from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from .views import _deferred_by_active_p0, _prioritize, materialize_role_views
from .gpt_writer import apply_to_tower
from .live_tower import build_live_tower_payload, read_live_tower_bytes
from runtime.nexo_agent_api.tower_paths import entity_path


class StateMaterializationTests(unittest.TestCase):
    def test_writer_pack_refreshes_stale_semantic_counts_without_proposals(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "tower"
            for relative in ("snapshot", "entities/hypothesis", "entities/test"):
                (root / relative).mkdir(parents=True, exist_ok=True)
            (root / "CONTROL.json").write_text(json.dumps({
                "truth_owner": "TOWER_V06@GOOGLE_DRIVE_PRIVATE",
            }))
            (root / "snapshot/latest.json").write_text(json.dumps({
                "schema_version": "0.6", "counts": {"hypotheses": 8, "tests": 35},
            }))
            for name in ("H1", "H2"):
                (root / "entities/hypothesis" / f"{name}.json").write_text(json.dumps({
                    "id": name, "scientific_question": f"Preserve {name}",
                }))
            (root / "entities/test/T1.json").write_text(json.dumps({
                "id": "T1", "status": "VERIFIED", "scientific_question": "Keep frozen science",
                "null": "Keep its null", "verdict": "SYNTHETIC_FIXTURE_ONLY",
            }))
            raw = json.dumps(build_live_tower_payload(root), sort_keys=True,
                             separators=(",", ":")).encode("utf-8")
            packed, first = apply_to_tower(raw, [])

            self.assertIsNotNone(packed)
            self.assertEqual(first["status"], "READY_TO_UPLOAD")
            result = read_live_tower_bytes(packed)
            latest = result["files"]["snapshot/latest.json"]["value"]
            self.assertEqual(latest["counts"]["hypotheses"], 2)
            self.assertEqual(latest["counts"]["tests"], 1)
            self.assertEqual(latest["semantic_freshness"], "CURRENT_CANONICAL_ENTITY_SCAN")
            test_entity = result["files"]["entities/test/T1.json"]["value"]
            self.assertEqual(
                {key: test_entity[key] for key in ("status", "scientific_question", "null", "verdict")},
                {"status": "VERIFIED", "scientific_question": "Keep frozen science",
                 "null": "Keep its null", "verdict": "SYNTHETIC_FIXTURE_ONLY"},
            )

            replay, second = apply_to_tower(packed, [])
            self.assertIsNone(replay)
            self.assertEqual(second["status"], "NO_OP")
            self.assertEqual(second["before"], second["after"])

    def test_writer_skips_semantic_refresh_without_snapshot_or_semantic_entity_model(self):
        with tempfile.TemporaryDirectory() as td:
            no_model = Path(td) / "no-model"
            (no_model / "CONTROL.json").parent.mkdir(parents=True)
            (no_model / "CONTROL.json").write_text(json.dumps({
                "truth_owner": "TOWER_V06@GOOGLE_DRIVE_PRIVATE",
            }))
            (no_model / "snapshot").mkdir()
            (no_model / "snapshot/latest.json").write_text(json.dumps({
                "counts": {"hypotheses": 8, "tests": 35},
            }))
            (no_model / "entities/work").mkdir(parents=True)
            raw = json.dumps(build_live_tower_payload(no_model), sort_keys=True,
                             separators=(",", ":")).encode("utf-8")
            packed, report = apply_to_tower(raw, [])
            self.assertIsNotNone(packed)
            self.assertEqual(report["status"], "READY_TO_UPLOAD")
            snapshot = read_live_tower_bytes(packed)["files"]["snapshot/latest.json"]["value"]
            self.assertEqual(snapshot["counts"], {"hypotheses": 8, "tests": 35})
            self.assertNotIn("semantic_freshness", snapshot)

            no_snapshot = Path(td) / "no-snapshot"
            (no_snapshot / "CONTROL.json").parent.mkdir(parents=True)
            (no_snapshot / "CONTROL.json").write_text(json.dumps({
                "truth_owner": "TOWER_V06@GOOGLE_DRIVE_PRIVATE",
            }))
            (no_snapshot / "entities/hypothesis").mkdir(parents=True)
            (no_snapshot / "entities/hypothesis/H1.json").write_text(json.dumps({"id": "H1"}))
            raw_without_snapshot = json.dumps(build_live_tower_payload(no_snapshot), sort_keys=True,
                                              separators=(",", ":")).encode("utf-8")
            output, _ = apply_to_tower(raw_without_snapshot, [])
            bundle = read_live_tower_bytes(output or raw_without_snapshot)
            self.assertNotIn("snapshot/latest.json", bundle["files"])

    def test_reconciles_state_cursor_and_ai_roi_snapshot(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            for rel in (
                "indexes",
                "entities/work",
                "entities/hypothesis",
                "entities/test",
                "snapshot",
                "manifests",
                "events/2026-09-14",
                "events/migration",
                "mutations/receipts",
            ):
                (root / rel).mkdir(parents=True)
            (root / "CONTROL.json").write_text(json.dumps({"mode": "ACTIVE", "schema_version": "0.6"}))
            (root / "snapshot/latest.json").write_text(json.dumps({
                "schema_version": "0.6", "event_cursor": "EVT-TOWER-V06-CUTOVER",
                "counts": {"active_work": 999, "hypotheses": 8, "tests": 35},
            }))
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
            (entity_path(root, "work", "W1")).write_text(json.dumps({
                "id": "W1", "entity_version": 2, "status": "RUNNING", "owner_role": "ADVISOR", "kind": "RESEARCH"
            }))
            (entity_path(root, "work", "W2")).write_text(json.dumps({
                "id": "W2", "entity_version": 1, "status": "READY", "owner_role": "ADVISOR", "kind": "RESEARCH"
            }))
            (entity_path(root, "work", "W3")).write_text(json.dumps({
                "id": "W3", "entity_version": 3, "status": "DONE", "owner_role": "ADVISOR", "kind": "RESEARCH"
            }))
            for name in ("H1", "H2"):
                (root / "entities/hypothesis" / f"{name}.json").write_text("{}")
            (entity_path(root, "test", "T1")).write_text("{}")
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

            self.assertEqual(active["count"], 3)
            self.assertEqual(set(by_id), {"W1", "W2", "LEGACY"})
            self.assertEqual((by_id["W1"]["entity_version"], by_id["W1"]["status"]), (2, "RUNNING"))
            self.assertEqual((by_id["W2"]["entity_version"], by_id["W2"]["status"]), (1, "READY"))
            self.assertNotIn("W3", by_id)
            self.assertEqual(snapshot["counts"]["active_work"], 3)
            self.assertEqual(snapshot["counts"]["hypotheses"], 2)
            self.assertEqual(snapshot["counts"]["tests"], 1)
            self.assertEqual(snapshot["semantic_freshness"], "CURRENT_CANONICAL_ENTITY_SCAN")
            self.assertEqual(snapshot["semantic_count_sources"], {
                "hypotheses": "entities/hypothesis/*.json",
                "tests": "entities/test/*.json",
            })
            self.assertEqual(snapshot["event_cursor"], runtime_event)
            self.assertEqual(roi["source_event_cursor"], runtime_event)
            self.assertEqual(roi["active_work"]["count"], 3)
            self.assertEqual(roi["flow"]["executor_ready"], 1)
            self.assertEqual(roi["events"]["runtime_total"], 1)
            self.assertEqual(roi["events"]["verified"], 1)
            self.assertEqual(roi["mutations"]["accepted"], 1)
            self.assertEqual(roi["mutations"]["readback_pass"], 1)
            self.assertEqual(roi["roi"]["mode"], "PROXY_ONLY_NO_COST_DATA")

    def test_cold_backlog_is_excluded_from_hot_state_and_role_views(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            for rel in ("indexes", "entities/work", "snapshot", "manifests"):
                (root / rel).mkdir(parents=True)
            (root / "CONTROL.json").write_text(json.dumps({"mode": "ACTIVE", "schema_version": "0.6"}))
            (root / "snapshot/latest.json").write_text(json.dumps({"schema_version": "0.6", "counts": {"active_work": 1}}))
            (root / "manifests/capabilities.json").write_text(json.dumps({"capabilities": {}}))
            (root / "manifests/artifacts.json").write_text(json.dumps({"artifacts": {}}))
            cold = {
                "id": "COLD-EMERGENT",
                "entity_version": 9,
                "status": "CHECKPOINTED",
                "kind": "EMERGENT_TEST",
                "owner_role": "EMERGENT",
                "cold_backlog": True,
            }
            (root / "indexes/active-work.json").write_text(json.dumps({"count": 1, "work": [cold]}))
            (entity_path(root, "work", "COLD-EMERGENT")).write_text(json.dumps(cold))

            materialize_role_views(root)

            active = json.loads((root / "indexes/active-work.json").read_text())
            emergent = json.loads((root / "bootstrap/emergent.json").read_text())
            self.assertEqual(active["count"], 0)
            self.assertEqual(active["work"], [])
            self.assertEqual(emergent["queue_count"], 0)
            self.assertEqual(emergent["queue"], [])

    def test_p0_outranks_critical_and_normal_is_not_treated_as_unknown(self):
        queue = [
            {"id": "LOW", "status": "READY", "owner_role": "EXECUTOR", "priority": "LOW"},
            {"id": "NORMAL", "status": "READY", "owner_role": "EXECUTOR", "priority": "NORMAL"},
            {"id": "CRITICAL", "status": "READY", "owner_role": "EXECUTOR", "priority": "CRITICAL"},
            {"id": "P0", "status": "READY", "owner_role": "EXECUTOR", "priority": "P0"},
        ]

        ranked = _prioritize(queue, "EXECUTOR")

        self.assertEqual([item["id"] for item in ranked], ["P0", "CRITICAL", "NORMAL", "LOW"])

    def test_create_candidate_is_hidden_while_referenced_p0_is_globally_active(self):
        create_candidate = {
            "id": "CREATE-LAYER",
            "status": "READY",
            "owner_role": "EXECUTOR",
            "priority": "NORMAL",
            "operator_contract": {
                "closure": {
                    "scheduling_class": "AFTER_P0_CLOSURE",
                    "p0_refs": ["P0-OTHER-ROLE"],
                }
            },
        }

        self.assertTrue(_deferred_by_active_p0(create_candidate, {"CREATE-LAYER", "P0-OTHER-ROLE"}))
        self.assertFalse(_deferred_by_active_p0(create_candidate, {"CREATE-LAYER"}))


if __name__ == "__main__":
    unittest.main()
