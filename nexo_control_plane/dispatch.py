from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Any, Callable

from nexo_jobs.canary import execute as execute_canary
from nexo_control_plane.execution_bridge import ExecutionDescriptor, build_execution_contract
from nexo_control_plane.models import WorkDomain, WorkRecord, WorkStatus


_ALLOWED_ADAPTERS = {
    "canary": Path("nexo_jobs/canary.py"),
    "execution": Path("nexo_control_plane/execution_bridge.py"),
}
_SAFE_ID = re.compile(r"^[A-Za-z0-9_.:-]+$")


@dataclass(frozen=True)
class DispatchRequest:
    work_id: str
    correlation_id: str
    domain: str
    adapter: str
    source_revision: str
    attempt: int
    args: dict[str, Any]


def resolve_adapter(name: str) -> Path:
    try:
        return _ALLOWED_ADAPTERS[name]
    except KeyError as exc:
        raise ValueError(f"adapter is not allow-listed: {name}") from exc


def _require_safe_id(name: str, value: object) -> str:
    if not isinstance(value, str) or not value or not _SAFE_ID.fullmatch(value):
        raise ValueError(f"invalid {name}")
    return value


def load_dispatch_request(path: Path) -> DispatchRequest:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("dispatch request must be a JSON object")

    work_id = _require_safe_id("work_id", data.get("work_id"))
    correlation_id = _require_safe_id("correlation_id", data.get("correlation_id"))
    domain = _require_safe_id("domain", data.get("domain"))
    adapter = _require_safe_id("adapter", data.get("adapter"))
    source_revision = _require_safe_id("source_revision", data.get("source_revision"))
    resolve_adapter(adapter)

    attempt = data.get("attempt")
    if not isinstance(attempt, int) or isinstance(attempt, bool) or attempt < 1:
        raise ValueError("attempt must be a positive integer")

    args = data.get("args", {})
    if not isinstance(args, dict):
        raise ValueError("args must be a JSON object")

    return DispatchRequest(
        work_id=work_id,
        correlation_id=correlation_id,
        domain=domain,
        adapter=adapter,
        source_revision=source_revision,
        attempt=attempt,
        args=args,
    )


def _base_result(request: DispatchRequest) -> dict[str, Any]:
    return {
        "work_id": request.work_id,
        "correlation_id": request.correlation_id,
        "domain": request.domain,
        "adapter": request.adapter,
        "source_revision": request.source_revision,
        "attempt": request.attempt,
    }


def _persist_result(output_path: Path, result: dict[str, Any]) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")


def _run_canary(request: DispatchRequest) -> dict[str, Any]:
    return execute_canary(request.args)


def _run_execution(request: DispatchRequest) -> dict[str, Any]:
    args = request.args
    required = {"runtime_requirement", "task_id", "repository", "required_outputs"}
    missing = sorted(required - set(args))
    if missing:
        raise ValueError("missing execution args: " + ",".join(missing))

    try:
        domain = WorkDomain(request.domain)
    except ValueError as exc:
        raise ValueError(f"unsupported execution domain: {request.domain}") from exc

    required_outputs = args["required_outputs"]
    if not isinstance(required_outputs, list) or not all(isinstance(x, str) and x for x in required_outputs):
        raise ValueError("required_outputs must be a string list")

    parameters = args.get("parameters", {})
    if not isinstance(parameters, dict):
        raise ValueError("parameters must be an object")

    work = WorkRecord(
        work_id=request.work_id,
        thread_id=str(args.get("thread_id", "")),
        domain=domain,
        status=WorkStatus.READY,
        runtime_requirement=str(args["runtime_requirement"]),
        correlation_id=request.correlation_id,
        lane_id=str(args.get("lane_id", "")),
        priority=str(args.get("priority", "MEDIUM")),
        attempt=request.attempt - 1,
        work_type=str(args.get("test_id", request.work_id)),
    )
    descriptor = ExecutionDescriptor(
        task_id=str(args["task_id"]),
        repository=str(args["repository"]),
        commit_sha=request.source_revision,
        required_outputs=tuple(required_outputs),
        parameters=parameters,
        seed=args.get("seed"),
        timeout_minutes=int(args.get("timeout_minutes", 60)),
    )
    contract = build_execution_contract(work, descriptor)
    return {
        "provider": contract.provider,
        "contract_hash": contract.contract_hash,
        "contract": json.loads(contract.canonical_json()),
    }


_ADAPTER_RUNNERS: dict[str, Callable[[DispatchRequest], dict[str, Any]]] = {
    "canary": _run_canary,
    "execution": _run_execution,
}


def run_dispatch_request(request_path: Path, output_path: Path) -> dict[str, Any]:
    request = load_dispatch_request(request_path)
    runner = _ADAPTER_RUNNERS[request.adapter]
    try:
        adapter_result = runner(request)
    except Exception as exc:
        failed = _base_result(request)
        failed.update(
            {
                "status": "FAILED",
                "error": {
                    "type": type(exc).__name__,
                    "message": str(exc),
                },
            }
        )
        _persist_result(output_path, failed)
        raise

    result = _base_result(request)
    result.update(
        {
            "status": "COMPLETED",
            "result": adapter_result,
        }
    )
    _persist_result(output_path, result)
    return result
