from __future__ import annotations

import math
from typing import Any

from nexo_control.contracts import VALIDATOR_REGISTRY
from nexo_control.results import json_safe


def _contains_nonfinite(value: Any) -> bool:
    if isinstance(value, float):
        return not math.isfinite(value)
    if isinstance(value, dict):
        return any(_contains_nonfinite(child) for child in value.values())
    if isinstance(value, (list, tuple)):
        return any(_contains_nonfinite(child) for child in value)
    return False


def _outcome(name: str, status: str, metrics: dict[str, Any] | None, reasons: list[str]) -> dict[str, Any]:
    return {
        "status": status,
        "validator": name,
        "metrics": json_safe(metrics or {}),
        "reasons": list(reasons),
    }


def run_validator(name: str, execution: dict[str, Any], diagnostics: Any) -> dict[str, Any]:
    if name not in VALIDATOR_REGISTRY:
        raise ValueError(f"unknown validator: {name}")

    if execution.get("status") != "COMPLETED" or execution.get("conclusion") != "success":
        return _outcome(name, "FAILED", {}, ["EXECUTION_FAILED"])

    artifacts = execution.get("artifact_names")
    if not isinstance(artifacts, list) or not artifacts:
        return _outcome(name, "NOT_PROMOTED", {}, ["REQUIRED_ARTIFACT_MISSING"])

    if name == "artifact_presence_only":
        return _outcome(name, "PASSED", {}, [])

    if not isinstance(diagnostics, dict):
        return _outcome(name, "FAILED", {}, ["INVALID_DIAGNOSTICS"])

    metrics = {key: value for key, value in diagnostics.items() if key != "passed"}
    if _contains_nonfinite(diagnostics):
        return _outcome(name, "NOT_PROMOTED", metrics, ["NONFINITE_DIAGNOSTIC"])
    if diagnostics.get("passed") is True:
        return _outcome(name, "PASSED", metrics, [])
    return _outcome(name, "NOT_PROMOTED", metrics, ["SCIENTIFIC_GATE_FAILED"])
