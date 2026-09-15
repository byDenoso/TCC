from __future__ import annotations

from .models import Backend, WorkDomain, WorkRecord, WorkStatus

_EXTERNAL_SCIENCE_CLASSES = {"HEAVY", "LONG", "MCMC", "NESTED", "GRID", "PARALLEL"}
_EXTERNAL_ENGINEERING_CLASSES = {"CODE", "CI", "RUNTIME", "HEAVY", "LONG"}


def route(work: WorkRecord) -> Backend:
    if work.status == WorkStatus.WAIT_DEPENDENCY:
        return Backend.WAIT_DEPENDENCY
    runtime = work.runtime_requirement.upper()
    if work.domain == WorkDomain.OLYMPUS:
        return Backend.LOCAL
    if work.domain == WorkDomain.SCIENCE and runtime in _EXTERNAL_SCIENCE_CLASSES:
        return Backend.GITHUB_SCIENCE
    if work.domain == WorkDomain.ENGINEERING and runtime in _EXTERNAL_ENGINEERING_CLASSES:
        return Backend.GITHUB_ENGINEERING
    return Backend.LOCAL
