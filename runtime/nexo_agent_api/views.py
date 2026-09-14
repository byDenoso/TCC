from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .service import AgentService

ROLES = ("DAILY", "ADVISOR", "EXECUTOR", "LEARNER", "EMERGENT")
ROLE_QUEUE_LIMIT = 5
PRIORITY_RANK = {"CRITICAL": 0, "HIGH": 1, "MEDIUM_HIGH": 2, "MEDIUM": 3, "LOW": 4}
STATUS_RANK = {"VERIFIED": 0, "READY": 1, "RUNNING": 2, "CHECKPOINTED": 3, "WAIT_DEPENDENCY": 4}
PARKED_STATUSES = {"WAIT_DEPENDENCY"}
HOT_STATUSES = {"READY", "RUNNING", "CHECKPOINTED", "WAIT_DEPENDENCY"}


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True), encoding="utf-8")


def _is_hot(item: dict[str, Any]) -> bool:
    status = str(item.get("status", ""))
    return status in HOT_STATUSES or (status == "VERIFIED" and item.get("learning_state") != "LEARNED")


def _refresh_hot_state(root: Path) -> dict[str, int]:
    index_path = root / "indexes" / "active-work.json"
    existing = json.loads(index_path.read_text(encoding="utf-8")) if index_path.exists() else {}
    existing_items = existing.get("work", []) if isinstance(existing, dict) else []

    entities: dict[str, dict[str, Any]] = {}
    folder = root / "entities" / "work"
    if folder.exists():
        for path in sorted(folder.glob("*.json")):
            payload = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                continue
            work_id = payload.get("id") or payload.get("work_id")
            if work_id:
                entities[str(work_id)] = payload

    refreshed: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in existing_items:
        if not isinstance(raw, dict):
            continue
        work_id = raw.get("id") or raw.get("work_id")
        if not work_id:
            continue
        key = str(work_id)
        item = entities.get(key, raw)
        seen.add(key)
        if _is_hot(item):
            refreshed.append(item)

    for key in sorted(set(entities) - seen):
        item = entities[key]
        if _is_hot(item):
            refreshed.append(item)

    payload = dict(existing) if isinstance(existing, dict) else {}
    payload.setdefault("schema_version", "0.6")
    payload.setdefault("source", "GITHUB_TOWER_HOT_SET")
    payload.setdefault(
        "policy",
        "Actionable only: READY|RUNNING|CHECKPOINTED|WAIT_DEPENDENCY plus VERIFIED awaiting learning; blocked/terminal learned/procedural stay cold",
    )
    payload["work"] = refreshed
    payload["count"] = len(refreshed)
    _write_json(index_path, payload)

    snapshot_path = root / "snapshot" / "latest.json"
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8")) if snapshot_path.exists() else {}
    counts = dict(snapshot.get("counts", {})) if isinstance(snapshot, dict) else {}
    counts["active_work"] = len(refreshed)
    snapshot["counts"] = counts

    event_files = sorted((root / "events").rglob("*.json")) if (root / "events").exists() else []
    if event_files:
        latest = json.loads(event_files[-1].read_text(encoding="utf-8"))
        snapshot["event_cursor"] = latest.get("event_id", event_files[-1].stem) if isinstance(latest, dict) else event_files[-1].stem
    _write_json(snapshot_path, snapshot)
    return {"active_work": len(refreshed)}


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
            1 if str(item.get("status", "")) in PARKED_STATUSES else 0,
            0 if item.get("owner_role") == role else 1,
            PRIORITY_RANK.get(str(item.get("priority", "MEDIUM")), 9),
            STATUS_RANK.get(str(item.get("status", "")), 9),
            str(item.get("id", "")),
        ),
    )[:ROLE_QUEUE_LIMIT]


def materialize_role_views(root: str | Path) -> dict[str, Any]:
    root = Path(root)
    state_counts = _refresh_hot_state(root)
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
    return {
        "roles": len(ROLES),
        "queue_counts": counts,
        "queue_limit": ROLE_QUEUE_LIMIT,
        "view_model": "SINGLE_ROLE_VIEW",
        "state_counts": state_counts,
    }
