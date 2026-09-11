from __future__ import annotations

from .models import Backend, Role, WorkDomain, WorkRecord, WorkStatus


_ALLOWED_CREATION: dict[Role, set[WorkDomain]] = {
    Role.ADVISOR: {WorkDomain.SCIENCE},
    Role.EMERGENT: {WorkDomain.SCIENCE},
    Role.CORE: {WorkDomain.ENGINEERING, WorkDomain.SYSTEM},
    Role.EXECUTOR: set(),
    Role.LEARNER: set(),
    Role.DAILY: set(),
}

_ENGINEERING_SIGNALS = {
    "CAPABILITY_GAP",
    "RUNTIME_DEFECT",
    "CI_FAILURE",
    "CHECKPOINT_FAILURE",
    "ARTIFACT_CORRUPTION",
    "PERFORMANCE_REGRESSION",
    "CONNECTOR_FAILURE",
}


class InvalidEngineeringSignal(ValueError):
    pass


def may_create_work(role: Role, domain: WorkDomain) -> bool:
    return domain in _ALLOWED_CREATION.get(role, set())


def engineering_from_signal(signal_type: str, parent: WorkRecord) -> WorkRecord:
    if signal_type not in _ENGINEERING_SIGNALS:
        raise InvalidEngineeringSignal(f"unsupported engineering signal: {signal_type}")
    safe_signal = signal_type.replace("_", "-")
    return WorkRecord(
        work_id=f"ENG::{safe_signal}::{parent.work_id}",
        thread_id="THR::ENGINEERING::ROOT",
        domain=WorkDomain.ENGINEERING,
        status=WorkStatus.READY,
        execution_backend=Backend.GITHUB_ENGINEERING,
        runtime_requirement="CODE",
        parent_id=parent.work_id,
        correlation_id=parent.correlation_id or parent.work_id,
        resource_keys=parent.resource_keys,
        priority="CRITICAL" if parent.status == WorkStatus.BLOCKED else "HIGH",
        work_type="ENGINEERING_REPAIR",
    )


def knowledge_namespace(work: WorkRecord) -> str:
    if work.domain == WorkDomain.SCIENCE:
        return "OBJECT"
    if work.domain in {WorkDomain.ENGINEERING, WorkDomain.SYSTEM}:
        return "PROCEDURAL"
    return "OBJECT"


def science_review_required(work: WorkRecord) -> bool:
    return work.domain == WorkDomain.ENGINEERING and work.affects_scientific_numerics
