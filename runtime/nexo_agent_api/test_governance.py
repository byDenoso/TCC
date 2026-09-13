from __future__ import annotations

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

    def test_l4_accepts_allowlisted_policy_with_evidence(self) -> None:
        receipt = apply_mutation_request(self.root, {
            "request_id": "REQ-L4-PASS",
            "entity_kind": "governance",
            "entity_name": "NEXO_RSI_POLICY",
            "expected_version": 1,
            "changes": {"retry_limit": 4, "parallelism": 2},
            "writer_role": "EMERGENT",
            "event_type": "POLICY_PROMOTION",
            "autonomy_level": "L4",
            "governance_evidence": self.evidence(),
        })
        self.assertTrue(receipt["accepted"])
        self.assertEqual(receipt["autonomy_level"], "L4")
        self.assertEqual(receipt["governance_gate"], "PASS")

    def test_l4_rejects_non_allowlisted_key(self) -> None:
        receipt = apply_mutation_request(self.root, {
            "request_id": "REQ-L4-BAD-KEY",
            "entity_kind": "governance",
            "entity_name": "NEXO_RSI_POLICY",
            "expected_version": 1,
            "changes": {"writer_authority": "EMERGENT"},
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
