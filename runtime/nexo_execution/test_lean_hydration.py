from __future__ import annotations

import unittest

from runtime.nexo_execution.dependency_producer import (
    compile_hydration_plan,
    hydrate_test_dependencies,
    validate_recipe,
)


class LeanHydrationTests(unittest.TestCase):
    def test_recipe_scientific_contract_only_requires_material_fields(self) -> None:
        recipe = {
            "schema": "nexo.dependency-producer.v1",
            "parent_test_id": "TEST::A",
            "requirements": ["materialized_table"],
            "capability_id": "producer.example",
            "repository": "byDenoso/TCC",
            "implementation_id": "example_v1",
            "scientific_contract": {
                "dataset": "DATASET-A@v1",
                "decision_rule": "hash must match frozen source",
            },
            "execution": {
                "attempt_timeout_minutes": 10,
                "resume_policy": "IDENTICAL_CONTRACT_ONLY",
            },
            "validation": {"required_outputs": ["table.dat"]},
            "binding": {
                "output_schema": "example.table.v1",
                "target_test_id": "TEST::A",
            },
        }

        result = validate_recipe(recipe)

        self.assertEqual(result["status"], "PASS")
        self.assertTrue(result["recipe_id"].startswith("RECIPE::"))

    def test_verified_inline_evidence_does_not_require_evidence_id(self) -> None:
        test = {
            "id": "TEST::A",
            "dependency_manifest": [
                {
                    "id": "DATA",
                    "required": True,
                    "status": "VERIFIED",
                    "source_ref": "drive://canonical/pantheon.dat",
                    "sha256": "abc123",
                }
            ],
        }

        plan = compile_hydration_plan(test)

        item = plan["items"][0]
        self.assertEqual(item["action"], "BIND_EXISTING")
        self.assertTrue(item["evidence_id"].startswith("EVID::"))
        self.assertEqual(plan["status"], "HYDRATE")

    def test_hydration_binds_verified_inline_evidence_and_becomes_ready(self) -> None:
        test = {
            "id": "TEST::A",
            "dependency_manifest": [
                {
                    "id": "DATA",
                    "required": True,
                    "status": "VERIFIED",
                    "source_ref": "drive://canonical/pantheon.dat",
                    "sha256": "abc123",
                }
            ],
        }

        result = hydrate_test_dependencies(test)

        dependency = result["test"]["dependency_manifest"][0]
        self.assertEqual(dependency["status"], "SATISFIED")
        self.assertEqual(dependency["binding"]["mode"], "VERIFIED_EVIDENCE_REUSE")
        self.assertTrue(dependency["binding"]["evidence_id"].startswith("EVID::"))
        self.assertTrue(result["evaluator_ready"])

    def test_missing_operational_artifact_requests_repair_not_recipe_bureaucracy(self) -> None:
        test = {
            "id": "TEST::A",
            "dependency_manifest": [
                {
                    "id": "CACHEABLE-DATA",
                    "required": True,
                    "status": "MISSING",
                    "source_ref": "https://example.invalid/frozen.dat",
                    "sha256": "abc123",
                }
            ],
        }

        plan = compile_hydration_plan(test)

        self.assertEqual(plan["items"][0]["action"], "RESOLVE_OPERATIONAL")
        self.assertEqual(plan["status"], "HYDRATE")
        self.assertNotEqual(plan["status"], "WAITING_BINDING")


if __name__ == "__main__":
    unittest.main()
