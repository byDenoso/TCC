from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from .service import AgentService


class ExecutorCapabilityGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "entities" / "work").mkdir(parents=True)
        (self.root / "manifests").mkdir(parents=True)
        (self.root / "snapshot").mkdir(parents=True)
        (self.root / "CONTROL.json").write_text(json.dumps({"mode": "ACTIVE", "schema_version": "0.6"}), encoding="utf-8")
        (self.root / "snapshot" / "latest.json").write_text(json.dumps({"event_cursor": "EVT-1"}), encoding="utf-8")
        (self.root / "manifests" / "capabilities.json").write_text(json.dumps({
            "capabilities": {
                "known_task": {"roles": ["EXECUTOR"], "backend": "github_dispatch", "task_id": "known_task", "status": "PROVEN"}
            }
        }), encoding="utf-8")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def write_work(self, name: str, **extra) -> None:
        payload = {
            "id": name,
            "entity_version": 1,
            "status": "READY",
            "owner_role": "EXECUTOR",
            "dependencies_resolved": True,
            "binding_verified": True,
            "repository": "byDenoso/TCC",
            "source_revision": "abc123",
            "required_outputs": ["result.json"],
            "validation_ref": "VAL",
            "runtime_available": True,
            "resource_lock_available": True,
        }
        payload.update(extra)
        (self.root / "entities" / "work" / f"{name}.json").write_text(json.dumps(payload), encoding="utf-8")

    def test_executor_rejects_unregistered_task_id(self) -> None:
        self.write_work("W-UNKNOWN", task_id="unknown_task")
        self.assertEqual(AgentService(self.root).queue_for("EXECUTOR"), [])

    def test_executor_rejects_implementation_ref_without_task_id(self) -> None:
        self.write_work("W-IMPL-ONLY", implementation_ref="vendor/model@deadbeef")
        self.assertEqual(AgentService(self.root).queue_for("EXECUTOR"), [])

    def test_executor_accepts_registered_task_id(self) -> None:
        self.write_work("W-KNOWN", task_id="known_task")
        queue = AgentService(self.root).queue_for("EXECUTOR")
        self.assertEqual([item["id"] for item in queue], ["W-KNOWN"])

    def test_executor_accepts_frozen_test_contract_without_registered_task_id(self) -> None:
        payload = {
            "id": "W-FROZEN",
            "entity_version": 1,
            "status": "READY",
            "owner_role": "EXECUTOR",
            "question": "Is the frozen binding contract executable?",
            "frozen_test": {
                "id": "T01-BIND",
                "method": "Resolve and validate the bound inputs.",
                "decision_rule": "PASS only when all required bindings validate.",
                "outputs": ["binding manifest", "validation receipt"],
                "claim_boundary": "Binding readiness only.",
            },
        }
        (self.root / "entities" / "work" / "W-FROZEN.json").write_text(json.dumps(payload), encoding="utf-8")

        queue = AgentService(self.root).queue_for("EXECUTOR")

        self.assertEqual([item["id"] for item in queue], ["W-FROZEN"])
        self.assertIn("frozen_test", queue[0])
        self.assertEqual(queue[0]["frozen_test"]["id"], "T01-BIND")


if __name__ == "__main__":
    unittest.main()
