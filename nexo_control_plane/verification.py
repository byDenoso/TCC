from __future__ import annotations

from .envelopes import ResultEnvelope
from .models import Backend, WorkRecord, WorkStatus


def result_is_verifiable(result: ResultEnvelope) -> bool:
    return (
        result.status.upper() in {"COMPLETED", "SUCCESS"}
        and result.exit_code == 0
        and bool(result.artifact_ref)
        and bool(result.result_hash)
        and bool(result.source_revision)
        and bool(result.correlation_id)
        and bool(result.backend_run_id)
    )


def _external(work: WorkRecord) -> bool:
    return work.execution_backend in {Backend.GITHUB_SCIENCE, Backend.GITHUB_ENGINEERING}


def can_learn(work: WorkRecord) -> bool:
    if _external(work):
        return work.status in {WorkStatus.VERIFIED, WorkStatus.DONE} and work.verification_status == "PASS"
    return work.status in {WorkStatus.VERIFIED, WorkStatus.DONE}


def can_close(work: WorkRecord) -> bool:
    if _external(work):
        return work.status in {WorkStatus.VERIFIED, WorkStatus.DONE} and work.verification_status == "PASS"
    return work.status in {WorkStatus.VERIFIED, WorkStatus.DONE}
