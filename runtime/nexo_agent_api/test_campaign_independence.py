"""Regression: a blocked lane must not serialize an unrelated scientific TEST.

This is a read-only campaign decision test suite. DISPATCH is a candidate
recommendation, not a Writer reservation or permission to start a RUN.
"""
from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from .campaign_continuation import CampaignFrontierResolver
from .service import AgentService
from .tower_paths import entity_path


class IndependentCampaignContinuationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        for kind in ("test_group", "test", "work", "run"):
            (self.root / "entities" / kind).mkdir(parents=True, exist_ok=True)
        (self.root / "manifests").mkdir(parents=True, exist_ok=True)
        (self.root / "manifests" / "capabilities.json").write_text(
            json.dumps({"capabilities": {
                "approved_executor": {
                    "roles": ["EXECUTOR"], "status": "ACTIVE",
                    "backend": "chatgpt_runtime", "task_id": "approved_science",
                },
            }}),
            encoding="utf-8",
        )
        self.put("test_group", "CAMP-IND", status="ACTIVE",
                 execution_order=["TEST-A", "TEST-B", "TEST-C"])

    def put(self, kind: str, entity_id: str, **fields) -> None:
        data = {"id": entity_id, **fields}
        if kind == "test":
            data.setdefault("campaign_id", "CAMP-IND")
        if kind == "run":
            data.setdefault("campaign_id", "CAMP-IND")
        path = entity_path(self.root, kind, entity_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data), encoding="utf-8")

    def runnable(self, test_id: str) -> None:
        self.put("test", test_id, status="READY", capability_id="approved_executor")

    def checkpoint(self, test_id: str) -> None:
        self.put("test", test_id, status="READY", current_run_id="RUN-"+test_id)
        self.put("run", "RUN-"+test_id, test_id=test_id, status="CHECKPOINTED")

    def active_run(self, test_id: str) -> None:
        self.put("test", test_id, status="READY", current_run_id="RUN-"+test_id)
        self.put("run", "RUN-"+test_id, test_id=test_id, status="RUNNING")

    def resolve(self) -> dict:
        return CampaignFrontierResolver(self.root).resolve("CAMP-IND")

    def continue_work(self) -> dict:
        with patch.dict(os.environ, {"NEXO_CAMPAIGN_CONTINUATION_MODE": "ACTIVE"}):
            return AgentService(self.root).continue_campaign("CAMP-IND")

    def test_checkpoint_does_not_hide_independent_ready_test(self) -> None:
        self.checkpoint("TEST-A")
        self.runnable("TEST-B")
        self.put("test", "TEST-C", status="READY", depends_on=["TEST-A"])
        result = self.resolve()
        self.assertEqual(result["ready"], ["TEST-B"])
        self.assertEqual(result["recoverable"], ["TEST-A"])
        self.assertEqual(result["blocked"], ["TEST-C"])
        self.assertEqual(result["next_test_ids"], ["TEST-B", "TEST-A"])

    def test_frozen_dependency_is_not_removed(self) -> None:
        self.put("test", "TEST-A", status="READY")
        self.put("test", "TEST-B", status="READY", depends_on=["TEST-A"])
        result = self.resolve()
        self.assertEqual(result["ready"], ["TEST-A"])
        self.assertIn("TEST-B", result["blocked"])

    def test_completed_parent_after_child_in_order_satisfies_dependency(self) -> None:
        self.put("test_group", "CAMP-IND", status="ACTIVE",
                 execution_order=["TEST-B", "TEST-A"])
        self.put("test", "TEST-A", status="DONE")
        self.put("test", "TEST-B", status="READY", depends_on=["TEST-A"])
        result = self.resolve()
        self.assertEqual(result["ready"], ["TEST-B"])
        self.assertEqual(result["blocked"], [])

    def test_unbound_first_ready_does_not_hide_second_runnable(self) -> None:
        self.put("test", "TEST-A", status="READY", capability_id="unknown_executor")
        self.runnable("TEST-B")
        result = self.continue_work()
        self.assertEqual((result["action"], result["test_id"]), ("DISPATCH", "TEST-B"))
        self.assertEqual(result["execution"]["status"], "RESOLVED")

    def test_checkpoint_cannot_starve_runnable_independent_test(self) -> None:
        self.checkpoint("TEST-A")
        self.runnable("TEST-B")
        result = self.continue_work()
        self.assertEqual((result["action"], result["test_id"]), ("DISPATCH", "TEST-B"))

    def test_running_run_still_prevents_competing_dispatch(self) -> None:
        self.active_run("TEST-A")
        self.runnable("TEST-B")
        result = self.continue_work()
        self.assertEqual((result["action"], result["test_id"]), ("RESUME", "TEST-A"))
        self.assertEqual(result["frontier"]["ready"], ["TEST-B"])

    def test_checkpoint_is_recovered_if_no_ready_candidate_can_run(self) -> None:
        self.checkpoint("TEST-A")
        self.put("test", "TEST-B", status="READY", capability_id="unknown_executor")
        result = self.continue_work()
        self.assertEqual((result["action"], result["test_id"]), ("RECOVER", "TEST-A"))

    def test_scientific_authorization_gate_stays_closed_per_test(self) -> None:
        self.put("test", "TEST-A", status="READY",
                 blocker_class="AUTHORIZATION_MISSING", capability_id="approved_executor")
        self.runnable("TEST-B")
        result = self.continue_work()
        self.assertEqual((result["action"], result["test_id"]), ("DISPATCH", "TEST-B"))
        self.assertIn("TEST-A", result["frontier"]["blocked"])

    def test_closed_campaign_is_not_reopened(self) -> None:
        self.put("test_group", "CAMP-IND", status="CLOSED")
        self.runnable("TEST-B")
        result = self.continue_work()
        self.assertEqual(result["action"], "TERMINAL")

    def test_shadow_returns_proposal_without_state_change(self) -> None:
        self.runnable("TEST-A")
        with patch.dict(os.environ, {"NEXO_CAMPAIGN_CONTINUATION_MODE": "SHADOW"}):
            result = AgentService(self.root).continue_campaign("CAMP-IND")
        self.assertEqual(result["action"], "SHADOW")
        self.assertEqual(result["proposed_action"], "DISPATCH")
        self.assertEqual(result["test_id"], "TEST-A")
        self.assertEqual(self.resolve()["ready"], ["TEST-A"])


if __name__ == "__main__":
    unittest.main()
