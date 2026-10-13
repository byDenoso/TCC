from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from runtime.nexo_agent_api.frontier import _lifecycle, _resume_evidence, roadmap_frontier
from runtime.nexo_agent_api.scientific_integrity import execution_fingerprint
from runtime.nexo_agent_api.tower_paths import entity_path


class FrontierEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        for folder in ("indexes", "roadmaps", "entities/test", "evolution"):
            (self.root / folder).mkdir(parents=True, exist_ok=True)
        self._write("indexes/active-roadmaps.json", {"items": [
            {"roadmap_id": "RM-A", "state": "ACTIVE", "priority": "P0"}]})
        self._write("roadmaps/RM-A.json", {"roadmap_id": "RM-A", "frontier_refs": ["T-A"]})

    def _write(self, relative, value):
        (self.root / relative).write_text(json.dumps(value), encoding="utf-8")

    def _test(self, value):
        entity_path(self.root, "test", value["id"]).write_text(json.dumps(value), encoding="utf-8")

    @staticmethod
    def _started(state="RUNNING"):
        return {
            "id": "T-A",
            "state": state,
            "execution_observation": "GITHUB_JOB_STEP",
            "started_at": "2026-10-04T12:00:00Z",
            "run_ref": "actions/runs/123",
        }

    def _reserve(self, test):
        test.update({
            "battery_id": "BAT-A",
            "attempt_id": "attempt-11111111111111111111111111111111",
            "prereg_hash": "frozen-design",
            "recipe": "recipe_a",
            "recipe_params": {"seed": 7},
            "execution_recipe_sha256": "a" * 64,
            "data_binding": {"inputs": [{"uri": "public/input", "sha256": "b" * 64}]},
        })
        spec = {
            "test_id": test["id"],
            "attempt_id": test["attempt_id"],
            "prereg_hash": test["prereg_hash"],
            "recipe": test["recipe"],
            "params": test["recipe_params"],
            "recipe_sha256": test["execution_recipe_sha256"],
            "inputs": test["data_binding"]["inputs"],
        }
        spec["execution_fingerprint"] = execution_fingerprint(test, spec["recipe_sha256"])
        self._write("evolution/batteries.json", {"batteries": [{"id": "BAT-A", "tests": [spec]}]})

    def test_missing_record_is_missing_not_ready(self):
        self.assertEqual(_lifecycle(None), "MISSING")

    def test_record_without_lifecycle_is_unknown(self):
        self.assertEqual(_lifecycle({"id": "T-A"}), "UNKNOWN")

    def test_indexed_unknown_record_does_not_enter_batch(self):
        self._test({"id": "T-A"})
        value = roadmap_frontier(self.root)
        self.assertEqual(value["ready"], [])
        self.assertEqual(value["batch"], [])
        self.assertEqual(value["waiting"][0]["reason"], "NOT_READY_UNKNOWN")

    def test_explicit_ready_and_dependencies_are_preserved(self):
        self._test({"id": "T-A", "state": "READY", "depends_on": ["T-B"]})
        self._test({"id": "T-B", "state": "DONE"})
        self.assertEqual(roadmap_frontier(self.root)["next"]["test_id"], "T-A")

    def test_unknown_dependency_is_not_terminal(self):
        self._test({"id": "T-A", "state": "READY", "depends_on": ["T-B"]})
        self._test({"id": "T-B"})
        self.assertEqual(roadmap_frontier(self.root)["waiting"][0]["waiting_on"], ["T-B"])

    def test_checkpoint_without_proof_is_review_only(self):
        self._test({"id": "T-A", "state": "CHECKPOINTED"})
        value = roadmap_frontier(self.root)
        self.assertEqual(value["state"], "WAIT_DEPENDENCY")
        self.assertIsNone(value["next"])
        self.assertEqual(value["batch"], [])
        self.assertEqual(value["resumable"], [])
        self.assertEqual(value["resume_candidates"][0]["test_id"], "T-A")
        self.assertEqual(value["checkpoint_review"][0]["test_id"], "T-A")
        evidence = value["resume_evidence_missing"][0]["resume_evidence"]
        self.assertEqual(evidence["missing_evidence"], [
            "EXECUTION_START_EVIDENCE_MISSING",
            "CANONICAL_ATTEMPT_RESERVATION_MISSING",
            "CHECKPOINT_REFERENCE_MISSING",
        ])
        self.assertFalse(evidence["execution_authorized"])

    def test_recorded_start_and_checkpoint_without_reservation_still_waits(self):
        test = {**self._started("CHECKPOINTED"), "checkpoint_ref": "artifact:checkpoint-1"}
        self._test(test)
        value = roadmap_frontier(self.root)
        self.assertEqual(value["resumable"], [])
        self.assertEqual(value["batch"], [])
        self.assertEqual(
            value["resume_evidence_missing"][0]["resume_evidence"]["missing_evidence"],
            ["CANONICAL_ATTEMPT_RESERVATION_MISSING"],
        )

    def test_exact_reservation_makes_running_a_static_candidate_only(self):
        test = self._started()
        self._reserve(test)
        self._test(test)
        self._write("roadmaps/RM-A.json", {"roadmap_id": "RM-A", "frontier_refs": ["T-A", "T-READY"]})
        self._test({"id": "T-READY", "state": "READY"})
        value = roadmap_frontier(self.root)
        self.assertEqual(value["state"], "RESUME_EXISTING")
        self.assertEqual(value["next"]["test_id"], "T-A")
        self.assertEqual(value["batch"][0]["test_id"], "T-A")
        evidence = value["resumable"][0]["resume_evidence"]
        self.assertTrue(evidence["static_resume_candidate"])
        self.assertEqual(evidence["action"], "VERIFY_RUNTIME_BEFORE_RESUME")
        self.assertFalse(evidence["execution_authorized"])

    def test_exact_reservation_and_reference_make_checkpoint_a_static_candidate(self):
        test = {**self._started("CHECKPOINTED"), "checkpoint_ref": "artifact:checkpoint-1"}
        self._reserve(test)
        self._test(test)
        value = roadmap_frontier(self.root)
        self.assertEqual(value["state"], "RESUME_EXISTING")
        self.assertEqual(value["resumable"][0]["test_id"], "T-A")
        self.assertEqual(value["resume_evidence_missing"], [])

    def test_changed_binding_invalidates_existing_reservation(self):
        test = {**self._started("CHECKPOINTED"), "checkpoint_ref": "artifact:checkpoint-1"}
        self._reserve(test)
        test["recipe_params"] = {"seed": 8}
        self._test(test)
        value = roadmap_frontier(self.root)
        self.assertEqual(value["resumable"], [])
        self.assertIn(
            "CANONICAL_ATTEMPT_RESERVATION_MISSING",
            value["resume_evidence_missing"][0]["resume_evidence"]["missing_evidence"],
        )

    def test_missing_timezone_or_invalid_run_does_not_prove_start(self):
        for change in ({"started_at": "2026-10-04T12:00:00"}, {"run_ref": "actions/runs/0"},
                       {"run_ref": "https://example.com/actions/runs/123"},
                       {"execution_observation": "QUEUED"}):
            with self.subTest(change=change):
                evidence = _resume_evidence(self.root, {**self._started(), **change})
                self.assertFalse(evidence["recorded_start_verified"])

    def test_blank_and_non_string_checkpoint_are_not_references(self):
        for checkpoint in ("", "  ", None, {}, 123):
            with self.subTest(checkpoint=checkpoint):
                evidence = _resume_evidence(
                    self.root,
                    {**self._started("CHECKPOINTED"), "checkpoint_ref": checkpoint},
                )
                self.assertIn("CHECKPOINT_REFERENCE_MISSING", evidence["missing_evidence"])

    def test_inspection_does_not_mutate_canonical_files(self):
        entity = self._started("CHECKPOINTED")
        before = copy.deepcopy(entity)
        self._test(entity)
        raw_before = entity_path(self.root, "test", "T-A").read_bytes()
        roadmap_frontier(self.root)
        self.assertEqual(entity_path(self.root, "test", "T-A").read_bytes(), raw_before)
        self.assertEqual(entity, before)


if __name__ == "__main__":
    unittest.main()
