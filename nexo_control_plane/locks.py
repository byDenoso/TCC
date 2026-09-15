from __future__ import annotations

from .models import WorkRecord, WorkStatus

_LOCK_HOLDING = {
    WorkStatus.QUEUED,
    WorkStatus.DISPATCHED,
    WorkStatus.RUNNING,
    WorkStatus.CHECKPOINTED,
    WorkStatus.RESULT_AVAILABLE,
    WorkStatus.VERIFYING,
}


def conflicts(a: WorkRecord, b: WorkRecord) -> bool:
    if a.work_id == b.work_id:
        return False
    return bool(set(a.resource_keys).intersection(b.resource_keys))


def acquireable(work: WorkRecord, active: list[WorkRecord]) -> bool:
    return not any(item.status in _LOCK_HOLDING and conflicts(work, item) for item in active)
