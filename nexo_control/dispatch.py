from __future__ import annotations

import re
from typing import Any

from nexo_control.planner import build_execution_plan

WORKFLOW_REGISTRY = {
    "nexo_noop": ".github/workflows/nexo-noop-executor.yml",
}


def _clean(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", value)


def make_correlation_id(campaign_id: str, test_id: str, attempt: int, sha: str) -> str:
    return f"NEXO_{_clean(campaign_id)}_{_clean(test_id)}_{int(attempt)}_{_clean(sha)[:8]}"


def build_dispatch_request(campaign_id: str, test: dict[str, Any], correlation_id: str) -> dict[str, Any]:
    alias = test["workflow"]
    if alias not in WORKFLOW_REGISTRY:
        raise ValueError(f"unregistered workflow: {alias}")
    inputs = dict(test.get("inputs") or {})
    inputs.update(
        {
            "correlation_id": correlation_id,
            "campaign_id": campaign_id,
            "test_id": test["test_id"],
        }
    )
    return {
        "test_id": test["test_id"],
        "workflow_alias": alias,
        "workflow": WORKFLOW_REGISTRY[alias],
        "ref": test["ref"],
        "correlation_id": correlation_id,
        "inputs": inputs,
        "validator": test["promotion"]["validator"],
    }


def build_dispatches(
    campaign: dict[str, Any],
    *,
    sha: str,
    attempt: int,
    dry_run: bool,
    completed: dict[str, str] | None = None,
    attempts: dict[str, int] | None = None,
) -> dict[str, Any]:
    plan = build_execution_plan(campaign, completed=completed, attempts=attempts)
    predicted = []
    for test in plan["runnable_now"]:
        correlation_id = make_correlation_id(campaign["campaign_id"], test["test_id"], attempt, sha)
        predicted.append(build_dispatch_request(campaign["campaign_id"], test, correlation_id))
    return {
        "schema_version": 1,
        "campaign_id": campaign["campaign_id"],
        "dry_run": bool(dry_run),
        "execution_plan": plan,
        "predicted_dispatches": predicted,
        "dispatches": [] if dry_run else predicted,
    }
