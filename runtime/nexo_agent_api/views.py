from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .service import AgentService

ROLES = ("DAILY", "ADVISOR", "EXECUTOR", "LEARNER", "EMERGENT")
LEGACY_VIEW_DIRS = ("bootstrap", "queues")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True), encoding="utf-8")


def _active_ids(root: Path) -> set[str] | None:
    path = root / "indexes" / "active-work.json"
    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {
        str(item.get("id") or item.get("work_id"))
        for item in payload.get("work", [])
        if isinstance(item, dict) and (item.get("id") or item.get("work_id"))
    }


def _prune_legacy_views(root: Path) -> int:
    removed = 0
    for directory in LEGACY_VIEW_DIRS:
        folder = root / directory
        if not folder.exists():
            continue
        for role in ROLES:
            path = folder / f"{role.lower()}.json"
            if path.exists():
                path.unlink()
                removed += 1
    return removed


def materialize_role_views(root: str | Path) -> dict[str, Any]:
    root = Path(root)
    service = AgentService(root)
    active_ids = _active_ids(root)
    counts: dict[str, int] = {}
    for role in ROLES:
        view = service.bootstrap(role)
        if active_ids is not None:
            queue = [item for item in view["queue"] if str(item.get("id")) in active_ids]
            view["queue"] = queue
            view["queue_count"] = len(queue)
        _write_json(root / "role_views" / f"{role.lower()}.json", view)
        counts[role] = view["queue_count"]
    pruned = _prune_legacy_views(root)
    return {"roles": len(ROLES), "queue_counts": counts, "legacy_views_pruned": pruned}
