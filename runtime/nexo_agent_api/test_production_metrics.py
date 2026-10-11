from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from .production_metrics import CONFIG_PATH, CONFIG_SCHEMA, GOAL_SCHEMA, evaluate_production_target


class ProductionThroughputMetricTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        for rel in ("entities/work", "entities/test", "events/2026-10-01", "runtime/artifacts"):
            (self.root / rel).mkdir(parents=True, exist_ok=True)
        self.current_window = {"start": "2026-10-02T00:00:00Z", "end": "2026-10-02T02:00:00Z"}

    def tearDown(self):
        self.tmp.cleanup()

    def _write_event(self, event_id: str, kind: str, name: str, version: int):
        event = {"event_id": event_id, "entity_kind": kind, "entity_name": name,
                 "entity_version": version, "writer_role": "ADVISOR", "material": True,
                 "readback": "PASS"}
        (self.root / "events/2026-10-01" / (event_id + ".json")).write_text(
            json.dumps(event, sort_keys=True), encoding="utf-8")

    def _install_target_and_config(self, *, baseline_window=None):
        target = {"id": "GOAL-ONE", "entity_version": 5,
                  "throughput_goal": {"schema": GOAL_SCHEMA,
                                      "metric": "verified_scientific_tests_per_hour",
                                      "multiplier": 4}}
        raw = json.dumps(target, ensure_ascii=False, sort_keys=True).encode("utf-8")
        (self.root / "entities/work/GOAL-ONE.json").write_bytes(raw)
        self._write_event("EVENT-GOAL", "work", "GOAL-ONE", 5)
        config = {"schema": CONFIG_SCHEMA, "target_ref": "entities/work/GOAL-ONE.json",
                  "target_sha256": hashlib.sha256(raw).hexdigest(), "target_entity_version": 5,
                  "target_verification_event_id": "EVENT-GOAL",
                  "baseline_window": baseline_window or {
                      "start": "2026-10-01T00:00:00Z", "end": "2026-10-01T02:00:00Z"}}
        config_path = self.root / CONFIG_PATH
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(json.dumps(config, sort_keys=True), encoding="utf-8")

    def _write_test(self, test_id: str, when: str, *, target="entities/work/GOAL-ONE.json",
                    status="DONE", phase="COMPLETED", verdict="SUPPORTED", category=None,
                    artifact=True, readback=True, intervention=None, eligible=True,
                    duplicate_of=None):
        test = {"id": test_id, "entity_version": 2, "target_ref": target, "status": status,
                "execution_phase": phase, "verdict": verdict, "prereg_hash": "sha256:preregistered",
                "executed_at": when, "started_at": "2026-10-01T00:00:00Z",
                "readiness": {"eligible": eligible}}
        if category:
            test["production_class"] = category
        if intervention is not None:
            test["human_intervention"] = intervention
        if duplicate_of:
            test["duplicate_of"] = duplicate_of
        path = self.root / "entities/test" / (test_id + ".json")
        path.write_text(json.dumps(test, sort_keys=True), encoding="utf-8")
        if artifact:
            artifact_path = self.root / "runtime/artifacts" / (test_id + ".json")
            artifact_bytes = json.dumps({"test_id": test_id, "status": "TERMINAL"}, sort_keys=True).encode()
            artifact_path.write_bytes(artifact_bytes)
            test["artifact_ref"] = f"runtime/artifacts/{test_id}.json"
            test["artifact_sha256"] = hashlib.sha256(artifact_bytes).hexdigest()
            path.write_text(json.dumps(test, sort_keys=True), encoding="utf-8")
        if readback:
            self._write_event("EVENT-" + test_id, "test", test_id, 2)

    def test_missing_live_target_is_blocked_without_zero_baseline(self):
        result = evaluate_production_target(self.root, current_window=self.current_window)
        self.assertEqual(result["status"], "BLOCKED_LIVE_TARGET_UNVERIFIED")
        self.assertIn("NO_VERIFIABLE_LIVE_THROUGHPUT_TARGET", result["blockers"])
        self.assertIsNone(result["baseline"]["value"])
        self.assertIsNone(result["observed"]["value"])

    def test_fourfold_is_measured_only_for_distinct_verified_scientific_tests(self):
        self._install_target_and_config()
        for index in range(2):
            self._write_test(f"BASE-{index}", "2026-10-01T01:00:00Z")
        for index in range(8):
            self._write_test(f"CURRENT-{index}", "2026-10-02T01:00:00Z",
                             intervention=(index == 0), eligible=True)
        # These rows are deliberately tempting operational/scientific proxies.
        self._write_test("CURRENT-SMOKE", "2026-10-02T01:00:00Z", category="SMOKE")
        self._write_test("CURRENT-RETRY", "2026-10-02T01:00:00Z", duplicate_of="CURRENT-0")
        self._write_test("CURRENT-SEED", "2026-10-02T01:00:00Z", category="SEED")
        self._write_test("CURRENT-SCAN", "2026-10-02T01:00:00Z", category="SCAN")
        self._write_test("CURRENT-CONTEST", "2026-10-02T01:00:00Z", verdict="CONTESTED")
        self._write_test("CURRENT-RUNNING", "2026-10-02T01:00:00Z", phase="RUNNING")
        self._write_test("CURRENT-NO-PROOF", "2026-10-02T01:00:00Z", artifact=False)
        self._write_test("CURRENT-WRONG-TARGET", "2026-10-02T01:00:00Z", target="entities/work/OTHER.json")

        result = evaluate_production_target(self.root, current_window=self.current_window)
        self.assertEqual(result["status"], "MEASURED_TARGET")
        self.assertEqual(result["baseline"]["count"], 2)
        self.assertEqual(result["observed"]["count"], 8)
        self.assertEqual(result["observed_multiplier"], 4.0)
        self.assertTrue(result["target_met"])
        self.assertEqual(result["autonomy"], {"value": 0.875, "numerator": 7,
                                               "denominator": 8, "status": "MEASURED"})
        self.assertEqual(result["median_observed_duration"]["samples"], 8)
        self.assertEqual(result["median_recovery_time"]["status"], "UNMEASURED")
        self.assertEqual(result["observed"]["quality"]["excluded_test_rows"], 5)
        self.assertGreaterEqual(result["observed"]["quality"]["execution_not_completed"], 1)
        self.assertGreaterEqual(result["observed"]["quality"]["missing_artifact_or_readback"], 1)

    def test_target_hash_and_readback_must_match_the_canonical_entity(self):
        self._install_target_and_config()
        config_path = self.root / CONFIG_PATH
        config = json.loads(config_path.read_text(encoding="utf-8"))
        config["target_sha256"] = "0" * 64
        config_path.write_text(json.dumps(config), encoding="utf-8")
        result = evaluate_production_target(self.root, current_window=self.current_window)
        self.assertEqual(result["status"], "BLOCKED_TARGET_PROVENANCE_UNVERIFIED")
        self.assertEqual(result["blockers"], ["TARGET_PROVENANCE_MISMATCH"])

        self._install_target_and_config()
        event_path = self.root / "events/2026-10-01/EVENT-GOAL.json"
        event = json.loads(event_path.read_text(encoding="utf-8"))
        event["readback"] = "FAIL"
        event_path.write_text(json.dumps(event), encoding="utf-8")
        result = evaluate_production_target(self.root, current_window=self.current_window)
        self.assertEqual(result["status"], "BLOCKED_TARGET_PROVENANCE_UNVERIFIED")
        self.assertEqual(result["blockers"], ["TARGET_READBACK_UNVERIFIED"])

    def test_overlapping_or_nonpositive_baseline_is_not_invented(self):
        self._install_target_and_config(baseline_window={
            "start": "2026-10-02T00:30:00Z", "end": "2026-10-02T01:30:00Z"})
        overlapping = evaluate_production_target(self.root, current_window=self.current_window)
        self.assertEqual(overlapping["status"], "BLOCKED_BASELINE_INTERVAL_UNVERIFIED")
        self.assertEqual(overlapping["blockers"], ["BASELINE_MUST_PRECEDE_CURRENT_WINDOW"])

        self._install_target_and_config()
        zero = evaluate_production_target(self.root, current_window=self.current_window)
        self.assertEqual(zero["status"], "BLOCKED_BASELINE_NOT_POSITIVE")
        self.assertEqual(zero["blockers"], ["BASELINE_HAS_NO_VERIFIED_COMPLETED_TESTS"])
        self.assertEqual(zero["baseline"]["count"], 0)
        self.assertEqual(zero["baseline"]["value"], 0.0)
        self.assertNotIn("target_met", zero)


if __name__ == "__main__":
    unittest.main()
