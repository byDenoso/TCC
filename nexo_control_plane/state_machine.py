from __future__ import annotations

from .models import Backend, WorkRecord, WorkStatus


class InvalidTransition(ValueError):
    pass


_ALLOWED: dict[WorkStatus, set[WorkStatus]] = {
    WorkStatus.PENDING: {WorkStatus.READY, WorkStatus.WAIT_DEPENDENCY, WorkStatus.BLOCKED, WorkStatus.SUPERSEDED},
    WorkStatus.READY: {WorkStatus.QUEUED, WorkStatus.DISPATCHED, WorkStatus.RUNNING, WorkStatus.WAIT_DEPENDENCY, WorkStatus.BLOCKED, WorkStatus.SUPERSEDED},
    WorkStatus.QUEUED: {WorkStatus.DISPATCHED, WorkStatus.BLOCKED, WorkStatus.SUPERSEDED},
    WorkStatus.DISPATCHED: {WorkStatus.RUNNING, WorkStatus.BLOCKED, WorkStatus.FAILED, WorkStatus.SUPERSEDED},
    WorkStatus.RUNNING: {WorkStatus.CHECKPOINTED, WorkStatus.RESULT_AVAILABLE, WorkStatus.BLOCKED, WorkStatus.FAILED, WorkStatus.INCONCLUSIVE},
    WorkStatus.CHECKPOINTED: {WorkStatus.DISPATCHED, WorkStatus.RUNNING, WorkStatus.RESULT_AVAILABLE, WorkStatus.FAILED, WorkStatus.BLOCKED},
    WorkStatus.RESULT_AVAILABLE: {WorkStatus.VERIFYING, WorkStatus.BLOCKED, WorkStatus.FAILED, WorkStatus.INCONCLUSIVE},
    WorkStatus.VERIFYING: {WorkStatus.VERIFIED, WorkStatus.BLOCKED, WorkStatus.FAILED, WorkStatus.INCONCLUSIVE},
    WorkStatus.VERIFIED: {WorkStatus.DONE, WorkStatus.INCONCLUSIVE, WorkStatus.SUPERSEDED},
    WorkStatus.WAIT_DEPENDENCY: {WorkStatus.READY, WorkStatus.BLOCKED, WorkStatus.SUPERSEDED},
    WorkStatus.BLOCKED: {WorkStatus.READY, WorkStatus.WAIT_DEPENDENCY, WorkStatus.SUPERSEDED},
    WorkStatus.FAILED: {WorkStatus.READY, WorkStatus.DISPATCHED, WorkStatus.SUPERSEDED},
    WorkStatus.INCONCLUSIVE: {WorkStatus.READY, WorkStatus.SUPERSEDED, WorkStatus.DONE},
    WorkStatus.SUPERSEDED: set(),
    WorkStatus.DONE: set(),
}


def can_transition(old: WorkStatus, new: WorkStatus, *, external_material: bool) -> bool:
    if old == new:
        return True
    if external_material and new == WorkStatus.DONE and old != WorkStatus.VERIFIED:
        return False
    return new in _ALLOWED.get(old, set())


def transition(work: WorkRecord, new_status: WorkStatus) -> WorkRecord:
    external = work.execution_backend in {Backend.GITHUB_SCIENCE, Backend.GITHUB_ENGINEERING}
    if not can_transition(work.status, new_status, external_material=external):
        raise InvalidTransition(f"invalid transition {work.status.value}->{new_status.value}")
    work.status = new_status
    return work
