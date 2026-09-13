from __future__ import annotations

from typing import Any


def select_correlated_run(runs: list[dict[str, Any]], correlation_id: str, ref: str) -> dict[str, Any]:
    matches = [
        run
        for run in runs
        if run.get("display_title") == correlation_id and run.get("head_branch") == ref
    ]
    if not matches:
        raise ValueError("zero matching runs for correlation ID")
    if len(matches) > 1:
        raise ValueError("multiple matching runs for correlation ID")
    return matches[0]


def summarize_results(campaign_id: str, results: list[dict[str, Any]]) -> dict[str, Any]:
    statuses = [result.get("validation", {}).get("status") for result in results]
    ready = bool(results) and all(status in {"PASSED", "NOT_PROMOTED"} for status in statuses)
    return {
        "schema_version": 1,
        "campaign_id": campaign_id,
        "test_count": len(results),
        "statuses": statuses,
        "ready_for_learning": ready,
        "results": [result.get("test_id") for result in results],
    }
