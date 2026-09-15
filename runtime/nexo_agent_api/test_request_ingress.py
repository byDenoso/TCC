from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from . import AgentService


class RequestIngressTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        for rel in ("entities/work", "events", "manifests", "snapshot"):
            (self.root / rel).mkdir(parents=True, exist_ok=True)
        (self.root / "CONTROL.json").write_text(json.dumps({"mode": "ACTIVE", "schema_version": "0.6"}))
        (self.root / "snapshot/latest.json").write_text(json.dumps({"event_cursor": "EVT-0"}))
        (self.root / "manifests/capabilities.json").write_text(json.dumps({"capabilities": {}}))
        self.service = AgentService(self.root)

    def tearDown(self):
        self.tmp.cleanup()

    def task(self, *, thread_id: str, subject: str = "GZ01-05", **extra):
        payload = {
            "thread_id": thread_id,
            "action": "run",
            "subject": subject,
            "domain": "SCIENCE",
            "owner_role": "EXECUTOR",
            "scope": "eROSITA super-battery",
        }
        payload.update(extra)
        return self.service.ingest_request(**payload)

    def read_work(self, work_id: str) -> dict:
        return json.loads((self.root / "entities" / "work" / f"{work_id}.json").read_text())

    def events(self) -> list[dict]:
        result = []
        for path in sorted((self.root / "events").rglob("*.json")):
            result.append(json.loads(path.read_text()))
        return result

    def test_same_task_from_two_chats_merges_into_one_work(self):
        first = self.task(thread_id="CHAT-A", correlation_id="CORR-A")
        second = self.task(thread_id="CHAT-B", correlation_id="CORR-B")

        self.assertTrue(first["admitted"])
        self.assertEqual(first["outcome"], "CREATED")
        self.assertEqual(second["outcome"], "MERGED")
        self.assertEqual(first["work_id"], second["work_id"])
        work = self.read_work(first["work_id"])
        self.assertEqual(work["request_count"], 2)
        self.assertEqual(work["source_threads"], ["CHAT-A", "CHAT-B"])
        self.assertEqual(len(work["request_refs"]), 2)
        self.assertNotIn("raw_text", work)
        self.assertEqual(second["readback"], "PASS")

    def test_different_material_task_creates_different_work(self):
        first = self.task(thread_id="CHAT-A", subject="GZ01-05")
        second = self.task(thread_id="CHAT-B", subject="GZ01-09")
        self.assertNotEqual(first["work_id"], second["work_id"])
        self.assertEqual(second["outcome"], "CREATED")

    def test_non_actionable_request_persists_nothing(self):
        result = self.task(thread_id="CHAT-A", actionable=False)
        self.assertFalse(result["admitted"])
        self.assertEqual(result["outcome"], "REJECTED_NON_ACTIONABLE")
        self.assertEqual(list((self.root / "entities" / "work").glob("*.json")), [])
        self.assertEqual(self.events(), [])

    def test_explicit_target_continues_existing_work_without_state_change(self):
        first = self.task(thread_id="CHAT-A")
        work_path = self.root / "entities" / "work" / f"{first['work_id']}.json"
        work = json.loads(work_path.read_text())
        work["status"] = "RUNNING"
        work["entity_version"] = 2
        work_path.write_text(json.dumps(work))

        continued = self.service.ingest_request(
            thread_id="CHAT-B",
            action="continue",
            subject="eROSITA tests",
            domain="SCIENCE",
            owner_role="EXECUTOR",
            target_work_id=first["work_id"],
            correlation_id="CORR-CONT",
        )

        self.assertEqual(continued["work_id"], first["work_id"])
        self.assertEqual(continued["outcome"], "MERGED")
        current = self.read_work(first["work_id"])
        self.assertEqual(current["status"], "RUNNING")
        self.assertEqual(current["request_count"], 2)

    def test_terminal_duplicate_is_not_resurrected(self):
        first = self.task(thread_id="CHAT-A")
        work_path = self.root / "entities" / "work" / f"{first['work_id']}.json"
        work = json.loads(work_path.read_text())
        work["status"] = "DONE"
        work["entity_version"] = 2
        work_path.write_text(json.dumps(work))

        duplicate = self.task(thread_id="CHAT-B")

        self.assertEqual(duplicate["outcome"], "TERMINAL_MATCH")
        current = self.read_work(first["work_id"])
        self.assertEqual(current["status"], "DONE")
        self.assertEqual(current["request_count"], 1)
        self.assertEqual(self.events()[-1]["event_type"], "REQUEST_TERMINAL_MATCH")

    def test_request_provenance_compacts_after_twenty_refs(self):
        result = None
        for i in range(25):
            result = self.task(thread_id=f"CHAT-{i:02d}", correlation_id=f"CORR-{i:02d}")

        work = self.read_work(result["work_id"])
        self.assertEqual(work["request_count"], 25)
        self.assertEqual(len(work["request_refs"]), 20)
        self.assertEqual(len(work["source_threads"]), 20)
        self.assertEqual(work["source_threads"][0], "CHAT-05")
        self.assertEqual(work["source_threads"][-1], "CHAT-24")


if __name__ == "__main__":
    unittest.main()
