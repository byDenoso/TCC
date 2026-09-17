from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from . import materialize_role_views
from .mutations import apply_mutation_request
from .service import AgentService
from .test_registry import register_test


class UniversalTestIngressContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "indexes").mkdir(parents=True)
        (self.root / "snapshot").mkdir(parents=True)
        (self.root / "manifests").mkdir(parents=True)
        (self.root / "CONTROL.json").write_text(json.dumps({"mode": "ACTIVE"}), encoding="utf-8")
        (self.root / "snapshot" / "latest.json").write_text(json.dumps({}), encoding="utf-8")
        (self.root / "manifests" / "capabilities.json").write_text(json.dumps({"capabilities": {}}), encoding="utf-8")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _create(self, kind: str, entity_id: str, changes: dict) -> dict:
        return apply_mutation_request(self.root, {
            "request_id": f"REQ-{kind.upper()}-CREATE",
            "entity_kind": kind,
            "entity_name": entity_id,
            "expected_version": 0,
            "changes": {"id": entity_id, **changes},
            "writer_role": "ADVISOR",
            "event_type": f"{kind.upper()}_CREATED",
        })

    def _read(self, kind: str, entity_id: str) -> dict:
        return json.loads((self.root / "entities" / kind / f"{entity_id}.json").read_text(encoding="utf-8"))

    @staticmethod
    def _frozen_test(test_id: str) -> dict:
        return {
            "id": test_id,
            "method": "Run the frozen estimator against the frozen null.",
            "decision_rule": {"PASS": "global_p>=0.05", "STRESS": "global_p<0.05"},
            "outputs": ["scientific_result"],
            "claim_boundary": "No claim beyond the frozen test decision rule.",
        }

    def test_campaign_is_first_class_creatable_entity(self) -> None:
        campaign_id = "CAMPAIGN::COSMOLOGY::PEER-2026"
        receipt = self._create("campaign", campaign_id, {
            "domain": "COSMOLOGY",
            "project_id": "PROJECT::PEER",
            "label": "PEER 2026",
            "status": "ACTIVE",
        })
        self.assertTrue(receipt["accepted"])
        self.assertEqual(receipt["readback"], "PASS")
        entity = self._read("campaign", campaign_id)
        self.assertEqual(entity["domain"], "COSMOLOGY")
        self.assertEqual(entity["project_id"], "PROJECT::PEER")

    def test_run_is_first_class_creatable_entity(self) -> None:
        run_id = "RUN::TEST-D04::0002"
        receipt = self._create("run", run_id, {
            "domain": "COSMOLOGY",
            "parent_id": "TEST::D04",
            "operational_status": "QUEUED",
            "analytical_status": "UNASSESSED",
            "status": "QUEUED",
        })
        self.assertTrue(receipt["accepted"])
        self.assertEqual(receipt["readback"], "PASS")
        entity = self._read("run", run_id)
        self.assertEqual(entity["parent_id"], "TEST::D04")
        self.assertEqual(entity["analytical_status"], "UNASSESSED")

    def test_register_test_canonicalizes_hierarchy_before_dispatch(self) -> None:
        registration = register_test(
            self.root,
            test_id="TEST::PEER::D04",
            domain="cosmology",
            title="D04 anchor-free profile",
            objective="Test anchor-free profile evidence.",
            campaign_id="CAMPAIGN::COSMOLOGY::PEER-2026",
            campaign_title="PEER 2026",
            test_group_id="TEST_GROUP::PEER_DETECTION_BATTERY",
            test_group_title="PEER Detection Battery",
            project_id="PROJECT::PEER",
            capability_id="CAPABILITY::PEER_PROFILE",
            correlation_id="CORR-PEER-D04-001",
        )

        self.assertTrue(registration["dispatch_ready"])
        self.assertEqual(registration["readback"], "PASS")
        self.assertEqual(registration["domain"], "COSMOLOGY")
        self.assertEqual(registration["run_id"], "RUN::TEST::PEER::D04::0001")

        campaign = self._read("campaign", registration["campaign_id"])
        group = self._read("test_group", registration["test_group_id"])
        test = self._read("test", registration["test_id"])
        run = self._read("run", registration["run_id"])

        self.assertEqual(campaign["parent_id"], "PROJECT::PEER")
        self.assertEqual(group["parent_id"], registration["campaign_id"])
        self.assertEqual(test["parent_id"], registration["test_group_id"])
        self.assertEqual(test["campaign_id"], registration["campaign_id"])
        self.assertEqual(test["operational_status"], "QUEUED")
        self.assertEqual(test["analytical_status"], "UNASSESSED")
        self.assertEqual(test["current_run_id"], registration["run_id"])
        self.assertEqual(test["run_ids"], [registration["run_id"]])
        self.assertEqual(run["test_id"], registration["test_id"])
        self.assertEqual(run["parent_id"], registration["test_id"])
        self.assertEqual(run["correlation_id"], "CORR-PEER-D04-001")

        second = register_test(
            self.root,
            test_id="TEST::PEER::D04",
            domain="COSMOLOGY",
            title="D04 anchor-free profile",
            objective="Test anchor-free profile evidence.",
            campaign_id="CAMPAIGN::COSMOLOGY::PEER-2026",
            campaign_title="PEER 2026",
            test_group_id="TEST_GROUP::PEER_DETECTION_BATTERY",
            test_group_title="PEER Detection Battery",
            project_id="PROJECT::PEER",
            capability_id="CAPABILITY::PEER_PROFILE",
            correlation_id="CORR-PEER-D04-002",
        )
        self.assertEqual(second["run_id"], "RUN::TEST::PEER::D04::0002")
        updated_test = self._read("test", second["test_id"])
        self.assertEqual(updated_test["current_run_id"], second["run_id"])
        self.assertEqual(updated_test["run_ids"], [registration["run_id"], second["run_id"]])
        self.assertEqual(updated_test["analytical_status"], "UNASSESSED")

    def test_register_test_with_frozen_contract_creates_scheduler_visible_work(self) -> None:
        test_id = "TEST::VISIBLE::001"
        registration = register_test(
            self.root,
            test_id=test_id,
            domain="COSMOLOGY",
            title="Visibility invariant",
            objective="Prove a dispatch-ready TEST is visible to the executor.",
            campaign_id="CAMP-VISIBLE-001",
            campaign_title="Visibility invariant campaign",
            frozen_test=self._frozen_test(test_id),
            correlation_id="CORR-VISIBLE-001",
        )

        self.assertTrue(registration["scheduler_visible"])
        self.assertEqual(registration["work_id"], f"WORK::{test_id}")
        work = self._read("work", registration["work_id"])
        self.assertEqual(work["test_id"], test_id)
        self.assertEqual(work["owner_role"], "EXECUTOR")
        self.assertEqual(work["status"], "READY")
        self.assertEqual(work["frozen_test"], self._frozen_test(test_id))

        materialize_role_views(self.root)
        queue_ids = {item["id"] for item in AgentService(self.root).queue_for("EXECUTOR")}
        self.assertIn(registration["work_id"], queue_ids)

    def test_ready_canonical_test_can_never_be_invisible_to_executor(self) -> None:
        test_id = "T-ORPHAN-READY-001"
        self._create("test", test_id, {
            "domain": "COSMOLOGY",
            "campaign_id": "CAMP-ORPHAN-001",
            "state": "READY",
            "mechanism": "FROZEN_ORPHAN_VISIBILITY_PROBE",
            "input_contract": {"dataset": "frozen"},
            "estimator_contract": {"primary": "frozen estimator"},
            "null_contract": {"primary": "frozen null"},
            "decision_contract": {"PASS": "global_p>=0.05", "STRESS": "global_p<0.05"},
            "claim_boundary": "Visibility repair cannot alter the frozen scientific contract.",
            "scientific_result": None,
        })

        self.assertFalse((self.root / "entities" / "work" / f"WORK::{test_id}.json").exists())
        materialize_role_views(self.root)

        repaired = self._read("work", f"WORK::{test_id}")
        self.assertEqual(repaired["test_id"], test_id)
        self.assertEqual(repaired["owner_role"], "EXECUTOR")
        self.assertEqual(repaired["status"], "READY")
        self.assertTrue(repaired["scheduler_visibility_repair"])
        self.assertEqual(repaired["frozen_test"]["claim_boundary"], "Visibility repair cannot alter the frozen scientific contract.")

        queue_ids = {item["id"] for item in AgentService(self.root).queue_for("EXECUTOR")}
        self.assertIn(f"WORK::{test_id}", queue_ids)

    def test_check_is_not_promoted_by_canonical_mutation_writer(self) -> None:
        receipt = self._create("check", "CHECK::LINT::001", {"status": "PASS"})
        self.assertFalse(receipt["accepted"])
        self.assertFalse((self.root / "entities" / "check" / "CHECK::LINT::001.json").exists())


if __name__ == "__main__":
    unittest.main()
