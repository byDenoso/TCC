from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any, Callable

from .scientific_intake import is_execution_utterance


TOOL_NAME = "nexo_submit_scientific_tests_v1"


def tool_descriptor() -> dict[str, Any]:
    return {
        "name": TOOL_NAME,
        "description": "Submit explicit user-directed scientific tests through the canonical Tower-first NEXO intake path.",
        "inputSchema": {
            "type": "object",
            "additionalProperties": False,
            "required": ["utterance"],
            "properties": {
                "utterance": {"type": "string", "minLength": 1},
                "source": {"type": "string", "default": "chat"},
                "defaults": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "datasets": {"type": "array", "items": {"type": "string"}},
                        "rival": {"type": "string"},
                        "null": {"type": "string"},
                        "method": {"type": "string"},
                        "decision_rule": {"type": "string"},
                        "model_constraints": {"type": "array", "items": {"type": "string"}},
                        "test_group_id": {"type": "string"},
                        "claim_boundary": {"type": "string"},
                        "execution_capability": {"type": "string"},
                    },
                },
            },
        },
    }


def _receipt_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    if is_dataclass(value):
        return asdict(value)
    if hasattr(value, "to_dict"):
        result = value.to_dict()
        if isinstance(result, dict):
            return result
    raise TypeError("scientific intake receipt must be a mapping or dataclass")


def submit_scientific_tests_tool(
    payload: dict[str, Any],
    service_factory: Callable[[], Any],
) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("payload must be an object")
    utterance = payload.get("utterance")
    if not isinstance(utterance, str) or not utterance.strip():
        raise ValueError("utterance is required")
    if not is_execution_utterance(utterance):
        raise ValueError("utterance is not an explicit scientific execution command")
    source = payload.get("source", "chat")
    if not isinstance(source, str) or not source.strip():
        raise ValueError("source must be a non-empty string")
    defaults = payload.get("defaults", {})
    if defaults is None:
        defaults = {}
    if not isinstance(defaults, dict):
        raise ValueError("defaults must be an object")

    application = service_factory()
    receipts = application.submit_utterance(
        utterance,
        source=source,
        defaults=dict(defaults),
    )
    if not isinstance(receipts, list):
        raise TypeError("scientific intake application must return a list")
    tests = [_receipt_dict(receipt) for receipt in receipts]
    return {"accepted": True, "tests": tests}
