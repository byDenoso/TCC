from __future__ import annotations

import json
import unittest
from pathlib import Path

from runtime.nexo_execution.core import TASK_REGISTRY
from runtime.nexo_execution.peer_detection import (
    EXECUTION_ORDER,
    evaluate_gate,
    load_gate_registry,
    policy_digest,
    synthesise_detection,
)


EXPECTED_IDS = [f"D{i:02d}" for i in range(26)]
EXPECTED_ORDER = [
    "D00", "D01", "D04", "D09", "D11", "D13", "D02", "D03", "D07", "D08",
    "D05", "D06", "D18", "D19", "D20", "D21", "D15", "D16", "D17", "D22",
    "D23", "D24", "D25",
]


class PeerDetectionRegistryTests(unittest.TestCase):
    def test_registry_covers_exactly_d00_through_d25(self):
        registry = load_gate_registry()
        self.assertEqual(sorted(registry["gates"]), EXPECTED_IDS)
        self.assertEqual(EXECUTION_ORDER, EXPECTED_ORDER)
        for gate_id in EXPECTED_IDS:
            gate = registry["gates"][gate_id]
            self.assertEqual(gate["gate_id"], gate_id)
            self.assertTrue(gate["capability_id"].startswith("peer.detection."))
            self.assertTrue(gate["task_id"].startswith("peer_detection_d"))
            self.assertIn("group", gate)
            self.assertIn("evaluator", gate)

    def test_policy_digest_is_stable_sha256(self):
        first = policy_digest()
        second = policy_digest()
        self.assertEqual(first, second)
        self.assertEqual(len(first), 64)
        int(first, 16)

    def test_all_gate_task_ids_are_allowlisted_with_correct_gate_argument(self):
        registry = load_gate_registry()
        for gate_id in EXPECTED_IDS:
            task_id = registry["gates"][gate_id]["task_id"]
            self.assertIn(task_id, TASK_REGISTRY)
            argv = TASK_REGISTRY[task_id]
            self.assertEqual(argv[:3], ["python3", "-m", "benchmarks.peer_detection_gate"])
            self.assertEqual(argv[-2:], ["--gate", gate_id])


class PeerDetectionGateTests(unittest.TestCase):
    def test_d00_freeze_validates_without_external_evidence(self):
        result = evaluate_gate("D00", None)
        self.assertEqual(result["gate_status"], "PASS")
        self.assertEqual(result["nexo_verification"]["decision"], "VERIFIED")
        self.assertEqual(result["metrics"]["gate_count"], 26)

    def test_missing_required_evidence_fails_closed_as_inconclusive(self):
        result = evaluate_gate("D02", None)
        self.assertEqual(result["gate_status"], "INCONCLUSIVE")
        self.assertEqual(result["nexo_verification"]["decision"], "INCONCLUSIVE")
        self.assertIn("INPUT_BUNDLE_NOT_BOUND", result["reason_codes"])

    def test_d02_uses_boundary_aware_empirical_tail(self):
        result = evaluate_gate("D02", {"q_observed": 20.0, "q_null_max": [0.0] * 1000})
        self.assertAlmostEqual(result["metrics"]["p_global"], 1.0 / 1001.0)
        self.assertEqual(result["gate_status"], "PASS")
        self.assertTrue(result["metrics"]["passes_evidence_threshold"])

    def test_d04_requires_interior_profile_minimum(self):
        result = evaluate_gate("D04", {
            "profile": [
                {"f_peer": 0.0, "chi2": 102.0},
                {"f_peer": 0.05, "chi2": 100.0},
                {"f_peer": 0.10, "chi2": 100.5},
            ]
        })
        self.assertEqual(result["gate_status"], "PASS")
        self.assertAlmostEqual(result["metrics"]["best_f_peer"], 0.05)
        self.assertAlmostEqual(result["metrics"]["delta_chi2_f0"], 2.0)

    def test_d09_marks_anchor_conditioned_signal(self):
        result = evaluate_gate("D09", {
            "without_anchor": {"f0_excluded": False, "preferred_f": 0.0},
            "with_anchor": {"f0_excluded": True, "preferred_f": 0.08},
        })
        self.assertEqual(result["gate_status"], "FAIL")
        self.assertEqual(result["classification_hint"], "ANCHOR_CONDITIONED_SIGNAL")
        self.assertIn("ANCHOR_FREE_SIGNAL_COLLAPSES", result["reason_codes"])

    def test_d25_synthesis_anchor_conditioned_has_priority_over_peer_specific(self):
        prior = {
            gate_id: {"gate_id": gate_id, "gate_status": "PASS", "classification_hint": None}
            for gate_id in EXPECTED_IDS if gate_id != "D25"
        }
        prior["D09"] = {
            "gate_id": "D09",
            "gate_status": "FAIL",
            "classification_hint": "ANCHOR_CONDITIONED_SIGNAL",
        }
        prior["D19"] = {
            "gate_id": "D19",
            "gate_status": "PASS",
            "classification_hint": "PEER_SPECIFIC_DETECTION",
        }
        result = synthesise_detection(prior)
        self.assertEqual(result["classification"], "ANCHOR_CONDITIONED_SIGNAL")

    def test_d25_synthesis_peer_specific_requires_no_unresolved_mandatory_gate(self):
        prior = {
            gate_id: {"gate_id": gate_id, "gate_status": "PASS", "classification_hint": None}
            for gate_id in EXPECTED_IDS if gate_id != "D25"
        }
        prior["D19"]["classification_hint"] = "PEER_SPECIFIC_DETECTION"
        result = synthesise_detection(prior)
        self.assertEqual(result["classification"], "PEER_SPECIFIC_DETECTION")
        prior["D23"]["gate_status"] = "INCONCLUSIVE"
        result = synthesise_detection(prior)
        self.assertEqual(result["classification"], "INCONCLUSIVE")

    def test_gate_result_schema_is_machine_readable(self):
        result = evaluate_gate("D01", {"chi2_null": 100.0, "chi2_peer": 98.0})
        self.assertEqual(result["schema"], "peer.detection.gate-result.v1")
        self.assertEqual(result["battery_id"], "PEER_DETECTION_V1")
        self.assertEqual(result["gate_id"], "D01")
        json.dumps(result, sort_keys=True)


if __name__ == "__main__":
    unittest.main()
