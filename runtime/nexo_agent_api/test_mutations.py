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

    def test_zero_version_creates_new_hypothesis_with_exact_readback(self) -> None:
        hypothesis_id = "HYP-CAMB-OPTIMIZATION-V1"
        receipt = apply_mutation_request(self.root, {
            "request_id": "REQ-CREATE-HYPOTHESIS-1",
            "entity_kind": "hypothesis",
            "entity_name": hypothesis_id,
            "expected_version": 0,
            "changes": {
                "id": hypothesis_id,
                "status": "OPEN",
                "proposition": "A targeted CAMB optimization can reduce runtime without violating the frozen numerical tolerance.",
                "claim_boundary": "Runtime improvement only; no scientific claim is implied.",
                "success_criteria": ["runtime improves", "accuracy remains within tolerance"],
                "kill_criteria": ["accuracy exceeds tolerance"],
                "critical_tests": ["baseline benchmark", "numerical equivalence regression"],
                "max_adaptive_followups": 2,
                "reopen_policy": "external_material_information_only",
            },
            "writer_role": "ADVISOR",
            "event_type": "HYPOTHESIS_CREATED",
        })
        self.assertTrue(receipt["accepted"])
        self.assertEqual(receipt["entity_version"], 1)
        self.assertEqual(receipt["readback"], "PASS")
        entity = json.loads((self.root / "entities" / "hypothesis" / f"{hypothesis_id}.json").read_text())
        self.assertEqual(entity["id"], hypothesis_id)
        self.assertEqual(entity["entity_version"], 1)
        self.assertEqual(entity["status"], "OPEN")
        self.assertEqual(entity["writer_role"], "ADVISOR")

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

    def test_work_terminal_mutation_refreshes_active_projection(self) -> None:
        (self.root / "indexes" / "active-work.json").write_text(json.dumps({
            "schema_version": "0.6",
            "work": [{
                "id": "W-CLOSE",
                "entity_version": 1,
                "status": "READY",
                "owner_role": "EXECUTOR",
                "kind": "ACTION",
            }],
        }), encoding="utf-8")
        (self.root / "entities" / "work" / "W-CLOSE.json").write_text(json.dumps({
            "id": "W-CLOSE",
            "entity_version": 1,
            "status": "READY",
            "owner_role": "EXECUTOR",
            "kind": "ACTION",
        }), encoding="utf-8")

        receipt = apply_mutation_request(self.root, {
            "request_id": "REQ-CLOSE-1",
            "entity_kind": "work",
            "entity_name": "W-CLOSE",
            "expected_version": 1,
            "changes": {"status": "DONE"},
            "writer_role": "EXECUTOR",
            "event_type": "WORK_DONE",
        })

        self.assertTrue(receipt["accepted"])
        self.assertEqual(receipt["readback"], "PASS")
        self.assertEqual(receipt["projection_refresh"]["status"], "PASS")

        active = json.loads((self.root / "indexes" / "active-work.json").read_text())
        self.assertEqual(active["work"], [])
        self.assertEqual(active["count"], 0)

        roi = json.loads((self.root / "snapshot" / "ai-roi.json").read_text())
        self.assertEqual(roi["active_work"]["count"], 0)

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
