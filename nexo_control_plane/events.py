from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256

from .models import Role, WorkRecord, WorkStatus


@dataclass(frozen=True)
class EventRecord:
    event_id: str
    thread_id: str
    work_id: str
    event_type: str
    correlation_id: str
    source_role: str
    target_role: str
    state_from: str
    state_to: str
    payload_ref: str
    resource_key: str
    severity: str
    dedupe_key: str
    acknowledged_at: str = ""


def make_transition_event(
    work: WorkRecord,
    source_role: Role,
    target_role: Role,
    old_status: WorkStatus,
    new_status: WorkStatus,
    payload_ref: str = "",
    *,
    severity: str = "INFO",
) -> EventRecord:
    correlation_id = work.correlation_id or work.work_id
    resource_key = sorted(work.resource_keys)[0] if work.resource_keys else ""
    identity = "|".join(
        [
            work.work_id,
            correlation_id,
            source_role.value,
            target_role.value,
            old_status.value,
            new_status.value,
            payload_ref,
            resource_key,
        ]
    )
    digest = sha256(identity.encode("utf-8")).hexdigest()
    dedupe_key = f"sha256:{digest}"
    return EventRecord(
        event_id=f"EVT::{digest[:20]}",
        thread_id=work.thread_id,
        work_id=work.work_id,
        event_type="STATE_TRANSITION",
        correlation_id=correlation_id,
        source_role=source_role.value,
        target_role=target_role.value,
        state_from=old_status.value,
        state_to=new_status.value,
        payload_ref=payload_ref,
        resource_key=resource_key,
        severity=severity,
        dedupe_key=dedupe_key,
    )
