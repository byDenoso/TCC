from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .service import AgentService

ROLES = ("DAILY", "ADVISOR", "EXECUTOR", "LEARNER", "EMERGENT")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True), encoding="utf-8")


def materialize_role_views(root: str | Path) -> dict[str, Any]:
    root = Path(root)
    service = AgentService(root)
    counts: dict[str, int] = {}
    for role in ROLES:
        queue = service.queue_for(role)
        bootstrap = service.bootstrap(role)
        _write_json(root / "queues" / f"{role.lower()}.json", {"role": role, "items": queue, "count": len(queue)})
        _write_json(root / "bootstrap" / f"{role.lower()}.json", bootstrap)
        counts[role] = len(queue)
    return {"roles": len(ROLES), "queue_counts": counts}
