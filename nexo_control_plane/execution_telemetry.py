from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class ExecutionTrace:
    accepted_at: datetime
    canonical_ready_at: datetime | None = None
    dispatched_at: datetime | None = None
    result_at: datetime | None = None
    canonical_closed_at: datetime | None = None
    failure_stage: str | None = None


def _elapsed(start: datetime, end: datetime | None) -> float | None:
    if end is None:
        return None
    delta = (end - start).total_seconds()
    if delta < 0:
        raise ValueError("execution trace timestamps are out of order")
    return float(delta)


def derive_latency_metrics(trace: ExecutionTrace) -> dict[str, float | None]:
    return {
        "time_to_canonical_ready_s": _elapsed(trace.accepted_at, trace.canonical_ready_at),
        "time_to_dispatch_s": _elapsed(trace.accepted_at, trace.dispatched_at),
        "time_to_result_s": _elapsed(trace.accepted_at, trace.result_at),
        "time_to_canonical_close_s": _elapsed(trace.accepted_at, trace.canonical_closed_at),
    }


def classify_failure_stage(trace: ExecutionTrace) -> str | None:
    return trace.failure_stage.upper() if trace.failure_stage else None
