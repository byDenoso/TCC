from __future__ import annotations

import pytest

from nexo_control.contracts import validate_campaign
from nexo_control.planner import build_execution_plan
from nexo_control.state import transition_campaign_state, transition_test_state
from tests.nexo.test_campaign_contract import valid_campaign


def test_planner_enforces_max_parallel():
    campaign = valid_campaign()
    campaign["budget"]["max_parallel"] = 1
    plan = build_execution_plan(validate_campaign(campaign))
    assert [item["test_id"] for item in plan["runnable_now"]] == ["T-ENG001"]
    assert plan["dry_run_safe"] is True


def test_dependency_is_blocked_until_parent_passes():
    campaign = validate_campaign(valid_campaign())
    plan = build_execution_plan(campaign)
    assert plan["blocked"][0]["test_id"] == "T-ENG002"
    assert plan["blocked"][0]["reason"] == "WAITING_DEPENDENCIES"

    resumed = build_execution_plan(campaign, completed={"T-ENG001": "PASSED"})
    assert [item["test_id"] for item in resumed["runnable_now"]] == ["T-ENG002"]


def test_failed_dependency_blocks_child():
    campaign = validate_campaign(valid_campaign())
    plan = build_execution_plan(campaign, completed={"T-ENG001": "FAILED"})
    child = next(item for item in plan["blocked"] if item["test_id"] == "T-ENG002")
    assert child["reason"] == "DEPENDENCY_NOT_PROMOTED"


def test_retry_budget_is_exposed_and_bounded():
    campaign = validate_campaign(valid_campaign())
    plan = build_execution_plan(campaign, attempts={"T-ENG001": 2})
    first = next(item for item in plan["blocked"] if item["test_id"] == "T-ENG001")
    assert first["reason"] == "RETRY_BUDGET_EXCEEDED"


def test_legal_test_transitions():
    state = "PLANNED"
    for target in ["READY", "DISPATCHED", "RUNNING", "VALIDATING", "PASSED"]:
        state = transition_test_state(state, target)
    assert state == "PASSED"


def test_illegal_test_transition_is_rejected():
    with pytest.raises(ValueError, match="illegal test transition"):
        transition_test_state("PLANNED", "PASSED")


def test_legal_campaign_transitions():
    state = "PLANNED"
    for target in ["READY", "RUNNING", "VALIDATING", "LEARNING", "CLOSED"]:
        state = transition_campaign_state(state, target)
    assert state == "CLOSED"


def test_illegal_campaign_transition_is_rejected():
    with pytest.raises(ValueError, match="illegal campaign transition"):
        transition_campaign_state("PLANNED", "CLOSED")
