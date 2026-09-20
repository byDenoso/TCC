from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class WorkDomain(str, Enum):
    SCIENCE = "SCIENCE"
    ENGINEERING = "ENGINEERING"
    OLYMPUS = "OLYMPUS"
    SYSTEM = "SYSTEM"


class WorkStatus(str, Enum):
    PENDING = "PENDING"
    READY = "READY"
    QUEUED = "QUEUED"
    DISPATCHED = "DISPATCHED"
    RUNNING = "RUNNING"
    CHECKPOINTED = "CHECKPOINTED"
    RESULT_AVAILABLE = "RESULT_AVAILABLE"
    VERIFYING = "VERIFYING"
    VERIFIED = "VERIFIED"
    WAIT_DEPENDENCY = "WAIT_DEPENDENCY"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"
    INCONCLUSIVE = "INCONCLUSIVE"
    SUPERSEDED = "SUPERSEDED"
    DONE = "DONE"


class Role(str, Enum):
    ADVISOR = "ADVISOR"
    EXECUTOR = "EXECUTOR"
    LEARNER = "LEARNER"
    EMERGENT = "EMERGENT"
    DAILY = "DAILY"
    CORE = "CORE"


class Backend(str, Enum):
    LOCAL = "LOCAL"
    GITHUB_SCIENCE = "GITHUB_SCIENCE"
    GITHUB_ENGINEERING = "GITHUB_ENGINEERING"
    WAIT_DEPENDENCY = "WAIT_DEPENDENCY"


@dataclass
class WorkRecord:
    work_id: str
    thread_id: str
    domain: WorkDomain
    status: WorkStatus
    execution_backend: Backend = Backend.LOCAL
    runtime_requirement: str = "LIGHT"
    parent_id: str = ""
    correlation_id: str = ""
    dependency_ids: tuple[str, ...] = field(default_factory=tuple)
    resource_keys: tuple[str, ...] = field(default_factory=tuple)
    lane_id: str = ""
    priority: str = "MEDIUM"
    speculative: bool = False
    external_run_id: str = ""
    attempt: int = 0
    checkpoint_ref: str = ""
    verification_status: str = ""
    result_ref: str = ""
    work_type: str = "ACTION"
    affects_scientific_numerics: bool = False
