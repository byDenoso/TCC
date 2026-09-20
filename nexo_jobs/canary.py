from __future__ import annotations

from typing import Any


def execute(args: dict[str, Any]) -> dict[str, Any]:
    allowed = {"message"}
    unknown = set(args) - allowed
    if unknown:
        raise ValueError(f"unsupported canary args: {sorted(unknown)}")
    message = args.get("message", "")
    if not isinstance(message, str) or not message:
        raise ValueError("canary message must be a non-empty string")
    return {"message": message, "canary": "PASS"}
