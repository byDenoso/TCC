from __future__ import annotations

import unittest

from .capability_resolution import CapabilityExecutionResolver


class CapabilityExecutionResolverTests(unittest.TestCase):
    def setUp(self) -> None:
        self.capabilities = {
            "known_task": {
                "roles": ["EXECUTOR"],
                "backend": "github_dispatch",
                "task_id": "known_task",
                "status": "PROVEN",
            },
            "mock_observer_v1": {
                "roles": ["EXECUTOR"],
                "backend": "github_dispatch",
                "task_id": "mock_observer_runtime",
                "status": "ACTIVE",
                "semantic_capabilities": [
                    "science.mock_observer",
                    "science.selection_forward",
                ],
            },
        }

    @staticmethod
    def frozen_test() -> dict:
        return {
            "id": "T-FROZEN",
            "execution_class": "LIGHTWEIGHT_ANALYTIC_NO_HEAVY_MCMC",
            "mechanism": "FROZEN_ANALYTIC_TEST",
            "input_contract": {"dataset": "frozen"},
            "estimator_contract": {"primary": "GLS"},
            "decision_contract": {"PASS": "p>=0.05"},
            "claim_boundary": "No broader claim.",
        }

    def test_exact_task_id_reuses_existing_capability(self) -> None:
        result = CapabilityExecutionResolver(self.capabilities).resolve({"task_id": "known_task"})
        self.assertEqual(result["status"], "RESOLVED")
        self.assertEqual(result["capability_id"], "known_task")
        self.assertEqual(result["task_id"], "known_task")
        self.assertEqual(result["backend"], "github_dispatch")

    def test_runtime_allowlisted_task_does_not_require_manifest_duplicate(self) -> None:
        result = CapabilityExecutionResolver(self.capabilities).resolve({"task_id": "h0_lcdm_origin"})
        self.assertEqual(result["status"], "RESOLVED")
        self.assertEqual(result["task_id"], "h0_lcdm_origin")
        self.assertEqual(result["capability_id"], "runtime::h0_lcdm_origin")
        self.assertEqual(result["resolution_source"], "runtime_registry")

    def test_semantic_requirements_resolve_compatible_executor(self) -> None:
        result = CapabilityExecutionResolver(self.capabilities).resolve(
            {"required_capabilities": ["science.mock_observer", "science.selection_forward"]}
        )
        self.assertEqual(result["status"], "RESOLVED")
        self.assertEqual(result["capability_id"], "mock_observer_v1")
        self.assertEqual(result["task_id"], "mock_observer_runtime")

    def test_complete_frozen_contract_without_capability_is_repair_required(self) -> None:
        result = CapabilityExecutionResolver(self.capabilities).resolve(self.frozen_test())
        self.assertEqual(result["status"], "REPAIR_REQUIRED")
        self.assertEqual(result["reason_code"], "CAPABILITY_REPAIR_REQUIRED")
        self.assertTrue(result["repairable"])
        self.assertTrue(result["repair_contract"]["same_pulse"])
        self.assertEqual(result["repair_contract"]["mechanism"], "FROZEN_ANALYTIC_TEST")
        self.assertEqual(result["repair_contract"]["target_repository"], "byDenoso/TCC")

    def test_nested_work_frozen_contract_without_capability_is_repair_required(self) -> None:
        result = CapabilityExecutionResolver(self.capabilities).resolve({
            "id": "WORK::T-FROZEN",
            "execution_class": "LIGHTWEIGHT_ANALYTIC_NO_HEAVY_MCMC",
            "frozen_test": {
                "id": "T-FROZEN",
                "method": {"mechanism": "FROZEN_ANALYTIC_TEST"},
                "decision_rule": {"PASS": "p>=0.05"},
                "outputs": ["scientific_result"],
                "claim_boundary": "No broader claim.",
            },
        })
        self.assertEqual(result["status"], "REPAIR_REQUIRED")
        self.assertEqual(result["repair_contract"]["test_id"], "T-FROZEN")

    def test_unknown_semantic_requirement_with_frozen_contract_is_repair_required(self) -> None:
        payload = self.frozen_test()
        payload["required_capabilities"] = ["science.extreme_value"]
        result = CapabilityExecutionResolver(self.capabilities).resolve(payload)
        self.assertEqual(result["status"], "REPAIR_REQUIRED")
        self.assertEqual(result["repair_contract"]["missing_capabilities"], ["science.extreme_value"])

    def test_incomplete_unknown_semantic_requirement_still_needs_adapter(self) -> None:
        result = CapabilityExecutionResolver(self.capabilities).resolve(
            {"required_capabilities": ["science.extreme_value"]}
        )
        self.assertEqual(result["status"], "NEEDS_ADAPTER")
        self.assertIn("science.extreme_value", result["reason"])
        self.assertNotIn("task_id", result)

    def test_legitimate_blocker_prevents_resolution(self) -> None:
        result = CapabilityExecutionResolver(self.capabilities).resolve({
            "task_id": "known_task",
            "blocker_class": "AUTHORIZATION_MISSING",
            "blocker": "missing credential",
        })
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["reason_code"], "AUTHORIZATION_MISSING")

    def test_legacy_administrative_blocker_text_does_not_prevent_resolution(self) -> None:
        result = CapabilityExecutionResolver(self.capabilities).resolve(
            {"task_id": "known_task", "blocker": "recipe_id missing"}
        )
        self.assertEqual(result["status"], "RESOLVED")
        self.assertEqual(result["task_id"], "known_task")


if __name__ == "__main__":
    unittest.main()
