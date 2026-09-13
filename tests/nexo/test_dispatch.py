from __future__ import annotations

import pytest

from nexo_control.dispatch import WORKFLOW_REGISTRY, build_dispatch_request, build_dispatches, make_correlation_id
from nexo_control.contracts import validate_campaign
from tests.nexo.test_campaign_contract import valid_campaign


def test_correlation_id_is_stable_and_attempt_specific():
    a = make_correlation_id("NEXO-NOOP-001", "T-ENG001", 1, "abcdef123456")
    b = make_correlation_id("NEXO-NOOP-001", "T-ENG001", 1, "abcdef123456")
    c = make_correlation_id("NEXO-NOOP-001", "T-ENG001", 2, "abcdef123456")
    assert a == b
    assert a != c
    assert a.startswith("NEXO_NEXO-NOOP-001_T-ENG001_1_abcdef12")


def test_registered_workflow_resolves_to_repository_workflow():
    campaign = valid_campaign()
    test = campaign["tests"][0]
    request = build_dispatch_request(campaign["campaign_id"], test, "CORR")
    assert request["workflow"] == ".github/workflows/nexo-noop-executor.yml"
    assert request["inputs"]["correlation_id"] == "CORR"
    assert request["inputs"]["campaign_id"] == campaign["campaign_id"]
    assert request["inputs"]["test_id"] == test["test_id"]


def test_unregistered_workflow_is_rejected():
    campaign = valid_campaign()
    test = dict(campaign["tests"][0])
    test["workflow"] = "unregistered"
    with pytest.raises(ValueError, match="unregistered workflow"):
        build_dispatch_request(campaign["campaign_id"], test, "CORR")


def test_inputs_remain_data():
    campaign = valid_campaign()
    test = campaign["tests"][0]
    test["inputs"] = {"note": "harmless value", "should_pass": True}
    request = build_dispatch_request(campaign["campaign_id"], test, "CORR")
    assert request["inputs"]["note"] == "harmless value"
    assert request["inputs"]["should_pass"] is True


def test_dry_run_produces_prediction_but_zero_dispatches():
    campaign = validate_campaign(valid_campaign())
    bundle = build_dispatches(campaign, sha="abcdef123456", attempt=1, dry_run=True)
    assert bundle["dispatches"] == []
    assert len(bundle["predicted_dispatches"]) == 1
    assert bundle["dry_run"] is True


def test_registry_is_minimal_in_v01():
    assert WORKFLOW_REGISTRY == {"nexo_noop": ".github/workflows/nexo-noop-executor.yml"}
