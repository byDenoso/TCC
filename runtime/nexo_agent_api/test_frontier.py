from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from runtime.nexo_agent_api.evolution import evolution_status
from runtime.nexo_agent_api.frontier import roadmap_frontier
from runtime.nexo_agent_api.tower_paths import entity_path


class FrontierTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "indexes").mkdir()
        (self.root / "roadmaps").mkdir()
        (self.root / "entities" / "test").mkdir(parents=True)
        (self.root / "evolution").mkdir()

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _index(self, *items):
        (self.root / "indexes" / "active-roadmaps.json").write_text(json.dumps({"items": list(items)}))

    def _roadmap(self, rid, **body):
        (self.root / "roadmaps" / f"{rid}.json").write_text(json.dumps({"roadmap_id": rid, **body}))

    def _test(self, tid, state, **body):
        entity_path(self.root, "test", tid).write_text(json.dumps({"id": tid, "state": state, **body}))

    def test_v2_frontier_refs_and_one_of_dependencies(self):
        self._index({"roadmap_id": "RM-A", "state": "ACTIVE", "priority": "P0", "relative_path": "roadmaps/RM-A.json"})
        self._roadmap("RM-A", frontier_refs=["T1", "T2", "T3", "T4"])
        self._test("T1", "DONE")
        self._test("T2", "READY")
        self._test("T3", "READY", depends_on=["T1", "ONE_OF:T2|T9"])
        self._test("T4", "READY", depends_on=["T1", "ONE_OF:T1|T2"])
        frontier = roadmap_frontier(self.root)
        self.assertEqual(frontier["state"], "EXECUTE_READY")
        self.assertEqual([r["test_id"] for r in frontier["ready"]], ["T2", "T4"])
        self.assertEqual(frontier["waiting"][0]["test_id"], "T3")

    def test_ready_beats_checkpointed_and_bad_roadmaps_are_not_fatal(self):
        self._index(
            {"roadmap_id": "RM-EMPTY", "state": "ACTIVE", "priority": "P0", "relative_path": "roadmaps/RM-EMPTY.json"},
            {"roadmap_id": "RM-V1", "state": "ACTIVE", "priority": "P1", "relative_path": "roadmaps/RM-V1.json"},
            {"roadmap_id": "RM-OFF", "state": "PLANNED", "relative_path": "roadmaps/RM-OFF.json"},
        )
        self._roadmap("RM-EMPTY")
        self._roadmap("RM-V1", tests=[{"roadmap_test_id": "TEST::X"}, {"roadmap_test_id": "TEST::Y"}])
        self._test("TEST::X", "READY")
        self._test("TEST::Y", "CHECKPOINTED")
        frontier = roadmap_frontier(self.root)
        self.assertEqual(frontier["state"], "EXECUTE_READY")
        self.assertEqual(frontier["next"]["test_id"], "TEST::X")
        self.assertEqual(frontier["batch"][0]["test_id"], "TEST::X")
        self.assertEqual(frontier["resumable"][0]["test_id"], "TEST::Y")
        self.assertEqual(frontier["skipped_roadmaps"][0]["reason"], "ACTIVE_ROADMAP_WITHOUT_TESTS")


    def test_running_still_beats_ready(self):
        self._index({"roadmap_id": "RM-A", "state": "ACTIVE", "priority": "P0", "relative_path": "roadmaps/RM-A.json"})
        self._roadmap("RM-A", frontier_refs=["T-RUN", "T-READY"])
        self._test("T-RUN", "RUNNING")
        self._test("T-READY", "READY")
        frontier = roadmap_frontier(self.root)
        self.assertEqual(frontier["state"], "RESUME_EXISTING")
        self.assertEqual(frontier["next"]["test_id"], "T-RUN")
        self.assertEqual(frontier["batch"][0]["test_id"], "T-RUN")

    def test_status_lists_non_closed_roadmaps_not_only_chartered(self):
        self._roadmap("RM-PROPOSED", state="ACTIVE", campaign_id="CAMP-P", charter={"status": "PROPOSED"}, frontier_refs=["T-P"])
        self._roadmap("RM-CHARTERED", state="ACTIVE", campaign_id="CAMP-C", charter={"status": "CHARTERED"}, frontier_refs=["T-C"])
        self._roadmap("RM-CLOSED", state="CLOSED", campaign_id="CAMP-X", charter={"status": "CLOSED"}, frontier_refs=[])
        self._test("T-P", "READY", roadmap_id="RM-PROPOSED")
        self._test("T-C", "CHECKPOINTED", roadmap_id="RM-CHARTERED")
        status = evolution_status(self.root)
        rows = {r["roadmap_id"]: r for r in status["roadmaps"]}
        self.assertEqual(set(rows), {"RM-PROPOSED", "RM-CHARTERED"})
        self.assertEqual(rows["RM-PROPOSED"]["campaign_id"], "CAMP-P")
        self.assertEqual(rows["RM-PROPOSED"]["ready"], 1)
        self.assertEqual(rows["RM-CHARTERED"]["resumable"], 1)


    def test_batch_round_robins_ready_across_roadmaps(self):
        self._index(
            {"roadmap_id": "RM-A", "state": "ACTIVE", "priority": "P0", "relative_path": "roadmaps/RM-A.json"},
            {"roadmap_id": "RM-B", "state": "ACTIVE", "priority": "P0", "relative_path": "roadmaps/RM-B.json"},
        )
        self._roadmap("RM-A", frontier_refs=[f"A-{i}" for i in range(12)])
        self._roadmap("RM-B", frontier_refs=["B-1"])
        for i in range(12):
            self._test(f"A-{i}", "READY", roadmap_id="RM-A")
        self._test("B-1", "READY", roadmap_id="RM-B")
        frontier = roadmap_frontier(self.root)
        batch_ids = [row["test_id"] for row in frontier["batch"]]
        self.assertIn("B-1", batch_ids)
        self.assertLess(batch_ids.index("B-1"), 3)

    def test_checkpoint_review_quota_is_visible_even_when_ready_batch_is_full(self):
        (self.root / "evolution" / "genome.json").write_text(json.dumps({"genes": [
            {"id": "executor.max_parallel_tests", "canonical": 10},
            {"id": "executor.checkpoint_reviews_per_run", "canonical": 2},
        ]}))
        self._index(
            {"roadmap_id": "RM-A", "state": "ACTIVE", "priority": "P0", "relative_path": "roadmaps/RM-A.json"},
            {"roadmap_id": "RM-B", "state": "ACTIVE", "priority": "P0", "relative_path": "roadmaps/RM-B.json"},
        )
        self._roadmap("RM-A", frontier_refs=[f"A-{i}" for i in range(12)])
        self._roadmap("RM-B", frontier_refs=["B-C1", "B-C2", "B-C3"])
        for i in range(12):
            self._test(f"A-{i}", "READY", roadmap_id="RM-A")
        for tid in ("B-C1", "B-C2", "B-C3"):
            self._test(tid, "CHECKPOINTED", roadmap_id="RM-B")
        frontier = roadmap_frontier(self.root)
        self.assertEqual(len(frontier["batch"]), 10)
        self.assertEqual([row["test_id"] for row in frontier["checkpoint_review"]], ["B-C1", "B-C2"])

    def test_materialized_checkpoint_missing_from_frontier_refs_is_visible(self):
        self._index({"roadmap_id": "RM-A", "state": "ACTIVE", "priority": "P0", "relative_path": "roadmaps/RM-A.json"})
        self._roadmap("RM-A", frontier_refs=["T-READY"])
        self._test("T-READY", "READY", roadmap_id="RM-A")
        self._test("T-ORPHAN-CKPT", "CHECKPOINTED", roadmap_id="RM-A")
        frontier = roadmap_frontier(self.root)
        self.assertIn("T-ORPHAN-CKPT", [r["test_id"] for r in frontier["resumable"]])


if __name__ == "__main__":
    unittest.main()
