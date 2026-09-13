from __future__ import annotations

import json
import math

import pytest

from nexo_control.results import build_result_envelope, json_safe, validate_result_schema
from nexo_control.validators import run_validator


def execution(status: str = "COMPLETED", conclusion: str = "success", artifacts=None) -> dict:
    return {
        "status": status,
        "conclusion": conclusion,
        "workflow": "nexo-noop-executor.yml",
        "run_id": 123,
        "head_sha": "abc123",
        "artifact_names": list(artifacts if artifacts is not None else ["result-artifact"]),
    }


def test_json_safe_converts_nested_nonfinite_numbers_to_null():
    payload = {"a": float("inf"), "b": [float("nan"), {"c": -float("inf")}], "d": 1.5}
    safe = json_safe(payload)
    assert safe == {"a": None, "b": [None, {"c": None}], "d": 1.5}
    json.dumps(safe, allow_nan=False)


def test_workflow_success_without_artifact_does_not_pass():
    result = run_validator("artifact_presence_only", execution(artifacts=[]), None)
    assert result["status"] == "NOT_PROMOTED"
    assert "REQUIRED_ARTIFACT_MISSING" in result["reasons"]


def test_artifact_presence_validator_passes_only_successful_execution():
    result = run_validator("artifact_presence_only", execution(), None)
    assert result["status"] == "PASSED"

    failed = run_validator("artifact_presence_only", execution(conclusion="failure"), None)
    assert failed["status"] == "FAILED"


def test_contract_validator_requires_explicit_passed_true():
    result = run_validator("contract_test_pass", execution(), {"passed": False, "score": 0.5})
    assert result["status"] == "NOT_PROMOTED"
    assert result["reasons"] == ["SCIENTIFIC_GATE_FAILED"]

    passed = run_validator("contract_test_pass", execution(), {"passed": True, "score": 0.5})
    assert passed["status"] == "PASSED"


def test_nonfinite_diagnostic_is_json_safe_and_fails_closed():
    result = run_validator("contract_test_pass", execution(), {"passed": True, "score": float("inf")})
    assert result["status"] == "NOT_PROMOTED"
    assert result["metrics"]["score"] is None
    assert "NONFINITE_DIAGNOSTIC" in result["reasons"]
    json.dumps(result, allow_nan=False)


def test_malformed_diagnostics_fail_closed():
    result = run_validator("contract_test_pass", execution(), ["not", "a", "mapping"])
    assert result["status"] == "FAILED"
    assert result["reasons"] == ["INVALID_DIAGNOSTICS"]


def test_result_envelope_validates_and_preserves_provenance():
    validation = run_validator("contract_test_pass", execution(), {"passed": True})
    envelope = build_result_envelope(
        campaign_id="NEXO-NOOP-001",
        test_id="T-ENG001",
        execution=execution(),
        validation=validation,
        campaign_commit="campaignsha",
        validator_commit="validatorsha",
    )
    assert validate_result_schema(envelope) == envelope
    assert envelope["provenance"]["campaign_commit"] == "campaignsha"
    assert envelope["provenance"]["validator_commit"] == "validatorsha"
