from __future__ import annotations

from typing import Any, Mapping

from runtime.nexo_core.models import CanonicalEntity, CanonicalEvent


def _clean(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _split(value: Any) -> list[str]:
    if value is None or value == "":
        return []
    if isinstance(value, (list, tuple, set)):
        return [_clean(item) for item in value if _clean(item)]
    text = _clean(value)
    if not text:
        return []
    parts = text.replace("\n", ";").split(";")
    return [part.strip() for part in parts if part.strip()]


def _work_ref(value: str) -> str:
    value = value.strip()
    if not value:
        return value
    return value if "::" in value else f"WORK::{value}"


def _int_or_default(value: Any, default: int) -> int:
    try:
        parsed = int(str(value).strip())
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


def work_row_to_entity(
    row: Mapping[str, Any],
    *,
    default_writer_role: str,
) -> CanonicalEntity:
    work_id = _clean(row.get("work_id"))
    if not work_id:
        raise ValueError("work_id is required")
    state = _clean(row.get("status")) or "UNKNOWN"
    explicit_writer = _clean(row.get("writer_role"))
    writer_role = explicit_writer or default_writer_role
    if not writer_role:
        raise ValueError("writer_role is required")

    dependencies = [_work_ref(value) for value in _split(row.get("dependency_ids"))]
    data = {
        "label": _clean(row.get("question")) or work_id,
        "domain": _clean(row.get("domain")) or None,
        "kind": _clean(row.get("kind")) or None,
        "parent_id": _clean(row.get("parent_id")) or None,
        "dependency_ids": dependencies,
        "resource_keys": _split(row.get("resource_keys")),
        "input_refs": _split(row.get("input_refs")),
        "result_ref": _clean(row.get("result_ref")) or None,
        "verification_status": _clean(row.get("verification_status")) or None,
        "execution_backend": _clean(row.get("execution_backend")) or None,
        "external_run_id": _clean(row.get("external_run_id")) or None,
        "checkpoint_ref": _clean(row.get("checkpoint_ref")) or None,
    }

    return CanonicalEntity(
        entity_ref=f"WORK::{work_id}",
        state=state,
        entity_version=_int_or_default(row.get("entity_version"), 1),
        writer_role=writer_role,
        last_event_id=_clean(row.get("last_event_id")) or None,
        last_correlation_id=_clean(row.get("last_correlation_id")) or None,
        data=data,
    )


def event_row_to_event(row: Mapping[str, Any]) -> CanonicalEvent:
    event_id = _clean(row.get("event_id"))
    if not event_id:
        raise ValueError("event_id is required")

    entity_ref = _clean(row.get("entity_ref"))
    if not entity_ref:
        work_id = _clean(row.get("work_id"))
        thread_id = _clean(row.get("thread_id"))
        if work_id:
            entity_ref = f"WORK::{work_id}"
        elif thread_id:
            entity_ref = thread_id if "::" in thread_id else f"THREAD::{thread_id}"
        else:
            raise ValueError("entity_ref, work_id, or thread_id is required")

    dedupe_key = _clean(row.get("dedupe_key"))
    if not dedupe_key:
        raise ValueError("dedupe_key is required for v0.5 events")

    return CanonicalEvent(
        event_id=event_id,
        entity_ref=entity_ref,
        event_type=_clean(row.get("event_type")) or "UNKNOWN",
        correlation_id=_clean(row.get("correlation_id")) or event_id,
        source_role=_clean(row.get("source_role")) or "UNKNOWN",
        state_from=_clean(row.get("state_from")) or "UNKNOWN",
        state_to=_clean(row.get("state_to")) or "UNKNOWN",
        resource_key=_clean(row.get("resource_key")) or entity_ref,
        dedupe_key=dedupe_key,
        payload_ref=_clean(row.get("payload_ref")) or None,
        run_id=_clean(row.get("run_id")) or None,
        timestamp=_clean(row.get("timestamp")) or None,
    )
