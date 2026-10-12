"""Synthetic sandbox benchmark for queue prioritization only; executes no work."""
from __future__ import annotations

import json
import statistics
import time

from .views import _prioritize


def _queue(size: int) -> list[dict]:
    result = []
    for index in range(size):
        incoming = index % 4 == 0
        result.append({
            "id": f"CARD-{index:06d}",
            "queue_kind": "INTER_AGENT_REQUEST" if incoming else "WORK",
            "owner_role": "EXECUTOR",
            "status": "PENDING" if incoming else "READY",
            "priority": "HIGH" if index % 17 == 0 else "NORMAL",
            "opened_at": f"2026-10-11T00:{index % 60:02d}:00Z",
        })
    return result


def _measure(size: int, repeats: int = 40) -> dict:
    queue = _queue(size)
    for _ in range(5):
        _prioritize(queue, "EXECUTOR")
    samples_ms = []
    result = None
    for _ in range(repeats):
        started = time.perf_counter_ns()
        result = _prioritize(queue, "EXECUTOR")
        samples_ms.append((time.perf_counter_ns() - started) / 1_000_000)
    median_ms = statistics.median(samples_ms)
    return {
        "input_cards": size,
        "selected_cards": len(result or []),
        "work_lane_visible": any(item["queue_kind"] == "WORK" for item in result or []),
        "request_lane_visible": any(item["queue_kind"] == "INTER_AGENT_REQUEST" for item in result or []),
        "median_projection_ms": round(median_ms, 4),
        "input_cards_per_second": round(size / (median_ms / 1000), 1) if median_ms else None,
        "repeats": repeats,
    }


def main() -> None:
    baseline_size = 300
    expanded_size = baseline_size * 4
    baseline = _measure(baseline_size)
    expanded = _measure(expanded_size)
    print(json.dumps({
        "scope": "SYNTHETIC_SANDBOX_QUEUE_PROJECTION_ONLY",
        "scientific_execution": False,
        "production_throughput_claim": False,
        "scale_factor": 4,
        "baseline": baseline,
        "fourfold_input": expanded,
        "projection_time_ratio": round(expanded["median_projection_ms"] /
                                        baseline["median_projection_ms"], 3)
        if baseline["median_projection_ms"] else None,
    }, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
