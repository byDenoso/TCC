from __future__ import annotations

from dataclasses import dataclass

from .models import WorkRecord, WorkStatus


@dataclass(frozen=True)
class ExternalRunState:
    backend_run_id: str
    correlation_id: str
    status: str
    exit_code: int | None
    artifact_ref: str
    checkpoint_ref: str
    result_hash: str
    conflicting_run_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class ReconcileDecision:
    next_status: WorkStatus
    action: str
    reason: str


def reconcile(work: WorkRecord, external: ExternalRunState | None) -> ReconcileDecision:
    if external is None:
        if work.status in {WorkStatus.DISPATCHED, WorkStatus.RUNNING}:
            return ReconcileDecision(WorkStatus.BLOCKED, "DISPATCH_MISSING", "external run cannot be resolved")
        return ReconcileDecision(work.status, "NO_OP", "no external state required")

    if len(set(external.conflicting_run_ids)) > 1:
        return ReconcileDecision(WorkStatus.BLOCKED, "DUPLICATE_RUN_CONFLICT", "multiple external runs share one logical execution")

    if external.correlation_id != (work.correlation_id or work.work_id):
        return ReconcileDecision(WorkStatus.BLOCKED, "IDENTITY_MISMATCH", "correlation_id mismatch")
    if work.external_run_id and external.backend_run_id != work.external_run_id:
        return ReconcileDecision(WorkStatus.BLOCKED, "IDENTITY_MISMATCH", "backend_run_id mismatch")

    ext_status = external.status.upper()

    if ext_status in {"QUEUED", "PENDING"}:
        desired = WorkStatus.DISPATCHED
        if work.status == desired:
            return ReconcileDecision(work.status, "NO_OP", "already aligned")
        return ReconcileDecision(desired, "TRACK_RUN", "external run queued")

    if ext_status in {"IN_PROGRESS", "RUNNING"}:
        desired = WorkStatus.RUNNING
        if work.status == desired:
            return ReconcileDecision(work.status, "NO_OP", "already aligned")
        return ReconcileDecision(desired, "TRACK_RUN", "external run active")

    if ext_status in {"COMPLETED", "SUCCESS"} and external.exit_code == 0:
        desired = WorkStatus.RESULT_AVAILABLE
        if work.status in {WorkStatus.RESULT_AVAILABLE, WorkStatus.VERIFYING, WorkStatus.VERIFIED, WorkStatus.DONE}:
            return ReconcileDecision(work.status, "NO_OP", "result already ingested or beyond")
        return ReconcileDecision(desired, "INGEST_RESULT", "external run completed successfully")

    if ext_status in {"FAILED", "CANCELLED", "TIMED_OUT", "TIMEOUT"} or (
        ext_status in {"COMPLETED", "SUCCESS"} and external.exit_code not in {None, 0}
    ):
        if external.checkpoint_ref:
            if work.status == WorkStatus.CHECKPOINTED:
                return ReconcileDecision(work.status, "NO_OP", "checkpoint already registered")
            return ReconcileDecision(WorkStatus.CHECKPOINTED, "RESUME_ELIGIBLE", "failed run has resumable checkpoint")
        return ReconcileDecision(WorkStatus.FAILED, "RUN_FAILED", "external run failed without checkpoint")

    return ReconcileDecision(WorkStatus.BLOCKED, "UNKNOWN_EXTERNAL_STATE", f"unrecognized external status {external.status}")
