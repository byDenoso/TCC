from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .service import AgentService

ROLES = ("DAILY", "ADVISOR", "EXECUTOR", "LEARNER", "EMERGENT")


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


def _write_legacy_stubs(root: Path, role: str) -> None:
    ref = f"role_views/{role.lower()}.json"
    _write_json(root / "bootstrap" / f"{role.lower()}.json", {
        "role": role,
        "queue": [],
        "queue_count": 0,
        "compatibility": "SUPERSEDED_BY_ROLE_VIEW",
        "role_view_ref": ref,
    })
    _write_json(root / "queues" / f"{role.lower()}.json", {
        "role": role,
        "items": [],
        "count": 0,
        "compatibility": "SUPERSEDED_BY_ROLE_VIEW",
        "role_view_ref": ref,
    })


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
        _write_legacy_stubs(root, role)
        counts[role] = view["queue_count"]
    return {"roles": len(ROLES), "queue_counts": counts, "legacy_mode": "STUBS_ONLY"}
