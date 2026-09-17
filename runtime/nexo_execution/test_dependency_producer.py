from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from runtime.nexo_execution.core import ExecutionContract
from runtime.nexo_execution.dependency_producer import (
    PRODUCER_IMPLEMENTATIONS,
    build_producer_envelope,
    checkpoint_compatible,
    compile_hydration_plan,
    hydrate_test_dependencies,
    producer_fingerprint,
    register_producer,
    run_recipe,
    validate_recipe,
)


def _recipe(*, implementation_id: str = "peer_anchor_ablation_native_v1"):
    return {
        "schema": "nexo.dependency-producer.v1",
        "recipe_id": "D09-PRODUCER-v1",
        "parent_test_id": "PEER-DETECTION-D09-V1",
        "requirements": ["WITHOUT_ANCHOR"],
        "capability_id": "peer.producer.anchor_ablation_native_v1",
        "repository": "byDenoso/TCC",
        "implementation_id": implementation_id,
        "scientific_contract": {
            "dataset": "DATASET-A@v1", "selection": {"sample":"matched"}, "likelihood":"LIKE-A@v1",
            "covariance":"COV-A@v1", "model":"PEER-v1", "null_or_rival":"LCDM-v1",
            "fixed_parameters":{}, "free_parameters":["f_peer"], "priors":{"f_peer":[0.0,0.2]},
            "nuisance_policy":{}, "cuts":{}, "observable":"cmb_bao", "decision_rule":"RULE-D09-v1",
            "claim_boundary":"NO_PEER_DETECTION_CLAIM",
        },
        "execution": {"attempt_timeout_minutes":180,"checkpointable":True,"resume_policy":"IDENTICAL_CONTRACT_ONLY"},
        "validation": {"required_outputs":["producer_evidence.json"],"integrity":["SHA256","NON_EMPTY_OUTPUT"]},
        "binding": {"output_schema":"peer.anchor-ablation.evidence.v1","target_test_id":"PEER-DETECTION-D09-V1"},
    }


def _hydration_test():
    return {
        "id": "TEST-H0-001",
        "status": "CHECKPOINTED",
        "dependency_manifest": [
            {"id": "DEP-DATA", "required": True, "status": "MISSING", "evidence_id": "EVID-DATA"},
            {"id": "DEP-MOCK", "required": True, "status": "MISSING", "recipe_id": "RECIPE-MOCK"},
            {"id": "DEP-OPTIONAL", "required": False, "status": "MISSING", "external_required": True},
        ],
    }


