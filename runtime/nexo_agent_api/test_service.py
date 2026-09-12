from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from .service import AgentService, TowerAgentIssue
from .views import materialize_role_views


class AgentServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "entities" / "work").mkdir(parents=True)
        (self.root / "manifests").mkdir(parents=True)
        (self.root / "snapshot").mkdir(parents=True)
        (self.root / "CONTROL.json").write_text(json.dumps({"mode": "ACTIVE", "schema_version": "0.6"}), encoding="utf-8")
        (self.root / "snapshot" / "latest.json").write_text(json.dumps({"event_cursor": "EVT-10"}), encoding="utf-8")
        (self.root / "manifests" / "capabilities.json").write_text(json.dumps({"capabilities": {"compile_v1": {"roles": ["EXECUTOR"], "backend": "github"}}}), encoding="utf-8")
        (self.root / "manifests" / "artifacts.json").write_text(json.dumps({"artifacts": {"ART-1": {"storage": "drive", "ref": "drive:1"}}}), encoding="utf-8")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def write_work(self, name: str, payload: dict) -> None:
        (self.root / "entities" / "work" / f"{name}.json").write_text(json.dumps(payload), encoding="utf-8")

    def test_executor_queue_requires_mechanical_eligibility(self) -> None:
        self.write_work("weak-ready", {"id": "W1", "entity_version": 1, "status": "READY", "owner_role": "EXECUTOR"})
        self.write_work("eligible", {
            "id": "W2", "entity_version": 3, "status": "READY", "owner_role": "EXECUTOR",
            "dependencies_resolved": True, "binding_verified": True, "task_id": "compile_v1",
            "repository": "byDenoso/TCC", "source_revision": "abc123", "required_outputs": ["out.json"],
            "validation_ref": "VAL-1", "runtime_available": True, "resource_lock_available": True,
        })
        queue = AgentService(self.root).queue_for("EXECUTOR")
        self.assertEqual([item["id"] for item in queue], ["W2"])

    def test_cas_mutation_increments_version_writes_event_and_readback(self) -> None:
        self.write_work("w1", {"id": "W1", "entity_version": 1, "status": "READY", "owner_role": "EXECUTOR"})
        result = AgentService(self.root).mutate(
            "work", "w1", expected_version=1, changes={"status": "RUNNING"},
            writer_role="EXECUTOR", event_type="WORK_STARTED", material=True,
        )
        self.assertTrue(result["accepted"])
        self.assertEqual(result["entity_version"], 2)
        self.assertEqual(json.loads((self.root / "entities" / "work" / "w1.json").read_text())["status"], "RUNNING")
        event_files = list((self.root / "events").rglob("*.json"))
        self.assertEqual(len(event_files), 1)
        self.assertEqual(json.loads(event_files[0].read_text())["entity_version"], 2)
        self.assertEqual(result["readback"], "PASS")

    def test_stale_version_is_rejected(self) -> None:
        self.write_work("w1", {"id": "W1", "entity_version": 2, "status": "RUNNING"})
        with self.assertRaises(TowerAgentIssue) as ctx:
            AgentService(self.root).mutate("work", "w1", expected_version=1, changes={"status": "DONE"}, writer_role="EXECUTOR", event_type="WORK_DONE")
        self.assertEqual(ctx.exception.code, "WRITE_CONFLICT_RETRY_REQUIRED")

    def test_bootstrap_is_single_role_payload(self) -> None:
        self.write_work("w2", {
            "id": "W2", "entity_version": 1, "status": "READY", "owner_role": "EXECUTOR",
            "dependencies_resolved": True, "binding_verified": True, "task_id": "compile_v1",
            "repository": "byDenoso/TCC", "source_revision": "abc", "required_outputs": ["o"],
            "validation_ref": "VAL", "runtime_available": True, "resource_lock_available": True,
        })
        bootstrap = AgentService(self.root).bootstrap("EXECUTOR")
        self.assertEqual(bootstrap["control"]["mode"], "ACTIVE")
        self.assertEqual(bootstrap["event_cursor"], "EVT-10")
        self.assertEqual(bootstrap["queue"][0]["id"], "W2")
        self.assertIn("compile_v1", bootstrap["capabilities"])

    def test_artifact_resolution_hides_storage_details_from_callers(self) -> None:
        resolved = AgentService(self.root).resolve_artifact("ART-1")
        self.assertEqual(resolved["storage"], "drive")
        with self.assertRaises(TowerAgentIssue) as ctx:
            AgentService(self.root).resolve_artifact("MISSING")
        self.assertEqual(ctx.exception.code, "ARTIFACT_NOT_FOUND")

    def test_active_work_index_is_used_and_hydrated_entity_overrides_it(self) -> None:
        (self.root / "indexes").mkdir(parents=True)
        (self.root / "indexes" / "active-work.json").write_text(json.dumps({"work": [{
            "id": "W-INDEX", "entity_version": 1, "status": "READY", "owner_role": "ADVISOR"
        }]}), encoding="utf-8")
        service = AgentService(self.root)
        self.assertEqual(service.queue_for("ADVISOR")[0]["id"], "W-INDEX")
        self.write_work("W-INDEX", {"id": "W-INDEX", "entity_version": 2, "status": "DONE", "owner_role": "ADVISOR"})
        self.assertEqual(service.queue_for("ADVISOR"), [])

    def test_first_mutation_auto_hydrates_from_active_work_index(self) -> None:
        (self.root / "indexes").mkdir(parents=True)
        (self.root / "indexes" / "active-work.json").write_text(json.dumps({"work": [{
            "id": "W-HYDRATE", "entity_version": 1, "status": "READY", "owner_role": "ADVISOR"
        }]}), encoding="utf-8")
        result = AgentService(self.root).mutate(
            "work", "W-HYDRATE", expected_version=1, changes={"status": "SOURCE_BINDING_PENDING"},
            writer_role="ADVISOR", event_type="WORK_UPDATED",
        )
        self.assertEqual(result["entity_version"], 2)
        entity = json.loads((self.root / "entities" / "work" / "W-HYDRATE.json").read_text())
        self.assertEqual(entity["status"], "SOURCE_BINDING_PENDING")

    def test_materialized_views_write_one_bootstrap_and_queue_per_role(self) -> None:
        self.write_work("w2", {
            "id": "W2", "entity_version": 1, "status": "READY", "owner_role": "EXECUTOR",
            "dependencies_resolved": True, "binding_verified": True, "task_id": "compile_v1",
            "repository": "byDenoso/TCC", "source_revision": "abc", "required_outputs": ["o"],
            "validation_ref": "VAL", "runtime_available": True, "resource_lock_available": True,
        })
        result = materialize_role_views(self.root)
        self.assertEqual(result["roles"], 5)
        self.assertTrue((self.root / "bootstrap" / "executor.json").exists())
        self.assertTrue((self.root / "queues" / "executor.json").exists())
        executor = json.loads((self.root / "bootstrap" / "executor.json").read_text())
        self.assertEqual(executor["queue_count"], 1)


if __name__ == "__main__":
    unittest.main()
