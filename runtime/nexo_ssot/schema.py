from __future__ import annotations

from typing import Any

CANONICAL_SECTIONS = (
    "projects",
    "work",
    "tests",
    "events",
    "knowledge",
    "relations",
    "decisions",
    "olympus_summary",
)

_REQUIRED_SCALAR_FIELDS = {
    "schema_version": str,
    "ssot_revision": int,
    "state_hash": str,
    "generated_at": str,
}

_ID_KEYS = (
    "id",
    "record_id",
    "work_id",
    "test_id",
    "meta_test_id",
    "project_id",
    "relation_id",
    "cross_id",
    "knowledge_id",
    "learning_id",
    "decision_id",
    "event_id",
    "integrity_id",
    "thread_id",
)


def normalize_record(record: dict[str, Any]) -> dict[str, Any]:
    """Return a shallow canonical record with a stable `id` when one can be resolved."""
    normalized = dict(record)
    if not normalized.get("id"):
        for key in _ID_KEYS[1:]:
            value = normalized.get(key)
            if value not in (None, ""):
                normalized["id"] = str(value)
                break
    if normalized.get("id") is not None:
        normalized["id"] = str(normalized["id"])
    return normalized


def validate_snapshot(snapshot: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(snapshot, dict):
        return ["snapshot must be an object"]

    for field, expected_type in _REQUIRED_SCALAR_FIELDS.items():
        if field not in snapshot:
            errors.append(f"missing required field: {field}")
            continue
        value = snapshot[field]
        if expected_type is int:
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                errors.append(f"{field} must be a non-negative integer")
        elif not isinstance(value, expected_type) or value == "":
            errors.append(f"{field} must be a non-empty {expected_type.__name__}")

    for section in CANONICAL_SECTIONS:
        value = snapshot.get(section)
        if value is None:
            errors.append(f"missing required field: {section}")
        elif not isinstance(value, list):
            errors.append(f"{section} must be an array")

    system = snapshot.get("system")
    if system is None:
        errors.append("missing required field: system")
    elif not isinstance(system, dict):
        errors.append("system must be an object")

    state_hash = snapshot.get("state_hash")
    if isinstance(state_hash, str) and state_hash and not state_hash.startswith("sha256:"):
        errors.append("state_hash must use sha256: prefix")

    for section in CANONICAL_SECTIONS:
        rows = snapshot.get(section)
        if not isinstance(rows, list):
            continue
        seen: set[str] = set()
        for index, row in enumerate(rows):
            if not isinstance(row, dict):
                errors.append(f"{section}[{index}] must be an object")
                continue
            normalized = normalize_record(row)
            row_id = normalized.get("id")
            if not row_id:
                errors.append(f"{section}[{index}] must have a stable id")
                continue
            if row_id in seen:
                errors.append(f"duplicate id in {section}: {row_id}")
            seen.add(row_id)

    return errors
