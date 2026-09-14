from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from .mutations import apply_mutation_request


class MutationInboxTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "indexes").mkdir(parents=True)
        (self.root / "entities" / "work").mkdir(parents=True)
        (self.root / "snapshot").mkdir(parents=True)
        (self.root / "manifests").mkdir(parents=True)
        (self.root / "CONTROL.json").write_text(json.dumps({"mode": "ACTIVE"}), encoding="utf-8")
        (self.root / "snapshot" / "latest.json").write_text(json.dumps({}), encoding="utf-8")
        (self.root / "manifests" / "capabilities.json").write_text(json.dumps({"capabilities": {}}), encoding="utf-8")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_decimal_string_version_hydrates_and_mutates(self) -> None:
        (self.root / "indexes" / "active-work.json").write_text(json.dumps({"work": [{
            "id": "W1", "entity_version": "1.0", "kind": "ACTION", "status": "READY"
        }]}), encoding="utf-8")
        receipt = apply_mutation_request(self.root, {
            "request_id": "REQ-1", "entity_kind": "work", "entity_name": "W1",
            "expected_version": 1, "changes": {"status": "BLOCKED"},
            "writer_role": "ADVISOR", "event_type": "WORK_BLOCKED"
        })
        self.assertTrue(receipt["accepted"])
        self.assertEqual(receipt["entity_version"], 2)
        entity = json.loads((self.root / "entities" / "work" / "W1.json").read_text())
        self.assertEqual(entity["entity_version"], 2)

    def test_stale_request_returns_typed_receipt(self) -> None:
        (self.root / "entities" / "work" / "W2.json").write_text(json.dumps({
            "id": "W2", "entity_version": 3, "status": "RUNNING"
        }), encoding="utf-8")
        receipt = apply_mutation_request(self.root, {
            "request_id": "REQ-2", "entity_kind": "work", "entity_name": "W2",
            "expected_version": 2, "changes": {"status": "DONE"},
            "writer_role": "EXECUTOR", "event_type": "WORK_DONE"
        })
        self.assertFalse(receipt["accepted"])
        self.assertEqual(receipt["issue"]["code"], "WRITE_CONFLICT_RETRY_REQUIRED")

    def test_zero_version_creates_new_work(self) -> None:
        (self.root / "indexes" / "active-work.json").write_text(json.dumps({"work": []}), encoding="utf-8")
        receipt = apply_mutation_request(self.root, {
            "request_id": "REQ-CREATE-1", "entity_kind": "work", "entity_name": "WORK::NEW",
            "expected_version": 0,
            "changes": {"status": "READY", "owner_role": "EXECUTOR", "kind": "ACTION"},
            "writer_role": "ADVISOR", "event_type": "WORK_READY"
        })
        self.assertTrue(receipt["accepted"])
        self.assertEqual(receipt["entity_version"], 1)
        self.assertEqual(receipt["readback"], "PASS")
        entity = json.loads((self.root / "entities" / "work" / "WORK::NEW.json").read_text())
        self.assertEqual(entity["id"], "WORK::NEW")
        self.assertEqual(entity["entity_version"], 1)
        self.assertEqual(entity["status"], "READY")
        self.assertEqual(entity["owner_role"], "EXECUTOR")

    def test_path_traversal_entity_name_is_rejected(self) -> None:
        receipt = apply_mutation_request(self.root, {
            "request_id": "REQ-3", "entity_kind": "work", "entity_name": "../bad",
            "expected_version": 1, "changes": {"status": "DONE"},
            "writer_role": "EXECUTOR", "event_type": "WORK_DONE"
        })
        self.assertFalse(receipt["accepted"])
        self.assertEqual(receipt["issue"]["code"], "INVALID_MUTATION_REQUEST")


if __name__ == "__main__":
    unittest.main()