class DependencyProducerTests(unittest.TestCase):
    def test_recipe_validation_accepts_complete_recipe(self):
        self.assertEqual(validate_recipe(_recipe())["status"], "PASS")

    def test_recipe_validation_rejects_empty_scientific_contract(self):
        recipe = _recipe(); recipe["scientific_contract"] = {}
        with self.assertRaisesRegex(ValueError, "scientific_contract"):
            validate_recipe(recipe)

    def test_producer_fingerprint_changes_on_scientific_change(self):
        first = producer_fingerprint(_recipe())
        changed = _recipe(); changed["scientific_contract"]["priors"] = {"f_peer":[0.0,0.4]}
        self.assertNotEqual(producer_fingerprint(changed), first)

    def test_checkpoint_requires_identical_fingerprint_and_recipe(self):
        recipe = _recipe(); fingerprint = producer_fingerprint(recipe)
        checkpoint = {"recipe_id":recipe["recipe_id"],"producer_fingerprint":fingerprint,"status":"CHECKPOINTED"}
        self.assertTrue(checkpoint_compatible(checkpoint, recipe))
        changed = _recipe(); changed["scientific_contract"]["dataset"] = "OTHER"
        self.assertFalse(checkpoint_compatible(checkpoint, changed))

    def test_envelope_hashes_outputs_and_preserves_fingerprint(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "producer_evidence.json"; output.write_text('{"ok":true}', encoding="utf-8")
            recipe = _recipe(); envelope = build_producer_envelope(recipe, [str(output)], status="COMPLETE")
            self.assertEqual(envelope["schema"], "nexo.dependency-producer-result.v1")
            self.assertEqual(envelope["producer_fingerprint"], producer_fingerprint(recipe))
            self.assertTrue(envelope["outputs"][0]["sha256"])
            self.assertEqual(envelope["status"], "COMPLETE")

    def test_generic_dependency_producer_is_allowlisted_runtime_task(self):
        contract = ExecutionContract.from_dict({
            "schema":"nexo.execution.v1", "execution_id":"DEP-1", "work_id":"TEST-D09", "test_id":"D09",
            "provider":"local", "repository":"byDenoso/TCC", "commit_sha":"abc",
            "task_id":"dependency_producer", "parameters":{"recipe_path":"recipe.json"}, "seed":None,
            "timeout_minutes":5, "required_outputs":["dependency_producer_result.json"],
        })
        self.assertEqual(contract.task_id, "dependency_producer")

    def test_register_producer_enables_allowlisted_recipe_execution(self):
        implementation_id = "test_emit_evidence_v1"
        previous = PRODUCER_IMPLEMENTATIONS.get(implementation_id)
        try:
            with tempfile.TemporaryDirectory() as directory:
                def emit(recipe):
                    path = Path(directory) / "producer_evidence.json"
                    path.write_text('{"ok":true}', encoding="utf-8")
                    return [str(path)]

                register_producer(implementation_id, emit)
                recipe = _recipe(implementation_id=implementation_id)
                result = run_recipe(recipe)
                self.assertEqual(result["status"], "COMPLETE")
                self.assertEqual(result["missing_required_outputs"], [])
        finally:
            if previous is None:
                PRODUCER_IMPLEMENTATIONS.pop(implementation_id, None)
            else:
                PRODUCER_IMPLEMENTATIONS[implementation_id] = previous

    def test_hydration_plan_reuses_existing_evidence_and_schedules_only_missing_dependency(self):
        plan = compile_hydration_plan(
            _hydration_test(),
            canonical_evidence={"EVID-DATA": {"status": "VALIDATED", "sha256": "abc123"}},
            recipes={"RECIPE-MOCK": {"state": "READY"}},
        )
        actions = {item["dependency_id"]: item["action"] for item in plan["items"]}
        self.assertEqual(actions["DEP-DATA"], "BIND_EXISTING")
        self.assertEqual(actions["DEP-MOCK"], "PRODUCE")
        self.assertEqual(actions["DEP-OPTIONAL"], "BLOCKED_EXTERNAL")
        self.assertEqual(plan["status"], "HYDRATE")

    def test_hydration_is_ready_when_required_dependencies_are_satisfied(self):
        test = _hydration_test()
        for item in test["dependency_manifest"]:
            if item["required"]:
                item["status"] = "SATISFIED"
        plan = compile_hydration_plan(test, canonical_evidence={}, recipes={})
        self.assertEqual(plan["status"], "READY_FOR_EVALUATOR")
        self.assertTrue(plan["evaluator_ready"])

    def test_hydration_binds_reused_and_produced_evidence_without_optional_blocker_stopping_lane(self):
        implementation_id = "test_hydrate_emit_v1"
        previous = PRODUCER_IMPLEMENTATIONS.get(implementation_id)
        try:
            with tempfile.TemporaryDirectory() as directory:
                def emit(recipe):
                    path = Path(directory) / "producer_evidence.json"
                    path.write_text('{"mock":true}', encoding="utf-8")
                    return [str(path)]

                register_producer(implementation_id, emit)
                recipe = _recipe(implementation_id=implementation_id)
                recipe["recipe_id"] = "RECIPE-MOCK"
                recipe["parent_test_id"] = "TEST-H0-001"
                recipe["binding"]["target_test_id"] = "TEST-H0-001"

                hydrated = hydrate_test_dependencies(
                    _hydration_test(),
                    canonical_evidence={"EVID-DATA": {"status": "VALIDATED", "sha256": "abc123"}},
                    recipes={"RECIPE-MOCK": recipe},
                )
                dependencies = {item["id"]: item for item in hydrated["test"]["dependency_manifest"]}
                self.assertEqual(dependencies["DEP-DATA"]["status"], "SATISFIED")
                self.assertEqual(dependencies["DEP-MOCK"]["status"], "SATISFIED")
                self.assertEqual(dependencies["DEP-OPTIONAL"]["status"], "BLOCKED_EXTERNAL")
                self.assertTrue(hydrated["evaluator_ready"])
        finally:
            if previous is None:
                PRODUCER_IMPLEMENTATIONS.pop(implementation_id, None)
            else:
                PRODUCER_IMPLEMENTATIONS[implementation_id] = previous


if __name__ == "__main__":
    unittest.main()
