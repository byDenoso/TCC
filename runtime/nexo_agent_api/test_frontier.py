from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from runtime.nexo_agent_api.frontier import roadmap_frontier
from runtime.nexo_agent_api.tower_paths import entity_path


class FrontierTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "indexes").mkdir()
        (self.root / "roadmaps").mkdir()
        (self.root / "entities" / "test").mkdir(parents=True)

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

    def test_resume_beats_new_and_bad_roadmaps_are_not_fatal(self):
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
        self.assertEqual(frontier["state"], "RESUME_EXISTING")
        self.assertEqual(frontier["next"]["test_id"], "TEST::Y")
        self.assertEqual(frontier["skipped_roadmaps"][0]["reason"], "ACTIVE_ROADMAP_WITHOUT_TESTS")


if __name__ == "__main__":
    unittest.main()
