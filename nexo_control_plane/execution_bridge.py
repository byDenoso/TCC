from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from runtime.nexo_execution.core import (
    ExecutionContract,
    GitHubActionsProvider,
    LocalProvider,
    ResultVerifier,
)

from .models import Backend, WorkRecord
from .router import route


@dataclass(frozen=True)
class ExecutionDescriptor:
    task_id: str
    repository: str
    commit_sha: str
    required_outputs: tuple[str, ...]
    parameters: dict[str, Any]
    seed: int | None = None
    timeout_minutes: int = 60


def provider_for(work: WorkRecord) -> str:
    backend = route(work)
    if backend in {Backend.GITHUB_SCIENCE, Backend.GITHUB_ENGINEERING}:
        return "github_actions"
    if backend == Backend.LOCAL:
        return "local"
    raise ValueError(f"work is not dispatchable: {backend.value}")


def build_execution_contract(work: WorkRecord, descriptor: ExecutionDescriptor) -> ExecutionContract:
    attempt = max(1, work.attempt + 1)
    execution_id = f"EXEC-{work.work_id}-A{attempt}"
    return ExecutionContract(
        schema="nexo.execution.v1",
        execution_id=execution_id,
        work_id=work.work_id,
        test_id=work.work_type or work.work_id,
        provider=provider_for(work),
        repository=descriptor.repository,
        commit_sha=descriptor.commit_sha,
        task_id=descriptor.task_id,
        parameters=dict(descriptor.parameters),
        seed=descriptor.seed,
        timeout_minutes=descriptor.timeout_minutes,
        required_outputs=list(descriptor.required_outputs),
    )


def execute_contract_here(contract: ExecutionContract) -> dict[str, Any]:
    result = LocalProvider().submit(contract)
    verification = ResultVerifier().verify(contract, result)
    return {"result": result.to_dict(), "verification": verification}


def dispatch_contract(
    contract: ExecutionContract,
    *,
    github_token: str | None = None,
    github_ref: str = "main",
    contract_name: str | None = None,
):
    if contract.provider == "local":
        return execute_contract_here(contract)
    if contract.provider == "github_actions":
        return GitHubActionsProvider(token=github_token).submit(
            contract,
            ref=github_ref,
            contract_name=contract_name,
        )
    raise ValueError(f"unsupported provider: {contract.provider}")
