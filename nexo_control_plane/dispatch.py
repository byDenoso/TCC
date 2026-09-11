from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Any, Callable

from nexo_jobs.canary import execute as execute_canary


_ALLOWED_ADAPTERS = {
    "canary": Path("nexo_jobs/canary.py"),
}
_ADAPTER_RUNNERS: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
    "canary": execute_canary,
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


def run_dispatch_request(request_path: Path, output_path: Path) -> dict[str, Any]:
    request = load_dispatch_request(request_path)
    runner = _ADAPTER_RUNNERS[request.adapter]
    adapter_result = runner(request.args)
    result = {
        "work_id": request.work_id,
        "correlation_id": request.correlation_id,
        "domain": request.domain,
        "adapter": request.adapter,
        "source_revision": request.source_revision,
        "attempt": request.attempt,
        "status": "COMPLETED",
        "result": adapter_result,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    return result
