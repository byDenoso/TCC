from __future__ import annotations

import copy
import unittest

from benchmarks.megastructure_round12 import (
    FROZEN_ENSEMBLES,
    DETECTOR_CONTRACT,
    evaluate_admission_gate,
    evaluate_detector_contract,
)


class MegastructureRound12Tests(unittest.TestCase):
    def test_gate_147_passes_complete_frozen_metadata(self):
        result = evaluate_admission_gate(FROZEN_ENSEMBLES)
        self.assertEqual(result["gate_id"], "T-MEGA26-LCDM-DATA-FREEZE-147")
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["ensemble_names"], ["EuclidLargeBox", "FLAMINGO-10K"])
        self.assertEqual(result["unresolved_required_fields"], [])

    def test_gate_147_fails_closed_when_required_metadata_is_missing(self):
        broken = copy.deepcopy(FROZEN_ENSEMBLES)
        broken["FLAMINGO-10K"].pop("matter_products")
        result = evaluate_admission_gate(broken)
        self.assertEqual(result["status"], "FAIL")
        self.assertIn("FLAMINGO-10K.matter_products", result["unresolved_required_fields"])

    def test_gate_148_freezes_detector_contract(self):
        result = evaluate_detector_contract(DETECTOR_CONTRACT)
        self.assertEqual(result["gate_id"], "T-MEGA26-LCDM-DETECTOR-CONTRACT-148")
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["fof_grid_b_over_b0"], [0.8, 0.9, 1.0, 1.1, 1.2])
        self.assertEqual(
            result["families"],
            ["FOF_SLHC", "MST_GRAPH", "CONTINUOUS_MATTER"],
        )
        self.assertEqual(result["primary_observable"], "L_span")


if __name__ == "__main__":
    unittest.main()
