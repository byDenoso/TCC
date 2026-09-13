from __future__ import annotations

# Kept as a dedicated module so CI must execute the governance boundary explicitly.
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from .mutations import apply_mutation_request


class GovernanceGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "indexes").mkdir(parents=True)
        (self.root / "entities" / "work").mkdir(parents=True)
        (self.root / "entities" / "governance").mkdir(parents=True)
        (self.root / "entities" / "strategy").mkdir(parents=True)
        (self.root / "snapshot").mkdir(parents=True)
        (self.root / "manifests").mkdir(parents=True)
        (self.root / "CONTROL.json").write_text(json.dumps({"mode": "ACTIVE"}), encoding="utf-8")
        (self.root / "snapshot" / "latest.json").write_text(json.dumps({}), encoding="utf-8")
        (self.root / "manifests" / "capabilities.json").write_text(json.dumps({"capabilities": {}}), encoding="utf-8")
        (self.root / "entities" / "governance" / "NEXO_RSI_POLICY.json").write_text(json.dumps({
            "id": "NEXO_RSI_POLICY",
            "entity_version": 1,
            "retry_limit": 3,
            "parallelism": 1,
        }), encoding="utf-8")
        (self.root / "entities" / "strategy" / "L3_STRATEGY.json").write_text(json.dumps({
            "id": "L3_STRATEGY",
            "entity_version": 1,
            "priority": "normal",
        }), encoding="utf-8")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    @staticmethod
    def evidence() -> dict[str, object]:
        return {
            "baseline_ref": "baseline:v1",
            "hypothesis_ref": "hypothesis:retry-v2",
            "evidence_refs": ["test:001"],
            "metric": "successful_completion_rate",
            "observed_gain": 0.08,
            "regression_passed": True,
            "rollback_ref": "policy:v1",
        }

    @staticmethod
    def proposal_hash(request: dict[str, object]) -> str:
        payload = {
            "entity_kind": request["entity_kind"],
            "entity_name": request["entity_name"],
            "expected_version": request["expected_version"],
            "changes": request["changes"],
        }
        encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def test_l3_requires_declared_intent_before_autonomous_execution(self) -> None:
        receipt = apply_mutation_request(self.root, {
            "request_id": "REQ-L3-NO-INTENT",
            "entity_kind": "strategy",
            "entity_name": "L3_STRATEGY",
            "expected_version": 1,
            "changes": {"priority": "high"},
            "writer_role": "LEARNER",
            "event_type": "STRATEGY_ADJUSTMENT",
            "autonomy_level": "L3",
        })
        self.assertFalse(receipt["accepted"])
        self.assertEqual(receipt["issue"]["code"], "L3_INTENT_REQUIRED")

    def test_l3_executes_with_intent_and_returns_execution_report(self) -> None:
        intent = {
            "summary": "Raise strategy priority for the next decision cycle.",
            "reason": "Recent verified outcomes increased expected decision value.",
            "metric": "expected_decision_value",
        }
        receipt = apply_mutation_request(self.root, {
            "request_id": "REQ-L3-REPORT",
            "entity_kind": "strategy",
            "entity_name": "L3_STRATEGY",
            "expected_version": 1,
            "changes": {"priority": "high"},
            "writer_role": "LEARNER",
            "event_type": "STRATEGY_ADJUSTMENT",
            "autonomy_level": "L3",
            "l3_intent": intent,
        })
        self.assertTrue(receipt["accepted"])
        self.assertEqual(receipt["autonomy_level"], "L3")
        self.assertEqual(receipt["governance_gate"], "PASS_WITH_REPORT")
        self.assertEqual(receipt["l3_report"]["status"], "EXECUTED")
        self.assertEqual(receipt["l3_report"]["intent"], intent)
        self.assertEqual(receipt["l3_report"]["requested_changes"], {"priority": "high"})
        self.assertEqual(receipt["l3_report"]["entity_version"], 2)
        self.assertEqual(receipt["l3_report"]["readback"], "PASS")
        self.assertTrue(receipt["l3_report"]["event_id"])

    def test_l4_requires_evidence(self) -> None:
        receipt = apply_mutation_request(self.root, {
            "request_id": "REQ-L4-EVIDENCE",
            "entity_kind": "governance",
            "entity_name": "NEXO_RSI_POLICY",
            "expected_version": 1,
            "changes": {"retry_limit": 4},
            "writer_role": "EMERGENT",
            "event_type": "POLICY_PROMOTION",
            "autonomy_level": "L4",
        })
        self.assertFalse(receipt["accepted"])
        self.assertEqual(receipt["issue"]["code"], "L4_PROMOTION_EVIDENCE_REQUIRED")

    def test_l4_requires_human_approval_after_evidence(self) -> None:
        request = {
            "request_id": "REQ-L4-APPROVAL",
            "entity_kind": "governance",
            "entity_name": "NEXO_RSI_POLICY",
            "expected_version": 1,
            "changes": {"retry_limit": 4, "parallelism": 2},
            "writer_role": "EMERGENT",
            "event_type": "POLICY_PROMOTION",
            "autonomy_level": "L4",
            "governance_evidence": self.evidence(),
        }
        receipt = apply_mutation_request(self.root, request)
        self.assertFalse(receipt["accepted"])
        self.assertEqual(receipt["autonomy_level"], "L4")
        self.assertEqual(receipt["governance_gate"], "L4_APPROVAL_REQUIRED")
        self.assertEqual(receipt["issue"]["code"], "L4_HUMAN_APPROVAL_REQUIRED")
        self.assertEqual(receipt["proposal_hash"], self.proposal_hash(request))

    def test_l4_accepts_exact_human_approved_proposal(self) -> None:
        request = {
            "request_id": "REQ-L4-PASS",
            "entity_kind": "governance",
            "entity_name": "NEXO_RSI_POLICY",
            "expected_version": 1,
            "changes": {"retry_limit": 4, "parallelism": 2},
            "writer_role": "EMERGENT",
            "event_type": "POLICY_PROMOTION",
            "autonomy_level": "L4",
            "governance_evidence": self.evidence(),
        }
        request["human_approval"] = {
            "approved": True,
            "approved_by": "HUMAN",
            "approval_ref": "user-approval:2026-09-13:l4-001",
            "proposal_hash": self.proposal_hash(request),
        }
        receipt = apply_mutation_request(self.root, request)
        self.assertTrue(receipt["accepted"])
        self.assertEqual(receipt["autonomy_level"], "L4")
        self.assertEqual(receipt["governance_gate"], "L4_HUMAN_APPROVED")
        self.assertEqual(receipt["proposal_hash"], request["human_approval"]["proposal_hash"])

    def test_l4_rejects_non_allowlisted_key(self) -> None:
        receipt = apply_mutation_request(self.root, {
            "request_id": "REQ-L4-BAD-KEY",
            "entity_kind": "governance",
            "entity_name": "NEXO_RSI_POLICY",
            "expected_version": 1,
            "changes": {"unrecognized_policy_option": True},
            "writer_role": "EMERGENT",
            "event_type": "POLICY_PROMOTION",
            "autonomy_level": "L4",
            "governance_evidence": self.evidence(),
        })
        self.assertFalse(receipt["accepted"])
        self.assertEqual(receipt["issue"]["code"], "L4_POLICY_KEY_NOT_ALLOWLISTED")

    def test_l5_boundary_overrides_declared_lower_level(self) -> None:
        receipt = apply_mutation_request(self.root, {
            "request_id": "REQ-L5-BOUNDARY",
            "entity_kind": "governance",
            "entity_name": "NEXO_RSI_POLICY",
            "expected_version": 1,
            "changes": {"human_override": False},
            "writer_role": "EMERGENT",
            "event_type": "POLICY_CHANGE",
            "autonomy_level": "L0",
        })
        self.assertFalse(receipt["accepted"])
        self.assertEqual(receipt["issue"]["code"], "L5_BOUNDARY_HUMAN_AUTHORITY_REQUIRED")
        self.assertEqual(receipt["autonomy_level"], "L5")


if __name__ == "__main__":
    unittest.main()
