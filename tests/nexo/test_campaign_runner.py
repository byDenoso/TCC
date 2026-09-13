from __future__ import annotations

import json
from pathlib import Path

from nexo_control.campaign_runner import execute_plan_bundle
from tests.nexo.test_runner_execution import FakeClient, request


def bundle() -> dict:
    return {
        "schema_version": 1,
        "campaign_id": "NEXO-NOOP-001",
        "campaign_commit": "campaign-sha",
        "attempt": 1,
        "dry_run": False,
        "execution_plan": {},
        "predicted_dispatches": [request()],
        "dispatches": [request()],
    }


def test_execute_bundle_writes_result_and_learning_summary(tmp_path: Path):
    summary = execute_plan_bundle(bundle(), FakeClient(), tmp_path, validator_commit="validator-sha")
    assert summary["ready_for_learning"] is True
    result = json.loads((tmp_path / "results" / "T-ENG001.json").read_text(encoding="utf-8"))
    assert result["validation"]["status"] == "PASSED"
    stored_summary = json.loads((tmp_path / "campaign-summary.json").read_text(encoding="utf-8"))
    assert stored_summary == summary


class BrokenClient(FakeClient):
    def dispatch_workflow(self, workflow, ref, inputs):
        raise RuntimeError("synthetic infrastructure failure")


def test_runner_persists_technical_failure_instead_of_losing_receipt(tmp_path: Path):
    summary = execute_plan_bundle(bundle(), BrokenClient(), tmp_path, validator_commit="validator-sha")
    assert summary["ready_for_learning"] is False
    result = json.loads((tmp_path / "results" / "T-ENG001.json").read_text(encoding="utf-8"))
    assert result["validation"]["status"] == "FAILED"
    assert "ORCHESTRATION_ERROR" in result["validation"]["reasons"][0]
