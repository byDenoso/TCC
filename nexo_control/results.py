from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
RESULT_SCHEMA_PATH = ROOT / ".nexo" / "schemas" / "result.schema.json"


def json_safe(value: Any) -> Any:
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, dict):
        return {str(key): json_safe(child) for key, child in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(child) for child in value]
    return value


def validate_result_schema(result: dict[str, Any]) -> dict[str, Any]:
    safe = json_safe(result)
    schema = json.loads(RESULT_SCHEMA_PATH.read_text(encoding="utf-8"))
    errors = list(Draft202012Validator(schema).iter_errors(safe))
    if errors:
        err = errors[0]
        location = ".".join(str(item) for item in err.path) or "result"
        raise ValueError(f"result schema validation failed at {location}: {err.message}")
    return safe


def build_result_envelope(
    *,
    campaign_id: str,
    test_id: str,
    execution: dict[str, Any],
    validation: dict[str, Any],
    campaign_commit: str,
    validator_commit: str,
) -> dict[str, Any]:
    envelope = {
        "schema_version": 1,
        "campaign_id": campaign_id,
        "test_id": test_id,
        "execution": json_safe(execution),
        "validation": json_safe(validation),
        "provenance": {
            "campaign_commit": campaign_commit,
            "validator_commit": validator_commit,
        },
    }
    return validate_result_schema(envelope)
