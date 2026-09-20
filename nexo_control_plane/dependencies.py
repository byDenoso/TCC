from __future__ import annotations

from .models import WorkRecord, WorkStatus

_SUCCESS = {WorkStatus.VERIFIED, WorkStatus.DONE}
_HARD_FAILURE = {WorkStatus.FAILED, WorkStatus.SUPERSEDED, WorkStatus.INCONCLUSIVE}


def dependencies_satisfied(work: WorkRecord, by_id: dict[str, WorkRecord]) -> bool:
    return all(dep in by_id and by_id[dep].status in _SUCCESS for dep in work.dependency_ids)


def dependency_gate(work: WorkRecord, by_id: dict[str, WorkRecord]) -> WorkStatus:
    if not work.dependency_ids:
        return WorkStatus.READY
    for dep in work.dependency_ids:
        record = by_id.get(dep)
        if record is not None and record.status in _HARD_FAILURE:
            return WorkStatus.BLOCKED
    if dependencies_satisfied(work, by_id):
        return WorkStatus.READY
    return WorkStatus.WAIT_DEPENDENCY
