from __future__ import annotations

from typing import Any

TERMINAL_TEST_STATES = {"PASSED", "NOT_PROMOTED", "FAILED", "BLOCKED"}


def build_execution_plan(
    campaign: dict[str, Any],
    completed: dict[str, str] | None = None,
    attempts: dict[str, int] | None = None,
) -> dict[str, Any]:
    completed = dict(completed or {})
    attempts = dict(attempts or {})
    budget = campaign["budget"]
    max_attempts = 1 + int(budget["max_retries_per_test"])

    runnable_candidates: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []
    terminal: list[dict[str, Any]] = []

    for test in campaign["tests"]:
        test_id = test["test_id"]
        state = completed.get(test_id)
        if state in TERMINAL_TEST_STATES:
            terminal.append({"test_id": test_id, "state": state})
            continue

        if attempts.get(test_id, 0) >= max_attempts:
            blocked.append({"test_id": test_id, "reason": "RETRY_BUDGET_EXCEEDED"})
            continue

        dependency_states = [completed.get(dep) for dep in test["depends_on"]]
        if any(state is not None and state != "PASSED" for state in dependency_states):
            blocked.append({"test_id": test_id, "reason": "DEPENDENCY_NOT_PROMOTED"})
            continue
        if any(state is None for state in dependency_states):
            blocked.append({"test_id": test_id, "reason": "WAITING_DEPENDENCIES"})
            continue

        runnable_candidates.append(test)

    max_parallel = int(budget["max_parallel"])
    runnable_now = runnable_candidates[:max_parallel]
    for test in runnable_candidates[max_parallel:]:
        blocked.append({"test_id": test["test_id"], "reason": "MAX_PARALLEL"})

    return {
        "schema_version": 1,
        "campaign_id": campaign["campaign_id"],
        "runnable_now": runnable_now,
        "blocked": blocked,
        "terminal": terminal,
        "budget": dict(budget),
        "dry_run_safe": True,
    }
