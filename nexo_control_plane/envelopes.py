from __future__ import annotations

from dataclasses import dataclass

from .models import Backend, WorkRecord


@dataclass(frozen=True)
class ExecutionEnvelope:
    work_id: str
    correlation_id: str
    domain: str
    thread_id: str
    lane_id: str
    backend: str
    task_type: str
    source_revision: str
    input_hash: str
    seed: int | None
    checkpoint_policy: str
    attempt: int
    resource_keys: tuple[str, ...]

    def __post_init__(self) -> None:
        required = {
            "work_id": self.work_id,
            "correlation_id": self.correlation_id,
            "domain": self.domain,
            "backend": self.backend,
            "task_type": self.task_type,
            "source_revision": self.source_revision,
            "input_hash": self.input_hash,
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise ValueError(f"missing execution-envelope fields: {','.join(missing)}")


@dataclass(frozen=True)
class ResultEnvelope:
    work_id: str
    correlation_id: str
    backend_run_id: str
    status: str
    exit_code: int
    artifact_ref: str
    checkpoint_ref: str
    runtime_seconds: float
    result_hash: str
    source_revision: str

    def __post_init__(self) -> None:
        required = {
            "work_id": self.work_id,
            "correlation_id": self.correlation_id,
            "backend_run_id": self.backend_run_id,
            "status": self.status,
            "source_revision": self.source_revision,
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise ValueError(f"missing result-envelope fields: {','.join(missing)}")
        if self.runtime_seconds < 0:
            raise ValueError("runtime_seconds must be non-negative")


def build_execution_envelope(
    work: WorkRecord,
    *,
    source_revision: str,
    input_hash: str,
    seed: int | None = None,
) -> ExecutionEnvelope:
    if work.execution_backend not in {Backend.GITHUB_SCIENCE, Backend.GITHUB_ENGINEERING}:
        raise ValueError("execution envelope is only for external GitHub backends")
    long_class = work.runtime_requirement.upper() in {"HEAVY", "LONG", "MCMC", "NESTED", "GRID", "PARALLEL"}
    return ExecutionEnvelope(
        work_id=work.work_id,
        correlation_id=work.correlation_id or work.work_id,
        domain=work.domain.value,
        thread_id=work.thread_id,
        lane_id=work.lane_id,
        backend=work.execution_backend.value,
        task_type=work.work_type,
        source_revision=source_revision,
        input_hash=input_hash,
        seed=seed,
        checkpoint_policy="MANDATORY" if long_class else "OPTIONAL",
        attempt=work.attempt,
        resource_keys=tuple(work.resource_keys),
    )
