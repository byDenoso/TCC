from __future__ import annotations

import copy

import pytest

from nexo_control.contracts import validate_campaign


def valid_campaign() -> dict:
    return {
        "schema_version": 1,
        "campaign_id": "NEXO-NOOP-001",
        "domain": "engineering",
        "question": "Can the GitHub-native control plane execute a deterministic no-op campaign?",
        "status": "PLANNED",
        "budget": {
            "max_tests": 3,
            "max_parallel": 2,
            "max_retries_per_test": 1,
            "max_runtime_minutes": 30,
        },
        "tests": [
            {
                "test_id": "T-ENG001",
                "executor": "github_workflow",
                "workflow": "nexo_noop",
                "ref": "nexo-gh-orchestrator-20260913",
                "inputs": {"should_pass": True},
                "depends_on": [],
                "promotion": {
                    "require_workflow_success": True,
                    "require_artifact": True,
                    "validator": "contract_test_pass",
                },
            },
            {
                "test_id": "T-ENG002",
                "executor": "github_workflow",
                "workflow": "nexo_noop",
                "ref": "nexo-gh-orchestrator-20260913",
                "inputs": {"should_pass": True},
                "depends_on": ["T-ENG001"],
                "promotion": {
                    "require_workflow_success": True,
                    "require_artifact": True,
                    "validator": "artifact_presence_only",
                },
            },
        ],
    }


def test_valid_campaign_is_accepted():
    campaign = valid_campaign()
    assert validate_campaign(campaign) == campaign


def test_unknown_executor_is_rejected():
    campaign = valid_campaign()
    campaign["tests"][0]["executor"] = "shell"
    with pytest.raises(ValueError, match="unknown executor"):
        validate_campaign(campaign)


def test_unknown_validator_is_rejected():
    campaign = valid_campaign()
    campaign["tests"][0]["promotion"]["validator"] = "magic"
    with pytest.raises(ValueError, match="unknown validator"):
        validate_campaign(campaign)


def test_duplicate_test_ids_are_rejected():
    campaign = valid_campaign()
    duplicate = copy.deepcopy(campaign["tests"][0])
    campaign["tests"].append(duplicate)
    with pytest.raises(ValueError, match="duplicate test_id"):
        validate_campaign(campaign)


def test_missing_dependency_is_rejected():
    campaign = valid_campaign()
    campaign["tests"][1]["depends_on"] = ["T-MISSING"]
    with pytest.raises(ValueError, match="missing dependency"):
        validate_campaign(campaign)


def test_dependency_cycle_is_rejected():
    campaign = valid_campaign()
    campaign["tests"][0]["depends_on"] = ["T-ENG002"]
    with pytest.raises(ValueError, match="dependency cycle"):
        validate_campaign(campaign)


def test_budget_overflow_is_rejected():
    campaign = valid_campaign()
    campaign["budget"]["max_tests"] = 1
    with pytest.raises(ValueError, match="max_tests"):
        validate_campaign(campaign)


def test_max_parallel_cannot_exceed_max_tests():
    campaign = valid_campaign()
    campaign["budget"]["max_parallel"] = 4
    campaign["budget"]["max_tests"] = 3
    with pytest.raises(ValueError, match="max_parallel"):
        validate_campaign(campaign)


@pytest.mark.parametrize("bad_key", ["run", "command", "shell", "script"])
def test_command_injection_fields_are_rejected(bad_key):
    campaign = valid_campaign()
    campaign["tests"][0]["inputs"][bad_key] = "forbidden"
    with pytest.raises(ValueError, match="forbidden key"):
        validate_campaign(campaign)
