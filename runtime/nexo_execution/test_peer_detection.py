from __future__ import annotations

import json
import unittest

from runtime.nexo_execution.core import TASK_REGISTRY
from runtime.nexo_execution.peer_detection import EXECUTION_ORDER, evaluate_gate, load_gate_registry, policy_digest, synthesise_detection

EXPECTED_IDS = [f"D{i:02d}" for i in range(26)]
EXPECTED_ORDER = [
    "D00", "D01", "D04", "D09", "D10", "D11", "D12", "D13", "D14", "D02",
    "D03", "D07", "D08", "D05", "D06", "D18", "D19", "D20", "D21", "D15",
    "D16", "D17", "D22", "D23", "D24", "D25",
]


def passing_evidence():
    zero_null = [0.0] * 1000
    return {
        "D01": {"chi2_null": 100.0, "chi2_peer": 98.0},
        "D02": {"q_observed": 20.0, "q_null_max": zero_null},
        "D03": {"q_local": 20.0, "q_null_scan_max": zero_null, "look_elsewhere_corrected": True},
        "D04": {"profile": [{"f_peer": 0.0, "chi2": 102.0}, {"f_peer": 0.05, "chi2": 100.0}, {"f_peer": 0.10, "chi2": 100.5}]},
        "D05": {"delta_lnZ": 6.0},
        "D06": {"runs": [{"classification": "PEER_SPECIFIC_DETECTION"}, {"classification": "PEER_SPECIFIC_DETECTION"}]},
        "D07": {"bias_sigma": 0.1, "coverage68": 0.68, "coverage95": 0.95, "fpr": 0.02, "fnr": 0.1},
        "D08": {"rank_uniformity_p": 0.4, "coverage68": 0.68, "coverage95": 0.95},
        "D09": {"without_anchor": {"f0_excluded": True, "preferred_f": 0.05}, "with_anchor": {"f0_excluded": True, "preferred_f": 0.08}},
        "D10": {"fits": {"no_anchor": {"f0_excluded": True, "preferred_f": 0.05}, "cepheid": {"f0_excluded": True, "preferred_f": 0.08}, "trgb": {"f0_excluded": True, "preferred_f": 0.06}}},
        "D11": {"estimates": [{"name": "Planck", "value": 0.05, "sigma": 0.02}, {"name": "ACT", "value": 0.055, "sigma": 0.02}, {"name": "SPT", "value": 0.045, "sigma": 0.02}]},
        "D12": {"contributions": {"TT": 2.0, "TE": 2.0, "EE": 2.0, "lensing": 1.0, "low_l": 1.0}, "single_block_creates_signal": False},
        "D13": {"runs": [{"signal_survives": True}, {"signal_survives": True}], "manufactured_by_single_tracer": False},
        "D14": {"datasets": [{"classification": "PEER_SPECIFIC_DETECTION"}, {"classification": "PEER_SPECIFIC_DETECTION"}, {"classification": "PEER_SPECIFIC_DETECTION"}]},
        "D15": {"max_new_tension_sigma": 1.5, "catastrophic_degradation": False},
        "D16": {"p_values": {"CMB": 0.5, "BAO": 0.4, "SN": 0.6}},
        "D17": {"delta_elpd": 4.0, "se": 2.0},
        "D18": {"delta_ic_peer_minus_rival": -3.0},
        "D19": {"peer_specific": True, "early_sector_supported": True},
        "D20": {"peer_specific": True, "early_sector_supported": True},
        "D21": {"peer_required": True, "early_sector_supported": True, "delta_ic_peer_minus_rival": -3.0},
        "D22": {"shifts_sigma": [0.1, -0.2, 0.3]},
        "D23": {"max_shift_sigma": 0.05, "delta_chi2": 0.02},
        "D24": {"run_count": 5, "basin_dispersion_sigma": 0.2, "same_physical_basin": True},
    }


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
        first = policy_digest(); second = policy_digest()
        self.assertEqual(first, second); self.assertEqual(len(first), 64); int(first, 16)

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
        result = evaluate_gate("D02", passing_evidence()["D02"])
        self.assertAlmostEqual(result["metrics"]["p_global"], 1.0 / 1001.0)
        self.assertEqual(result["gate_status"], "PASS")
        self.assertTrue(result["metrics"]["passes_evidence_threshold"])

    def test_d04_requires_interior_profile_minimum(self):
        result = evaluate_gate("D04", passing_evidence()["D04"])
        self.assertEqual(result["gate_status"], "PASS")
        self.assertAlmostEqual(result["metrics"]["best_f_peer"], 0.05)
        self.assertAlmostEqual(result["metrics"]["delta_chi2_f0"], 2.0)

    def test_d09_marks_anchor_conditioned_signal(self):
        result = evaluate_gate("D09", {"without_anchor": {"f0_excluded": False, "preferred_f": 0.0}, "with_anchor": {"f0_excluded": True, "preferred_f": 0.08}})
        self.assertEqual(result["gate_status"], "FAIL")
        self.assertEqual(result["classification_hint"], "ANCHOR_CONDITIONED_SIGNAL")
        self.assertIn("ANCHOR_FREE_SIGNAL_COLLAPSES", result["reason_codes"])

    def test_every_gate_has_a_conclusive_valid_fixture(self):
        fixtures = passing_evidence()
        results = {"D00": evaluate_gate("D00", None)}
        for gate_id in EXPECTED_IDS[1:-1]:
            result = evaluate_gate(gate_id, fixtures[gate_id])
            self.assertNotEqual(result["gate_status"], "INCONCLUSIVE", gate_id)
            self.assertEqual(result["nexo_verification"]["status"], "PASS", gate_id)
            results[gate_id] = result
        d25 = evaluate_gate("D25", {"results": results})
        self.assertNotEqual(d25["gate_status"], "INCONCLUSIVE")
        self.assertEqual(d25["classification_hint"], "PEER_SPECIFIC_DETECTION")

    def test_d25_synthesis_anchor_conditioned_has_priority_over_peer_specific(self):
        prior = {gate_id: {"gate_id": gate_id, "gate_status": "PASS", "classification_hint": None} for gate_id in EXPECTED_IDS if gate_id != "D25"}
        prior["D09"] = {"gate_id": "D09", "gate_status": "FAIL", "classification_hint": "ANCHOR_CONDITIONED_SIGNAL"}
        prior["D19"] = {"gate_id": "D19", "gate_status": "PASS", "classification_hint": "PEER_SPECIFIC_DETECTION"}
        self.assertEqual(synthesise_detection(prior)["classification"], "ANCHOR_CONDITIONED_SIGNAL")

    def test_d25_synthesis_peer_specific_requires_no_unresolved_mandatory_gate(self):
        prior = {gate_id: {"gate_id": gate_id, "gate_status": "PASS", "classification_hint": None} for gate_id in EXPECTED_IDS if gate_id != "D25"}
        prior["D19"]["classification_hint"] = "PEER_SPECIFIC_DETECTION"
        self.assertEqual(synthesise_detection(prior)["classification"], "PEER_SPECIFIC_DETECTION")
        prior["D23"]["gate_status"] = "INCONCLUSIVE"
        self.assertEqual(synthesise_detection(prior)["classification"], "INCONCLUSIVE")

    def test_gate_result_schema_is_machine_readable(self):
        result = evaluate_gate("D01", passing_evidence()["D01"])
        self.assertEqual(result["schema"], "peer.detection.gate-result.v1")
        self.assertEqual(result["battery_id"], "PEER_DETECTION_V1")
        self.assertEqual(result["gate_id"], "D01")
        json.dumps(result, sort_keys=True)


if __name__ == "__main__": unittest.main()
