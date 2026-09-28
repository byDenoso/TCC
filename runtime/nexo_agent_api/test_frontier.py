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

    def test_retired_tests_never_fill_the_batch(self):
        # Archived contest chains used to be ranked "contests first" and took every batch slot.
        self._index({"roadmap_id": "RM-A", "state": "ACTIVE", "priority": "P0", "relative_path": "roadmaps/RM-A.json"})
        refs = [f"CONTEST-CONTEST-T{i}-1-1" for i in range(12)] + ["T-READY", "T-ODD"]
        self._roadmap("RM-A", frontier_refs=refs)
        for i in range(12):
            self._test(f"CONTEST-CONTEST-T{i}-1-1", "ARCHIVED", contests_test_id=f"CONTEST-T{i}-1")
        self._test("T-READY", "READY")
        self._test("T-ODD", "QUEUED_SOMEWHERE")
        (self.root / "entities" / "test" / "LOOSE-ARCHIVED.json").write_text(json.dumps({"id": "LOOSE-ARCHIVED", "state": "ARCHIVED"}))
        frontier = roadmap_frontier(self.root)
        self.assertEqual(frontier["next"]["test_id"], "T-READY")
        self.assertEqual([r["test_id"] for r in frontier["ready"]], ["T-READY"])
        self.assertTrue(all(item["state"] in {"READY", "RUNNING", "CHECKPOINTED"} for item in frontier["batch"]))
        self.assertIn("T-ODD", [w["test_id"] for w in frontier["waiting"]])

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

    def test_public_status_groups_recurrent_signals_without_merging_causes_or_private_refs(self):
        artifacts = self.root / "entities" / "artifact"
        artifacts.mkdir()
        self._test("T-A", "DONE")
        self._test("T-B", "DONE")
        self._test("T-PRIVATE", "DONE", semantic={"topic_id": "olympus"})

        rows = (
            ("S-1", "2026-09-24T10:00:00Z", "CHATGPT_TASK_EXECUTOR", {
                "code": "READY_INPUTS_NOT_MATERIALIZED", "topic_id": "engineering.nexo_runtime.state_integrity",
                "test_id": "T-A", "symptom": "private symptom text",
            }),
            ("S-2", "2026-09-25T10:00:00Z", "CHATGPT_CONVERSATION", {
                "code": "READY_INPUTS_NOT_MATERIALIZED", "topic_id": "engineering.nexo_runtime.state_integrity",
                "test_id": "T-B", "remedy": "private remedy text",
            }),
            ("S-3", "2026-09-26T10:00:00Z", "CHATGPT", {
                "code": "SINGLE_OCCURRENCE", "topic_id": "engineering.nexo_runtime.state_integrity",
                "test_id": "T-B",
            }),
            ("S-4", "2026-09-26T11:00:00Z", "CHATGPT", {
                "code": "READY_INPUTS_NOT_MATERIALIZED", "topic_id": "olympus",
                "test_id": "T-PRIVATE", "symptom": "private Olympus text",
            }),
            ("S-5", "2026-09-26T12:00:00Z", "CHATGPT", {
                "code": "READY_INPUTS_NOT_MATERIALIZED", "topic_id": "olympus",
                "symptom": "private Olympus text without a test reference",
            }),
        )
        for artifact_id, created_at, source, signal in rows:
            signals = [signal]
            if artifact_id == "S-1":
                signals.append({**signal, "cause": "private cause text"})
            (artifacts / f"{artifact_id}.json").write_text(json.dumps({
                "id": artifact_id, "kind": "LEARNING_SIGNAL", "created_at": created_at, "source": source,
                "payload": {"signals": signals},
            }), encoding="utf-8")

        # Raw clusters stay internal; the public status exposes only reviewed incidents.
        self.assertNotIn("signal_clusters", evolution_status(self.root, public=True))
        status = evolution_status(self.root)
        clusters = status["signal_clusters"]
        self.assertEqual(len(clusters), 1)
        cluster = clusters[0]
        self.assertEqual(cluster["code"], "READY_INPUTS_NOT_MATERIALIZED")
        self.assertEqual(cluster["occurrences"], 2)
        self.assertEqual(cluster["sources"], ["AUTOMATION", "CONVERSATION"])
        self.assertEqual(cluster["topic_ids"], ["engineering.nexo_runtime.state_integrity"])
        self.assertEqual(cluster["test_ids"], ["T-A", "T-B"])
        self.assertEqual((cluster["first_seen"], cluster["last_seen"]),
                         ("2026-09-24T10:00:00Z", "2026-09-25T10:00:00Z"))
        self.assertEqual(evolution_status(self.root)["signal_clusters"], clusters)
        self.assertNotIn("private", json.dumps(clusters).lower())
        self.assertNotIn("T-PRIVATE", json.dumps(clusters))


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
