from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .service import AgentService

ROLES = ("DAILY", "ADVISOR", "EXECUTOR", "LEARNER", "EMERGENT")
ROLE_QUEUE_LIMIT = 5
PRIORITY_RANK = {"CRITICAL": 0, "HIGH": 1, "MEDIUM_HIGH": 2, "MEDIUM": 3, "LOW": 4}
STATUS_RANK = {"VERIFIED": 0, "READY": 1, "RUNNING": 2, "CHECKPOINTED": 3, "WAIT_DEPENDENCY": 4}


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True), encoding="utf-8")


def _active_ids(root: Path) -> set[str] | None:
    path = root / "indexes" / "active-work.json"
    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {str(item.get("id") or item.get("work_id")) for item in payload.get("work", []) if isinstance(item, dict) and (item.get("id") or item.get("work_id"))}


def _prioritize(queue: list[dict[str, Any]], role: str) -> list[dict[str, Any]]:
    return sorted(
        queue,
        key=lambda item: (
            0 if item.get("owner_role") == role else 1,
            PRIORITY_RANK.get(str(item.get("priority", "MEDIUM")), 9),
            STATUS_RANK.get(str(item.get("status", "")), 9),
            str(item.get("id", "")),
        ),
    )[:ROLE_QUEUE_LIMIT]


def materialize_role_views(root: str | Path) -> dict[str, Any]:
    root = Path(root)
    service = AgentService(root)
    active_ids = _active_ids(root)
    counts: dict[str, int] = {}
    for role in ROLES:
        view = service.bootstrap(role)
        queue = view["queue"]
        if active_ids is not None:
            queue = [item for item in queue if str(item.get("id")) in active_ids]
        queue = _prioritize(queue, role)
        view["queue"] = queue
        view["queue_count"] = len(queue)
        view["queue_limit"] = ROLE_QUEUE_LIMIT
        view["view_model"] = "SINGLE_ROLE_VIEW"
        _write_json(root / "bootstrap" / f"{role.lower()}.json", view)
        _write_json(root / "queues" / f"{role.lower()}.json", {
            "role": role,
            "items": [],
            "count": 0,
            "compatibility": "SUPERSEDED_BY_BOOTSTRAP_ROLE_VIEW",
            "role_view_ref": f"bootstrap/{role.lower()}.json",
        })
        counts[role] = view["queue_count"]
    return {"roles": len(ROLES), "queue_counts": counts, "queue_limit": ROLE_QUEUE_LIMIT, "view_model": "SINGLE_ROLE_VIEW"}
