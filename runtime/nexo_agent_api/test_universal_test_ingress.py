from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from . import materialize_role_views
from .mutations import apply_mutation_request
from .service import AgentService, TowerAgentIssue
from .scheduler_visibility import ensure_scheduler_visibility
from .evolution import prereg_hash
from .test_registry import register_test
from runtime.nexo_agent_api.tower_paths import entity_path


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

        self.recipes = self.root / "recipes"
        (self.recipes / "smoke").mkdir(parents=True)
        (self.recipes / "audit_recipe.py").write_text("result = 1\n")
        (self.recipes / "smoke/audit_recipe.json").write_text("{}")
        self.env = patch.dict(os.environ, {"NEXO_RECIPE_ROOT": str(self.recipes)})
        self.env.start()

    def tearDown(self) -> None:
        self.env.stop()
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
        return json.loads((entity_path(self.root, kind, entity_id)).read_text(encoding="utf-8"))

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

        self.assertFalse(registration["dispatch_ready"])
        self.assertFalse(registration["readiness"]["eligible"])
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
        self.assertEqual(test["operational_status"], "DRAFT")
        self.assertEqual(run["status"], "DRAFT")
        self.assertNotIn("attempt_id", test)
        self.assertNotIn("battery_id", test)
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

    def test_legacy_frozen_metadata_does_not_invent_executable_work(self) -> None:
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

        self.assertFalse(registration["scheduler_visible"])
        self.assertFalse(registration["dispatch_ready"])
        self.assertIsNone(registration["work_id"])
        self.assertEqual(self._read("test", test_id)["frozen_test"], self._frozen_test(test_id))
        self.assertFalse(entity_path(self.root, "work", f"WORK::{test_id}").exists())

    def _ready_test(self, test_id):
        test = {"id": test_id, "domain": "COSMOLOGY", "status": "READY", "state": "READY",
                "question": "Is the generated mean bounded?", "null": "Unbounded", "rival": "Bounded",
                "method": "Seeded sample mean", "dataset_and_selection": "Frozen generated sample",
                "success_criteria": "abs(mean)<1", "kill_criteria": "abs(mean)>=1",
                "claim_boundary": "No broader claim", "frozen_at": "2026-09-30T10:00:00Z",
                "recipe": "audit_recipe", "recipe_params": {"seed": 17},
                "data_binding": {"status": "BOUND", "inputs": [{"name": "sample", "kind": "generated",
                    "generator": "v1", "seed": 17, "sha256": "a" * 64}]}}
        test["prereg_hash"] = prereg_hash(test_id, test)
        return test

    def test_ready_canonical_test_can_never_be_invisible_to_executor(self) -> None:
        test_id = "T-ORPHAN-READY-001"
        definition = self._ready_test(test_id)
        receipt = self._create("test", test_id, definition)
        self.assertTrue(receipt["accepted"], receipt)

        self.assertFalse((self.root / "entities" / "work" / f"WORK::{test_id}.json").exists())
        materialize_role_views(self.root)

        repaired = self._read("work", f"WORK::{test_id}")
        self.assertEqual(repaired["test_id"], test_id)
        self.assertEqual(repaired["owner_role"], "EXECUTOR")
        self.assertEqual(repaired["status"], "READY")
        self.assertTrue(repaired["scheduler_visibility_repair"])
        self.assertEqual(repaired["frozen_test"]["claim_boundary"], "No broader claim")

        queue_ids = {item["id"] for item in AgentService(self.root).queue_for("EXECUTOR")}
        self.assertIn(f"WORK::{test_id}", queue_ids)

    def test_legacy_ready_without_binding_cannot_be_projected_as_executable(self):
        test_id = "LEGACY-READY"
        test = {"id": test_id, "domain": "COSMOLOGY", "status": "READY",
                "frozen_test": self._frozen_test(test_id)}
        # Historical state can predate admission; visibility must not launder it.
        path = entity_path(self.root, "test", test_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(test))
        result = ensure_scheduler_visibility(self.root, test)
        self.assertFalse(result["visible"])
        self.assertIn("INPUT_PROVENANCE_INCOMPLETE", result["readiness"]["reasons"])
        self.assertEqual(result["blocker_class"], "EXECUTION_PREREQUISITES_MISSING")
        self.assertFalse(entity_path(self.root, "work", f"WORK::{test_id}").exists())

    def test_stale_existing_work_does_not_bypass_readiness(self):
        test = self._ready_test("STALE-WORK")
        self.assertTrue(self._create("test", test["id"], test)["accepted"])
        self.assertTrue(ensure_scheduler_visibility(self.root, test)["visible"])
        binding = test.pop("data_binding")
        self.assertFalse(ensure_scheduler_visibility(self.root, test)["visible"])
        work = self._read("work", f"WORK::{test['id']}")
        self.assertEqual(work["status"], "WAIT_DEPENDENCY")
        self.assertEqual(work["owner_role"], "EXECUTOR")
        test["data_binding"] = binding
        self.assertTrue(ensure_scheduler_visibility(self.root, test)["visible"])
        self.assertEqual(self._read("work", f"WORK::{test['id']}")["status"], "READY")

    def test_terminal_registration_does_not_reopen_or_create_partial_graph(self):
        test_id = "FINISHED"
        self.assertTrue(self._create("test", test_id, {"domain": "COSMOLOGY", "status": "DONE"})["accepted"])
        before = self._read("test", test_id)
        with self.assertRaises(TowerAgentIssue):
            register_test(self.root, test_id=test_id, domain="COSMOLOGY", title="Existing", objective="Existing",
                          campaign_id="NEW-CAMPAIGN")
        self.assertEqual(self._read("test", test_id), before)
        self.assertFalse(entity_path(self.root, "campaign", "NEW-CAMPAIGN").exists())

    def test_reserved_execution_is_not_replaced_by_registration(self):
        from .evolution import battery_requests
        from .tower_apply import apply_requests
        test = self._ready_test("RESERVED")
        self.assertTrue(self._create("test", test["id"], test)["accepted"])
        receipts = apply_requests(self.root, battery_requests({"created_at": "2026-09-30T10:01:00Z"},
            {"battery_id": "bat-registration-guard", "tests": [{"test_id": test["id"],
                "recipe": test["recipe"], "params": test["recipe_params"]}]}, self.root))
        self.assertTrue(all(r.get("accepted") for r in receipts), receipts)
        before = self._read("test", test["id"])
        self.assertEqual(before["status"], "QUEUED")
        with self.assertRaises(TowerAgentIssue):
            register_test(self.root, test_id=test["id"], domain="COSMOLOGY", title="Reserved",
                          objective="Existing execution", campaign_id="RESERVED-CAMPAIGN")
        self.assertEqual(self._read("test", test["id"]), before)
        self.assertFalse(entity_path(self.root, "campaign", "RESERVED-CAMPAIGN").exists())

    def test_stale_projection_does_not_take_over_someone_elses_work(self):
        test = self._ready_test("OWNED")
        self.assertTrue(self._create("test", test["id"], test)["accepted"])
        work_id = f"WORK::{test['id']}"
        self.assertTrue(self._create("work", work_id, {"test_id": test["id"], "owner_role": "ADVISOR",
            "status": "CHECKPOINTED"})["accepted"])
        before = self._read("work", work_id)
        test.pop("data_binding")
        self.assertFalse(ensure_scheduler_visibility(self.root, test)["visible"])
        self.assertEqual(self._read("work", work_id), before)

    def test_check_is_not_promoted_by_canonical_mutation_writer(self) -> None:
        receipt = self._create("check", "CHECK::LINT::001", {"status": "PASS"})
        self.assertFalse(receipt["accepted"])
        self.assertFalse((entity_path(self.root, "check", "CHECK::LINT::001")).exists())


if __name__ == "__main__":
    unittest.main()
