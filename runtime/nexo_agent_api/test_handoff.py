from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from . import AgentService, TowerAgentIssue, materialize_role_views


class HandoffProtocolTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        for rel in ("entities/work", "manifests", "snapshot"):
            (self.root / rel).mkdir(parents=True)
        (self.root / "CONTROL.json").write_text(json.dumps({"mode": "ACTIVE", "schema_version": "0.6"}))
        (self.root / "snapshot/latest.json").write_text(json.dumps({"event_cursor": None}))
        (self.root / "manifests/capabilities.json").write_text(json.dumps({"capabilities": {}}))
        (self.root / "manifests/artifacts.json").write_text(json.dumps({"artifacts": {}}))

    def tearDown(self):
        self.tmp.cleanup()

    def test_director_handoff_routes_pending_ack_done(self):
        service = AgentService(self.root)
        created = service.emit_handoff(
            from_role="DIRECTOR",
            to_role="EXECUTOR",
            handoff_type="WORK_READY",
            entity_ref="WORK::GZ01-T02",
            thread_id="THR::SCIENCE::GZ-01",
            next_action="execute",
        )
        self.assertEqual(created["state"], "PENDING")
        self.assertEqual(service.inbox_for("ADVISOR"), [])
        self.assertEqual(service.inbox_for("EXECUTOR")[0]["handoff_id"], created["handoff_id"])

        service.transition_handoff(created["handoff_id"], state="ACK", writer_role="EXECUTOR")
        self.assertEqual(service.inbox_for("EXECUTOR")[0]["state"], "ACK")

        service.transition_handoff(created["handoff_id"], state="DONE", writer_role="EXECUTOR")
        self.assertEqual(service.inbox_for("EXECUTOR"), [])
        with self.assertRaises(TowerAgentIssue):
            service.transition_handoff(created["handoff_id"], state="ACK", writer_role="EXECUTOR")

    def test_bootstrap_projects_only_five_actionable_handoffs(self):
        service = AgentService(self.root)
        for i in range(6):
            service.emit_handoff(
                from_role="ADVISOR",
                to_role="EXECUTOR",
                handoff_type="WORK_READY",
                entity_ref=f"W{i}",
                thread_id="THR-1",
                next_action="execute",
            )
        bootstrap = service.bootstrap("EXECUTOR")
        self.assertEqual(bootstrap["inbox_count"], 5)
        self.assertEqual(bootstrap["inbox_limit"], 5)
        self.assertEqual(len(bootstrap["inbox"]), 5)

        materialize_role_views(self.root)
        persisted = json.loads((self.root / "bootstrap/executor.json").read_text())
        self.assertEqual(persisted["inbox_count"], 5)
        self.assertEqual(persisted["inbox_limit"], 5)

    def test_handoff_embeds_canonical_work_envelope_and_preserves_it_on_ack(self):
        work = {
            "id": "WORK::GZ01-B03",
            "entity_version": 7,
            "kind": "ACTION",
            "status": "READY",
            "owner_role": "EXECUTOR",
            "thread_id": "THR::SCIENCE::GZ-01",
            "question": "Run the next bounded discriminant",
            "next_action": "execute",
            "task_id": "gz01_multprobe_consistency",
            "repository": "byDenoso/TCC",
            "source_revision": "abc123",
            "required_outputs": ["benchmark_result.json"],
        }
        (self.root / "entities/work/WORK::GZ01-B03.json").write_text(json.dumps(work))
        service = AgentService(self.root)

        created = service.emit_handoff(
            from_role="ADVISOR",
            to_role="EXECUTOR",
            handoff_type="WORK_READY",
            entity_ref=work["id"],
            thread_id=work["thread_id"],
            next_action=work["next_action"],
        )

        self.assertEqual(created["entity_version"], 7)
        self.assertEqual(created["entity_path"], "entities/work/WORK::GZ01-B03.json")
        self.assertEqual(created["work_envelope"]["task_id"], "gz01_multprobe_consistency")
        self.assertFalse(created["hydration_required"])

        ack = service.transition_handoff(created["handoff_id"], state="ACK", writer_role="EXECUTOR")
        self.assertEqual(ack["entity_version"], 7)
        self.assertEqual(ack["work_envelope"]["source_revision"], "abc123")


if __name__ == "__main__":
    unittest.main()
