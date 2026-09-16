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
        for kind in ("work", "campaign", "test", "run", "result"):
            (self.root / "entities" / kind).mkdir(parents=True)
        (self.root / "manifests").mkdir(parents=True)
        (self.root / "snapshot").mkdir(parents=True)
        (self.root / "CONTROL.json").write_text(json.dumps({"mode": "ACTIVE", "schema_version": "0.6"}), encoding="utf-8")
        (self.root / "snapshot" / "latest.json").write_text(json.dumps({"event_cursor": "EVT-1"}), encoding="utf-8")
        (self.root / "manifests" / "capabilities.json").write_text(json.dumps({
            "capabilities": {
                "known_task": {"roles": ["EXECUTOR"], "backend": "github_dispatch", "task_id": "known_task", "status": "PROVEN"},
                "mock_observer_v1": {
                    "roles": ["EXECUTOR"],
                    "backend": "github_dispatch",
                    "task_id": "mock_observer_runtime",
                    "status": "ACTIVE",
                    "semantic_capabilities": ["science.mock_observer"]
                }
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

    def frozen_work(self, name: str = "W-FROZEN", **extra) -> dict:
        payload = {
            "id": name,
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
        payload.update(extra)
        return payload

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
        payload = self.frozen_work()
        (self.root / "entities" / "work" / "W-FROZEN.json").write_text(json.dumps(payload), encoding="utf-8")

        queue = AgentService(self.root).queue_for("EXECUTOR")

        self.assertEqual([item["id"] for item in queue], ["W-FROZEN"])
        self.assertIn("frozen_test", queue[0])
        self.assertEqual(queue[0]["frozen_test"]["id"], "T01-BIND")

    def test_executor_queue_preserves_interdomain_ref(self) -> None:
        payload = self.frozen_work(interdomain_ref="META::INTERDOMAIN::TEST-001")
        (self.root / "entities" / "work" / "W-FROZEN.json").write_text(json.dumps(payload), encoding="utf-8")

        queue = AgentService(self.root).queue_for("EXECUTOR")

        self.assertEqual(queue[0].get("interdomain_ref"), "META::INTERDOMAIN::TEST-001")

    def test_service_exposes_campaign_frontier(self) -> None:
        (self.root / "entities" / "campaign" / "CAMP-1.json").write_text(
            json.dumps({"id": "CAMP-1", "status": "ACTIVE", "execution_order": ["TEST::A"]}),
            encoding="utf-8",
        )
        (self.root / "entities" / "test" / "TEST::A.json").write_text(
            json.dumps({"id": "TEST::A", "campaign_id": "CAMP-1", "status": "READY"}),
            encoding="utf-8",
        )

        frontier = AgentService(self.root).campaign_frontier("CAMP-1")

        self.assertEqual(frontier["ready"], ["TEST::A"])

    def test_service_resolves_semantic_test_execution(self) -> None:
        decision = AgentService(self.root).resolve_test_execution(
            {"required_capabilities": ["science.mock_observer"]}
        )

        self.assertEqual(decision["status"], "RESOLVED")
        self.assertEqual(decision["task_id"], "mock_observer_runtime")


if __name__ == "__main__":
    unittest.main()
