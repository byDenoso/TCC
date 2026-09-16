from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from runtime.nexo_execution.dependency_producer import (
    build_producer_envelope,
    checkpoint_compatible,
    producer_fingerprint,
    validate_recipe,
)


def _recipe():
    return {
        "schema": "nexo.dependency-producer.v1",
        "recipe_id": "D09-PRODUCER-v1",
        "parent_test_id": "PEER-DETECTION-D09-V1",
        "requirements": ["WITHOUT_ANCHOR"],
        "capability_id": "peer.producer.anchor_ablation_native_v1",
        "repository": "byDenoso/TCC",
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


if __name__ == "__main__":
    unittest.main()
