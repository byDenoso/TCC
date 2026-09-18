from __future__ import annotations

from typing import Any

from .dependencies import dependency_gate
from .locks import acquireable
from .models import Backend, WorkDomain, WorkRecord, WorkStatus
from .router import route
from .scheduler import CapacityProfile, SchedulerSnapshot, eligible_dispatches

_ACTIVE = {
    WorkStatus.QUEUED,
    WorkStatus.DISPATCHED,
    WorkStatus.RUNNING,
    WorkStatus.CHECKPOINTED,
    WorkStatus.RESULT_AVAILABLE,
    WorkStatus.VERIFYING,
}


def _enum(enum_type, value: str, field_name: str):
    try:
        return enum_type(value)
    except ValueError as exc:
        raise ValueError(f"unknown {field_name}: {value}") from exc


def _parse_work(raw: dict[str, Any]) -> WorkRecord:
    domain = _enum(WorkDomain, raw["domain"], "domain")
    status = _enum(WorkStatus, raw["status"], "status")
    backend_raw = raw.get("execution_backend") or "LOCAL"
    backend = _enum(Backend, backend_raw, "execution_backend")
    return WorkRecord(
        work_id=str(raw["work_id"]),
        thread_id=str(raw.get("thread_id", "")),
        domain=domain,
        status=status,
        execution_backend=backend,
        runtime_requirement=str(raw.get("runtime_requirement", "LIGHT")),
        parent_id=str(raw.get("parent_id", "")),
        correlation_id=str(raw.get("correlation_id", "")),
        dependency_ids=tuple(raw.get("dependency_ids", ())),
        resource_keys=tuple(raw.get("resource_keys", ())),
        lane_id=str(raw.get("lane_id", "")),
        priority=str(raw.get("priority", "MEDIUM")),
        speculative=bool(raw.get("speculative", False)),
        external_run_id=str(raw.get("external_run_id", "")),
        attempt=int(raw.get("attempt", 0)),
        checkpoint_ref=str(raw.get("checkpoint_ref", "")),
        verification_status=str(raw.get("verification_status", "")),
        result_ref=str(raw.get("result_ref", "")),
        work_type=str(raw.get("work_type", "ACTION")),
    )


def build_shadow_plan(snapshot: dict[str, Any]) -> dict[str, Any]:
    raw_works = snapshot.get("works", [])
    works = [_parse_work(dict(raw)) for raw in raw_works]
    by_id = {w.work_id: w for w in works}
    if len(by_id) != len(works):
        raise ValueError("duplicate work_id in snapshot")

    active = [w for w in works if w.status in _ACTIVE]
    waits: list[dict[str, str]] = []
    conflicts: list[dict[str, str]] = []
    candidates: list[WorkRecord] = []

    for w in works:
        if w.status != WorkStatus.READY:
            continue
        gate = dependency_gate(w, by_id)
        if gate != WorkStatus.READY:
            waits.append({"work_id": w.work_id, "reason": gate.value})
            continue
        if not acquireable(w, active):
            conflicts.append({"work_id": w.work_id, "reason": "RESOURCE_LOCK"})
            continue
        candidates.append(w)

    metrics = snapshot.get("metrics", {})
    sched_snapshot = SchedulerSnapshot(
        verification_backlog=int(metrics.get("verification_backlog", 0)),
        ready_queue_count=int(metrics.get("ready_queue_count", len([w for w in works if w.status == WorkStatus.READY]))),
        engineering_backlog=int(metrics.get("engineering_backlog", len([w for w in candidates if w.domain == WorkDomain.ENGINEERING]))),
    )
    profile = CapacityProfile()
    dispatchable = eligible_dispatches(candidates, active, sched_snapshot, profile)

    pressure: list[str] = []
    if sched_snapshot.verification_backlog >= profile.unverified_soft_limit:
        pressure.append("VERIFICATION_BACKPRESSURE")
    if sched_snapshot.ready_queue_count >= profile.ready_queue_soft_limit:
        pressure.append("READY_QUEUE_BACKPRESSURE")
    reserve = profile.verification_reserve if sched_snapshot.verification_backlog > 0 else 0
    if len(active) >= profile.max_global - reserve:
        pressure.append("CAPACITY_SATURATED")

    dispatch = [
        {
            "work_id": w.work_id,
            "domain": w.domain.value,
            "backend": route(w).value,
            "priority": w.priority,
            "lane_id": w.lane_id,
        }
        for w in dispatchable
    ]

    selected_ids = {w["work_id"] for w in dispatch}
    deferred = [
        {"work_id": w.work_id, "reason": "BACKPRESSURE_OR_CAPACITY"}
        for w in candidates
        if w.work_id not in selected_ids
    ]

    return {
        "dispatch": dispatch,
        "waits": waits,
        "conflicts": conflicts,
        "deferred": deferred,
        "pressure": pressure,
        "counts": {
            "active": len(active),
            "ready": len([w for w in works if w.status == WorkStatus.READY]),
            "dispatch": len(dispatch),
            "waits": len(waits),
            "conflicts": len(conflicts),
            "deferred": len(deferred),
        },
    }
