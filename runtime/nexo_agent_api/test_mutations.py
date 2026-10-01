from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from .mutations import apply_mutation_request
from runtime.nexo_agent_api.tower_paths import entity_path


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
        entity = json.loads((entity_path(self.root, "work", "W1")).read_text())
        self.assertEqual(entity["entity_version"], 2)

    def test_stale_request_returns_typed_receipt(self) -> None:
        (entity_path(self.root, "work", "W2")).write_text(json.dumps({
            "id": "W2", "entity_version": 3, "status": "RUNNING"
        }), encoding="utf-8")
        receipt = apply_mutation_request(self.root, {
            "request_id": "REQ-2", "entity_kind": "work", "entity_name": "W2",
            "expected_version": 2, "changes": {"status": "DONE"},
            "writer_role": "EXECUTOR", "event_type": "WORK_DONE"
        })
        self.assertFalse(receipt["accepted"])
        self.assertEqual(receipt["issue"]["code"], "WRITE_CONFLICT_RETRY_REQUIRED")

    def test_identical_test_result_payload_is_no_op_even_from_duplicate_gateway_envelope(self) -> None:
        changes = {
            "status": "DONE", "state": "DONE", "verdict": "PROMOTED",
            "decision": "FROZEN_DECISION", "result_summary": "Mesmo resultado congelado.",
            "statistics": {"n": 5, "rate": 1.0},
            "limitations": ["Amostra congelada."],
            "reproducibility": {"attempts": [{"attempt": 1, "status": "DONE"}]},
            "executed_by": "CHATGPT_TASK_EXECUTOR",
            "executed_at": "2026-09-26T12:10:01Z",
            "inbox_ref": "gateway:tcc-first-envelope",
            "semantic": {"result_meaning": "O sinal sobreviveu."},
        }
        path = entity_path(self.root, "test", "T-RESULT-REPLAY")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"id": "T-RESULT-REPLAY", "entity_version": 7, **changes}))
        before = path.read_bytes()
        receipt = apply_mutation_request(self.root, {
            "request_id": "REQ-INBOX-RESULT-DUPLICATE",
            "entity_kind": "test", "entity_name": "T-RESULT-REPLAY", "expected_version": 7,
            "changes": {**changes, "executed_at": "2026-09-26T12:24:00Z",
                        "inbox_ref": "gateway:tcc-duplicate-envelope"},
            "writer_role": "EXECUTOR", "event_type": "TEST_RESULT_RECORDED",
        })
        self.assertTrue(receipt["accepted"])
        self.assertEqual(receipt["status"], "NO_OP")
        self.assertEqual(receipt["reason"], "RESULT_PAYLOAD_ALREADY_CANONICAL")
        self.assertEqual(receipt["entity_version"], 7)
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(list((self.root / "events").rglob("*.json")), [])
        self.assertFalse((self.root / "NEXO_TOWER_LIVE.json").exists())

    def test_same_result_source_identity_with_changed_payload_is_conflict(self) -> None:
        path = entity_path(self.root, "test", "T-RESULT-CONFLICT")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({
            "id": "T-RESULT-CONFLICT", "entity_version": 4,
            "status": "DONE", "state": "DONE", "verdict": "PROMOTED",
            "result_summary": "Resultado original.", "executed_by": "CHATGPT_TASK_EXECUTOR",
            "executed_at": "2026-09-26T12:10:01Z", "inbox_ref": "gateway:tcc-stable",
        }))
        before = path.read_bytes()
        receipt = apply_mutation_request(self.root, {
            "request_id": "REQ-INBOX-RESULT-STABLE",
            "entity_kind": "test", "entity_name": "T-RESULT-CONFLICT", "expected_version": 4,
            "changes": {
                "status": "DONE", "state": "DONE", "verdict": "REJECTED",
                "result_summary": "Conteúdo diferente.", "executed_by": "CHATGPT_TASK_EXECUTOR",
                "executed_at": "2026-09-26T12:10:01Z", "inbox_ref": "gateway:tcc-stable",
            },
            "writer_role": "EXECUTOR", "event_type": "TEST_RESULT_RECORDED",
        })
        self.assertFalse(receipt["accepted"])
        self.assertEqual(receipt["issue"]["code"], "INBOX_RESULT_IDENTITY_CONFLICT")
        self.assertEqual(receipt["issue"]["details"]["different_fields"],
                         ["result_summary", "verdict"])
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(list((self.root / "events").rglob("*.json")), [])

    def test_different_result_source_cannot_replay_older_or_undated_content(self) -> None:
        path = entity_path(self.root, "test", "T-RESULT-ORDER")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({
            "id": "T-RESULT-ORDER", "entity_version": 6,
            "status": "DONE", "state": "DONE", "verdict": "PROMOTED",
            "result_summary": "Resultado canônico.", "executed_by": "CHATGPT_TASK_EXECUTOR",
            "executed_at": "2026-09-26T12:10:01Z", "inbox_ref": "gateway:tcc-newer",
        }))
        before = path.read_bytes()
        for request_id, executed_at in (("REQ-OLDER", "2026-09-26T00:28:00Z"),
                                        ("REQ-UNDATED", None),
                                        ("REQ-SAME-TIME", "2026-09-26T12:10:01Z")):
            changes = {
                "status": "DONE", "state": "DONE", "verdict": "REJECTED",
                "result_summary": "Payload divergente.", "executed_by": "CHATGPT_TASK_EXECUTOR",
                "inbox_ref": "gateway:tcc-other",
            }
            if executed_at:
                changes["executed_at"] = executed_at
            receipt = apply_mutation_request(self.root, {
                "request_id": request_id, "entity_kind": "test", "entity_name": "T-RESULT-ORDER",
                "expected_version": 6, "changes": changes,
                "writer_role": "EXECUTOR", "event_type": "TEST_RESULT_RECORDED",
            })
            self.assertFalse(receipt["accepted"])
            self.assertEqual(receipt["issue"]["code"], "INBOX_RESULT_ORDER_CONFLICT")
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(list((self.root / "events").rglob("*.json")), [])

    def test_invalid_result_datetime_cannot_establish_replacement_order(self) -> None:
        path = entity_path(self.root, "test", "T-RESULT-BAD-CLOCK")
        path.parent.mkdir(parents=True, exist_ok=True)
        base = {
            "id": "T-RESULT-BAD-CLOCK", "entity_version": 3,
            "status": "DONE", "state": "DONE", "verdict": "INCONCLUSIVE",
            "result_summary": "Resultado canônico.", "inbox_ref": "gateway:tcc-old",
        }
        cases = (
            ("2026-09-26T12:10:01Z", {"at": "2026-09-26T12:20:01Z"}),
            ("2026-09-26T12:10:01Z", True),
            ({"at": "2026-09-26T12:10:01Z"}, "2026-09-26T12:20:01Z"),
        )
        for index, (current_at, incoming_at) in enumerate(cases):
            with self.subTest(index=index):
                path.write_text(json.dumps({**base, "executed_at": current_at}))
                receipt = apply_mutation_request(self.root, {
                    "request_id": f"REQ-BAD-CLOCK-{index}",
                    "entity_kind": "test", "entity_name": "T-RESULT-BAD-CLOCK",
                    "expected_version": 3,
                    "changes": {
                        "status": "DONE", "state": "DONE", "verdict": "REJECTED",
                        "result_summary": "Payload divergente.", "inbox_ref": "gateway:tcc-new",
                        "executed_at": incoming_at,
                    },
                    "writer_role": "EXECUTOR", "event_type": "TEST_RESULT_RECORDED",
                })
                self.assertFalse(receipt["accepted"])
                self.assertEqual(receipt["issue"]["code"], "INBOX_RESULT_ORDER_CONFLICT")

    def test_prepared_test_with_executor_metadata_accepts_its_first_result(self) -> None:
        path = entity_path(self.root, "test", "T-PREPARED-FIRST-RESULT")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({
            "id": "T-PREPARED-FIRST-RESULT", "entity_version": 2,
            "status": "READY", "state": "READY",
            "executed_by": "ASSIGNED_EXECUTOR", "inbox_ref": "preparation:receipt-1",
        }))
        receipt = apply_mutation_request(self.root, {
            "request_id": "REQ-FIRST-RESULT",
            "entity_kind": "test", "entity_name": "T-PREPARED-FIRST-RESULT",
            "expected_version": 2,
            "changes": {
                "status": "DONE", "state": "DONE", "verdict": "INCONCLUSIVE",
                "result_summary": "Primeiro resultado real.", "executed_by": "CHATGPT_TASK_EXECUTOR",
                "executed_at": "2026-09-26T12:20:01Z", "inbox_ref": "gateway:tcc-result",
            },
            "writer_role": "EXECUTOR", "event_type": "TEST_RESULT_RECORDED",
        })
        self.assertTrue(receipt["accepted"])
        self.assertNotEqual(receipt.get("status"), "NO_OP")
        self.assertEqual(receipt["entity_version"], 3)
        self.assertEqual(json.loads(path.read_text())["result_summary"], "Primeiro resultado real.")

    def test_later_different_result_source_remains_a_real_mutation(self) -> None:
        path = entity_path(self.root, "test", "T-RESULT-LATER")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({
            "id": "T-RESULT-LATER", "entity_version": 2,
            "status": "DONE", "state": "DONE", "verdict": "INCONCLUSIVE",
            "result_summary": "Resultado antigo.", "executed_by": "CHATGPT_TASK_EXECUTOR",
            "executed_at": "2026-09-26T12:10:01Z", "inbox_ref": "gateway:tcc-old",
        }))
        receipt = apply_mutation_request(self.root, {
            "request_id": "REQ-LATER", "entity_kind": "test", "entity_name": "T-RESULT-LATER",
            "expected_version": 2,
            "changes": {
                "status": "DONE", "state": "DONE", "verdict": "INCONCLUSIVE",
                "result_summary": "Resultado novo.", "executed_by": "CHATGPT_TASK_EXECUTOR",
                "executed_at": "2026-09-26T12:20:01Z", "inbox_ref": "gateway:tcc-new",
            },
            "writer_role": "EXECUTOR", "event_type": "TEST_RESULT_RECORDED",
        })
        self.assertTrue(receipt["accepted"])
        self.assertNotEqual(receipt.get("status"), "NO_OP")
        self.assertEqual(receipt["entity_version"], 3)
        current = json.loads(path.read_text())
        self.assertEqual(current["result_summary"], "Resultado novo.")
        self.assertEqual(current["inbox_ref"], "gateway:tcc-new")

    def test_stale_identical_result_still_returns_version_conflict(self) -> None:
        path = entity_path(self.root, "test", "T-RESULT-STALE")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({
            "id": "T-RESULT-STALE", "entity_version": 5,
            "status": "DONE", "state": "DONE", "verdict": "INCONCLUSIVE",
            "inbox_ref": "gateway:tcc-stale",
        }))
        receipt = apply_mutation_request(self.root, {
            "request_id": "REQ-INBOX-RESULT-STALE",
            "entity_kind": "test", "entity_name": "T-RESULT-STALE", "expected_version": 4,
            "changes": {"status": "DONE", "state": "DONE", "verdict": "INCONCLUSIVE",
                        "inbox_ref": "gateway:tcc-stale"},
            "writer_role": "EXECUTOR", "event_type": "TEST_RESULT_RECORDED",
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
        entity = json.loads((entity_path(self.root, "work", "WORK::NEW")).read_text())
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
        entity = json.loads((entity_path(self.root, "test", "GZSB-01-DESI-INFERENCE-PRIOR-SENSITIVITY")).read_text())
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
        entity = json.loads((entity_path(self.root, "test_group", group_id)).read_text())
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
        entity = json.loads((entity_path(self.root, "hypothesis", hypothesis_id)).read_text())
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
        self.assertFalse((entity_path(self.root, "work", "WORK::NEW")).exists())

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
        self.assertFalse((entity_path(self.root, "test_group", "TEST_GROUP::CAMP-GROWTH-LSS::A")).exists())

    def test_existing_entity_never_accepts_partial_creation_as_generic_no_op(self) -> None:
        path = entity_path(self.root, "artifact", "ARTIFACT::EXISTING")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({
            "id": "ARTIFACT::EXISTING", "entity_version": 1,
            "kind": "EVIDENCE", "status": "RECORDED", "payload": {"value": 1},
        }))
        receipt = apply_mutation_request(self.root, {
            "request_id": "REQ-CREATE-ARTIFACT-DIFFERENT",
            "entity_kind": "artifact", "entity_name": "ARTIFACT::EXISTING",
            "expected_version": 0,
            "changes": {"kind": "EVIDENCE", "status": "RECORDED"},
            "writer_role": "LEARNER", "event_type": "ARTIFACT_RECORDED",
        })
        self.assertFalse(receipt["accepted"])
        self.assertEqual(receipt["issue"]["code"], "WRITE_CONFLICT_RETRY_REQUIRED")
        self.assertEqual(json.loads(path.read_text())["payload"], {"value": 1})

    def test_exact_durable_artifact_record_replay_is_no_op_but_changed_payload_conflicts(self) -> None:
        path = entity_path(self.root, "artifact", "LEARNING_SIGNAL::STABLE")
        path.parent.mkdir(parents=True, exist_ok=True)
        changes = {
            "kind": "LEARNING_SIGNAL", "status": "RECORDED", "source": "CHATGPT",
            "created_at": "2026-09-26T12:10:01Z", "payload": {"signal": "stable"},
        }
        path.write_text(json.dumps({"id": "LEARNING_SIGNAL::STABLE", "entity_version": 1, **changes}))
        base = {
            "request_id": "REQ-INBOX-STABLE", "entity_kind": "artifact",
            "entity_name": "LEARNING_SIGNAL::STABLE", "expected_version": 0,
            "writer_role": "LEARNER", "event_type": "LEARNING_SIGNAL_RECORDED",
        }
        replay = apply_mutation_request(self.root, {**base, "changes": changes})
        self.assertTrue(replay["accepted"])
        self.assertEqual(replay["status"], "NO_OP")
        self.assertEqual(replay["entity_version"], 1)

        conflict = apply_mutation_request(self.root, {
            **base, "changes": {**changes, "payload": {"signal": "changed"}},
        })
        self.assertFalse(conflict["accepted"])
        self.assertEqual(conflict["issue"]["code"], "WRITE_CONFLICT_RETRY_REQUIRED")
        self.assertEqual(json.loads(path.read_text())["payload"], {"signal": "stable"})

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
        (entity_path(self.root, "work", "W-CLOSE")).write_text(json.dumps({
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

    def test_material_test_mutation_refreshes_live_tower_and_public_projection(self) -> None:
        receipt = apply_mutation_request(self.root, {
            "request_id": "REQ-LIVE-TOWER-1",
            "entity_kind": "test",
            "entity_name": "TEST-LIVE-1",
            "expected_version": 0,
            "changes": {
                "id": "TEST-LIVE-1",
                "status": "READY",
                "domain": "ENGINEERING",
                "title": "Live Tower integration test",
            },
            "writer_role": "ADVISOR",
            "event_type": "TEST_CREATED",
        })

        self.assertTrue(receipt["accepted"])
        self.assertEqual(receipt["readback"], "PASS")
        self.assertEqual(receipt["live_tower_refresh"]["status"], "PASS")
        self.assertEqual(
            receipt["live_tower_refresh"]["stable_file_id"],
            "1m97cFmEkw19yiqD_6FWPG4j1lDCAYM4z",
        )
        self.assertEqual(receipt["projection_refresh"]["status"], "PASS")
        self.assertEqual(receipt["projection_refresh"]["projection_state"], "CURRENT")
        self.assertEqual(
            receipt["projection_refresh"]["tower_revision"],
            receipt["live_tower_refresh"]["revision"],
        )
        self.assertTrue((self.root / "NEXO_TOWER_LIVE.json").exists())
        self.assertTrue((self.root / "projections" / "public" / "latest.json").exists())

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
