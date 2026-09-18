import unittest

from runtime.nexo_execution.generic_contract import evaluate_contract


FROZEN = {
    "id": "T-GENERIC-001",
    "method": {
        "mechanism": "GENERIC_LIGHTWEIGHT_TEST",
        "input_contract": {"dataset": "bound-by-hash"},
        "estimator_contract": {"primary": "direct matrix arithmetic"},
        "null_contract": {"primary": "frozen null"},
    },
    "decision_rule": {"CONSISTENT": "frozen decision rule"},
    "outputs": ["scientific_result"],
    "claim_boundary": "No broader claim.",
}


class GenericContractExecutorTests(unittest.TestCase):
    def test_missing_numeric_binding_is_scientific_definition_blocker(self):
        result = evaluate_contract(FROZEN, {})
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["reason_code"], "SCIENTIFIC_DEFINITION_MISSING")
        self.assertFalse(result["scientific_claim_promoted"])

    def test_quadratic_form_executes_with_frozen_decision_key(self):
        result = evaluate_contract(FROZEN, {
            "operation": "quadratic_form",
            "residual": [1.0, 2.0],
            "precision": [[1.0, 0.0], [0.0, 1.0]],
            "decision": "CONSISTENT",
            "input_refs": [{"ref": "sha256:abc", "sha256": "abc"}],
        })
        self.assertEqual(result["status"], "DONE")
        self.assertEqual(result["statistics"]["chi2"], 5.0)
        self.assertEqual(result["decision"], "CONSISTENT")
        self.assertEqual(result["evidence_level"], "NATIVE_NUMERIC")

    def test_unfrozen_decision_is_rejected(self):
        result = evaluate_contract(FROZEN, {
            "operation": "quadratic_form",
            "residual": [1.0],
            "precision": [[1.0]],
            "decision": "INVENTED",
            "input_refs": [{"ref": "sha256:abc", "sha256": "abc"}],
        })
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["reason_code"], "FROZEN_CONTRACT_CONFLICT")

    def test_fixed_trajectory_compares_candidates(self):
        result = evaluate_contract(FROZEN, {
            "operation": "fixed_trajectory_chi_square",
            "observed": [1.0, 2.0],
            "precision": [[1.0, 0.0], [0.0, 1.0]],
            "trajectories": {"null": [1.0, 1.0], "rival": [0.0, 0.0]},
            "decision": "CONSISTENT",
            "input_refs": [{"ref": "sha256:abc", "sha256": "abc"}],
        })
        self.assertEqual(result["statistics"]["chi2"], {"null": 1.0, "rival": 5.0})

    def test_gls_profiles_linear_model(self):
        result = evaluate_contract(FROZEN, {
            "operation": "gls",
            "observed": [1.0, 3.0],
            "design": [[1.0, 0.0], [1.0, 1.0]],
            "precision": [[1.0, 0.0], [0.0, 1.0]],
            "decision": "CONSISTENT",
            "input_refs": [{"ref": "sha256:abc", "sha256": "abc"}],
        })
        self.assertEqual(result["statistics"]["coefficients"], [1.0, 2.0])
        self.assertAlmostEqual(result["statistics"]["chi2"], 0.0)

    def test_quadrature_bootstrap_and_jackknife_are_deterministic(self):
        common = {
            "decision": "CONSISTENT",
            "input_refs": [{"ref": "sha256:abc", "sha256": "abc"}],
        }
        quad = evaluate_contract(FROZEN, {**common, "operation": "quadrature_1d", "x": [0, 1, 2], "y": [0, 1, 2]})
        jack = evaluate_contract(FROZEN, {**common, "operation": "jackknife_mean", "values": [1, 2, 3]})
        boot_a = evaluate_contract(FROZEN, {**common, "operation": "bootstrap_mean", "values": [1, 2, 3], "resamples": 20, "seed": 7})
        boot_b = evaluate_contract(FROZEN, {**common, "operation": "bootstrap_mean", "values": [1, 2, 3], "resamples": 20, "seed": 7})
        self.assertEqual(quad["statistics"]["integral"], 2.0)
        self.assertAlmostEqual(jack["statistics"]["estimate"], 2.0)
        self.assertEqual(boot_a["statistics"], boot_b["statistics"])

    def test_published_summary_is_explicitly_labeled(self):
        result = evaluate_contract(FROZEN, {
            "operation": "published_summary",
            "statistics": {"global_p": None, "finding": "reconstruction-sensitive"},
            "decision": "CONSISTENT",
            "evidence_level": "SUMMARY_LEVEL",
            "input_refs": [{"ref": "arxiv:2601.00001v2", "sha256": "abc"}],
        })
        self.assertEqual(result["status"], "DONE")
        self.assertEqual(result["evidence_level"], "SUMMARY_LEVEL")
        self.assertIsNone(result["statistics"]["global_p"])


if __name__ == "__main__":
    unittest.main()
