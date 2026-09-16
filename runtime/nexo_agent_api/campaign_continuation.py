from __future__ import annotations

import json
from pathlib import Path
from typing import Any


_SUCCESS_STATES = {"VERIFIED", "DONE", "COMPLETE", "COMPLETED", "TERMINALIZED", "PASS"}
_ACTIVE_RUN_STATES = {"QUEUED", "DISPATCHED", "RUNNING", "CHECKPOINTED"}
_RECOVERABLE_RUN_STATES = {"FAILED", "STALE", "INTERRUPTED", "TIMED_OUT"}
_CAMPAIGN_TERMINAL_STATES = {"DONE", "COMPLETE", "COMPLETED", "TERMINALIZED", "CLOSED"}


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None
    return payload if isinstance(payload, dict) else None


def _status(entity: dict[str, Any] | None) -> str:
    if not entity:
        return ""
    return str(entity.get("operational_status") or entity.get("status") or "").upper()


class CampaignFrontierResolver:
    """Derive campaign continuation state from canonical entities only.

    This resolver is intentionally read-only. It reconstructs the frontier on
    demand instead of introducing a second persisted campaign cursor.
    """

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)

    def _entity(self, kind: str, entity_id: str) -> dict[str, Any] | None:
        return _read_json(self.root / "entities" / kind / f"{entity_id}.json")

    def _tests(self, campaign_id: str) -> dict[str, dict[str, Any]]:
        folder = self.root / "entities" / "test"
        items: dict[str, dict[str, Any]] = {}
        if not folder.exists():
            return items
        for path in folder.glob("*.json"):
            payload = _read_json(path)
            if not payload or str(payload.get("campaign_id")) != campaign_id:
                continue
            test_id = str(payload.get("id") or path.stem)
            items[test_id] = payload
        return items

    def _runs(self, campaign_id: str) -> dict[str, list[dict[str, Any]]]:
        folder = self.root / "entities" / "run"
        items: dict[str, list[dict[str, Any]]] = {}
        if not folder.exists():
            return items
        for path in folder.glob("*.json"):
            payload = _read_json(path)
            if not payload or str(payload.get("campaign_id")) != campaign_id:
                continue
            test_id = str(payload.get("test_id") or "")
            if test_id:
                items.setdefault(test_id, []).append(payload)
        return items

    @staticmethod
    def _ordered_ids(campaign: dict[str, Any], tests: dict[str, dict[str, Any]]) -> list[str]:
        declared = [str(value) for value in campaign.get("execution_order", []) if str(value)]
        ordered = [test_id for test_id in declared if test_id in tests]
        ordered.extend(sorted(test_id for test_id in tests if test_id not in ordered))
        return ordered

    @staticmethod
    def _select_run(test: dict[str, Any], runs: list[dict[str, Any]]) -> dict[str, Any] | None:
        current = str(test.get("current_run_id") or "")
        if current:
            for run in runs:
                if str(run.get("id")) == current:
                    return run
        if not runs:
            return None
        return sorted(runs, key=lambda item: str(item.get("created_at") or item.get("id") or ""))[-1]

    def resolve(self, campaign_id: str) -> dict[str, Any]:
        campaign = self._entity("campaign", campaign_id)
        if campaign is None:
            raise ValueError(f"campaign not found: {campaign_id}")

        tests = self._tests(campaign_id)
        runs_by_test = self._runs(campaign_id)
        ordered_ids = self._ordered_ids(campaign, tests)

        completed: list[str] = []
        active: list[str] = []
        recoverable: list[str] = []
        ready: list[str] = []
        blocked: list[str] = []

        for test_id in ordered_ids:
            test = tests[test_id]
            test_state = _status(test)
            if test_state in _SUCCESS_STATES:
                completed.append(test_id)
                continue

            run = self._select_run(test, runs_by_test.get(test_id, []))
            run_state = _status(run)
            if run_state in _ACTIVE_RUN_STATES:
                active.append(test_id)
                continue
            if run_state in _RECOVERABLE_RUN_STATES and bool((run or {}).get("recoverable")):
                recoverable.append(test_id)
                continue

            dependencies = [str(value) for value in test.get("depends_on", []) if str(value)]
            dependencies_closed = all(dep in completed for dep in dependencies)
            manual = str(test.get("execution_policy") or "AUTO").upper() == "MANUAL"
            explicit_blocker = bool(test.get("blocker"))
            if dependencies_closed and not manual and not explicit_blocker and test_state in {"READY", "QUEUED", "CHECKPOINTED", ""}:
                ready.append(test_id)
            else:
                blocked.append(test_id)

        campaign_state = _status(campaign)
        terminal_ids = [str(value) for value in campaign.get("terminal_test_ids", []) if str(value)]
        terminal = campaign_state in _CAMPAIGN_TERMINAL_STATES
        if not terminal and terminal_ids:
            terminal = all(test_id in completed for test_id in terminal_ids)
        if not terminal and tests and not terminal_ids:
            terminal = len(completed) == len(tests)

        if terminal:
            next_test_ids: list[str] = []
            frontier_status = "TERMINAL"
        else:
            next_test_ids = recoverable or active or ready
            frontier_status = "ACTIVE"

        return {
            "campaign_id": campaign_id,
            "status": frontier_status,
            "active": active,
            "recoverable": recoverable,
            "ready": ready,
            "blocked": blocked,
            "completed": completed,
            "terminal": terminal,
            "next_test_ids": list(next_test_ids),
        }
