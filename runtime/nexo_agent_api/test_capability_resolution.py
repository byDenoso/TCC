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

    def test_exact_task_id_reuses_existing_capability(self) -> None:
        result = CapabilityExecutionResolver(self.capabilities).resolve({"task_id": "known_task"})

        self.assertEqual(result["status"], "RESOLVED")
        self.assertEqual(result["capability_id"], "known_task")
        self.assertEqual(result["task_id"], "known_task")
        self.assertEqual(result["backend"], "github_dispatch")

    def test_semantic_requirements_resolve_compatible_executor(self) -> None:
        result = CapabilityExecutionResolver(self.capabilities).resolve(
            {
                "required_capabilities": [
                    "science.mock_observer",
                    "science.selection_forward",
                ]
            }
        )

        self.assertEqual(result["status"], "RESOLVED")
        self.assertEqual(result["capability_id"], "mock_observer_v1")
        self.assertEqual(result["task_id"], "mock_observer_runtime")

    def test_unknown_semantic_requirement_needs_adapter(self) -> None:
        result = CapabilityExecutionResolver(self.capabilities).resolve(
            {"required_capabilities": ["science.extreme_value"]}
        )

        self.assertEqual(result["status"], "NEEDS_ADAPTER")
        self.assertIn("science.extreme_value", result["reason"])
        self.assertNotIn("task_id", result)

    def test_explicit_blocker_prevents_resolution(self) -> None:
        result = CapabilityExecutionResolver(self.capabilities).resolve(
            {"task_id": "known_task", "blocker": "missing credential"}
        )

        self.assertEqual(result["status"], "BLOCKED")


if __name__ == "__main__":
    unittest.main()
