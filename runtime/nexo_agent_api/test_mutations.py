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

    def test_zero_version_creates_new_work_with_matching_identity(self) -> None:
        (self.root / "indexes" / "active-work.json").write_text(json.dumps({"work": []}), encoding="utf-8")
        receipt = apply_mutation_request(self.root, {
            "request_id": "REQ-CREATE-1", "entity_kind": "work", "entity_name": "WORK::NEW",
            "expected_version": 0,
            "changes": {"id": "WORK::NEW", "status": "READY", "owner_role": "EXECUTOR", "kind": "ACTION"},
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

    def test_zero_version_creates_new_test_with_exact_readback(self) -> None:
        receipt = apply_mutation_request(self.root, {
            "request_id": "REQ-CREATE-TEST-1",
            "entity_kind": "test",
            "entity_name": "GZSB-01-DESI-INFERENCE-PRIOR-SENSITIVITY",
            "expected_version": 0,
            "changes": {
                "id": "GZSB-01-DESI-INFERENCE-PRIOR-SENSITIVITY",
                "test_group_id": "TEST_GROUP::CAMP-GROWTH-LSS::GZ01-EROSITA-SUPERBATTERY",
                "campaign_id": "CAMP-GROWTH-LSS",
                "status": "VERIFIED",
                "evidence_class": "FROZEN_BATTERY_CHILD",
            },
            "writer_role": "EXECUTOR",
            "event_type": "TEST_VERIFIED",
        })
        self.assertTrue(receipt["accepted"])
        self.assertEqual(receipt["entity_version"], 1)
        self.assertEqual(receipt["readback"], "PASS")
        entity = json.loads((self.root / "entities" / "test" / "GZSB-01-DESI-INFERENCE-PRIOR-SENSITIVITY.json").read_text())
        self.assertEqual(entity["id"], "GZSB-01-DESI-INFERENCE-PRIOR-SENSITIVITY")
        self.assertEqual(entity["entity_version"], 1)
        self.assertEqual(entity["campaign_id"], "CAMP-GROWTH-LSS")
        self.assertEqual(entity["test_group_id"], "TEST_GROUP::CAMP-GROWTH-LSS::GZ01-EROSITA-SUPERBATTERY")

    def test_zero_version_creates_new_test_group_with_exact_readback(self) -> None:
        group_id = "TEST_GROUP::CAMP-GROWTH-LSS::GZ01-EROSITA-SUPERBATTERY"
        receipt = apply_mutation_request(self.root, {
            "request_id": "REQ-CREATE-TEST-GROUP-1",
            "entity_kind": "test_group",
            "entity_name": group_id,
            "expected_version": 0,
            "changes": {
                "id": group_id,
                "campaign_id": "CAMP-GROWTH-LSS",
                "group_kind": "BATTERY",
                "label": "GZ01 eROSITA Superbattery",
                "status": "ACTIVE",
            },
            "writer_role": "ADVISOR",
            "event_type": "TEST_GROUP_CREATED",
        })
        self.assertTrue(receipt["accepted"])
        self.assertEqual(receipt["entity_version"], 1)
        self.assertEqual(receipt["readback"], "PASS")
        entity = json.loads((self.root / "entities" / "test_group" / f"{group_id}.json").read_text())
        self.assertEqual(entity["id"], group_id)
        self.assertEqual(entity["entity_version"], 1)
        self.assertEqual(entity["group_kind"], "BATTERY")

    def test_zero_version_rejects_mismatched_identity(self) -> None:
        (self.root / "indexes" / "active-work.json").write_text(json.dumps({"work": []}), encoding="utf-8")
        receipt = apply_mutation_request(self.root, {
            "request_id": "REQ-CREATE-2", "entity_kind": "work", "entity_name": "WORK::NEW",
            "expected_version": 0,
            "changes": {"id": "WORK::OTHER", "status": "READY"},
            "writer_role": "ADVISOR", "event_type": "WORK_READY"
        })
        self.assertFalse(receipt["accepted"])
        self.assertEqual(receipt["issue"]["code"], "INVALID_MUTATION_REQUEST")
        self.assertFalse((self.root / "entities" / "work" / "WORK::NEW.json").exists())

    def test_zero_version_rejects_mismatched_identity_for_test_group(self) -> None:
        receipt = apply_mutation_request(self.root, {
            "request_id": "REQ-CREATE-TEST-GROUP-2",
            "entity_kind": "test_group",
            "entity_name": "TEST_GROUP::CAMP-GROWTH-LSS::A",
            "expected_version": 0,
            "changes": {"id": "TEST_GROUP::CAMP-GROWTH-LSS::B", "campaign_id": "CAMP-GROWTH-LSS"},
            "writer_role": "ADVISOR",
            "event_type": "TEST_GROUP_CREATED",
        })
        self.assertFalse(receipt["accepted"])
        self.assertEqual(receipt["issue"]["code"], "INVALID_MUTATION_REQUEST")
        self.assertFalse((self.root / "entities" / "test_group" / "TEST_GROUP::CAMP-GROWTH-LSS::A.json").exists())

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
