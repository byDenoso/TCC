from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

from .service import AgentService

ROLES = ("DAILY", "ADVISOR", "EXECUTOR", "LEARNER", "EMERGENT")
ROLE_QUEUE_LIMIT = 5
PRIORITY_RANK = {"CRITICAL": 0, "HIGH": 1, "MEDIUM_HIGH": 2, "MEDIUM": 3, "LOW": 4}
STATUS_RANK = {"VERIFIED": 0, "READY": 1, "RUNNING": 2, "CHECKPOINTED": 3, "WAIT_DEPENDENCY": 4}
PARKED_STATUSES = {"WAIT_DEPENDENCY"}
HOT_STATUSES = {"READY", "RUNNING", "CHECKPOINTED", "WAIT_DEPENDENCY"}
_RUNTIME_EVENT_NAME = re.compile(r"^\d{8}T\d{12}Z-[A-Za-z0-9]+\.json$")
SEMANTIC_ENTITY_COUNT_KEYS = {
    "hypothesis": "hypotheses",
    "test": "tests",
    "campaign": "campaigns",
    "decision": "decisions",
    "program": "programs",
}


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True), encoding="utf-8")


def _is_hot(item: dict[str, Any]) -> bool:
    if item.get("cold_backlog") is True:
        return False
    status = str(item.get("status", ""))
    return status in HOT_STATUSES or (status == "VERIFIED" and item.get("learning_state") != "LEARNED")


def _runtime_event_paths(root: Path) -> list[Path]:
    events_root = root / "events"
    if not events_root.exists():
        return []
    return sorted(
        (path for path in events_root.rglob("*.json") if _RUNTIME_EVENT_NAME.fullmatch(path.name)),
        key=lambda path: path.name,
    )


def _latest_runtime_event_id(root: Path) -> str | None:
    candidates = _runtime_event_paths(root)
    if not candidates:
        return None
    latest_path = candidates[-1]
    payload = json.loads(latest_path.read_text(encoding="utf-8"))
    if isinstance(payload, dict) and payload.get("event_id"):
        return str(payload["event_id"])
    return latest_path.stem


def _counter_dict(values: list[str]) -> dict[str, int]:
    return dict(sorted(Counter(values).items()))


def _semantic_entity_counts(root: Path) -> tuple[dict[str, int], dict[str, str]]:
    counts: dict[str, int] = {}
    sources: dict[str, str] = {}
    entities_root = root / "entities"
    for folder_name, count_key in SEMANTIC_ENTITY_COUNT_KEYS.items():
        folder = entities_root / folder_name
        if not folder.exists():
            continue
        counts[count_key] = sum(1 for path in folder.glob("*.json") if path.is_file())
        sources[count_key] = f"entities/{folder_name}/*.json"
    return counts, sources


def _write_ai_roi_snapshot(root: Path, active_items: list[dict[str, Any]], event_cursor: str | None) -> dict[str, int]:
    events: list[dict[str, Any]] = []
    for path in _runtime_event_paths(root):
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            events.append(payload)

    receipts: list[dict[str, Any]] = []
    receipts_root = root / "mutations" / "receipts"
    if receipts_root.exists():
        for path in sorted(receipts_root.glob("*.json")):
            payload = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                receipts.append(payload)

    statuses = [str(item.get("status", "UNKNOWN")) for item in active_items]
    owners = [str(item.get("owner_role", "UNASSIGNED")) for item in active_items]
    event_types = [str(item.get("event_type", "UNKNOWN")) for item in events]
    writer_roles = [str(item.get("writer_role", "UNKNOWN")) for item in events]

    accepted = sum(1 for item in receipts if item.get("accepted") is True)
    rejected = sum(1 for item in receipts if item.get("accepted") is False)
    readback_pass = sum(1 for item in receipts if item.get("readback") == "PASS")
    readback_fail = sum(1 for item in receipts if item.get("readback") not in (None, "PASS"))
    material_events = sum(1 for item in events if item.get("material") is True)
    verified_events = sum(1 for event_type in event_types if "VERIFIED" in event_type)
    decision_events = sum(1 for event_type in event_types if "DECISION" in event_type)

    flow = {
        "executor_ready": sum(1 for item in active_items if item.get("status") == "READY" and item.get("owner_role") == "EXECUTOR"),
        "advisor_ready": sum(1 for item in active_items if item.get("status") == "READY" and item.get("owner_role") == "ADVISOR"),
        "handoff_pending": sum(1 for item in active_items if item.get("status") == "READY" and item.get("owner_role") == "ADVISOR"),
        "wait_dependency": sum(1 for item in active_items if item.get("status") == "WAIT_DEPENDENCY"),
    }

    payload = {
        "schema_version": "0.6",
        "classification": "DERIVED_NOT_AUTHORITY",
        "truth_owner": "byDenoso/NEXO-Obsidian-Vault@main:TOWER_V06",
        "source_event_cursor": event_cursor,
        "active_work": {
            "count": len(active_items),
            "by_status": _counter_dict(statuses),
            "by_owner": _counter_dict(owners),
        },
        "flow": flow,
        "events": {
            "runtime_total": len(events),
            "material": material_events,
            "verified": verified_events,
            "decision": decision_events,
            "by_type": _counter_dict(event_types),
            "by_writer_role": _counter_dict(writer_roles),
        },
        "mutations": {
            "receipts_total": len(receipts),
            "accepted": accepted,
            "rejected": rejected,
            "readback_pass": readback_pass,
            "readback_fail": readback_fail,
        },
        "roi": {
            "mode": "PROXY_ONLY_NO_COST_DATA",
            "cost_data": "UNAVAILABLE",
            "useful_output_proxies": {
                "verified_events": verified_events,
                "decision_events": decision_events,
                "material_events": material_events,
            },
            "note": "No monetary ROI is calculated without measured cost data. This snapshot exposes reconstructible operational proxies only.",
        },
    }
    _write_json(root / "snapshot" / "ai-roi.json", payload)
    return {
        "runtime_events": len(events),
        "mutation_receipts": len(receipts),
        "executor_ready": flow["executor_ready"],
    }


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

    refreshed_by_id: dict[str, dict[str, Any]] = {}
    for raw in existing_items:
        if not isinstance(raw, dict):
            continue
        work_id = raw.get("id") or raw.get("work_id")
        if not work_id:
            continue
        key = str(work_id)
        item = entities.get(key, raw)
        if _is_hot(item):
            refreshed_by_id[key] = item

    for key, item in entities.items():
        if key not in refreshed_by_id and _is_hot(item):
            refreshed_by_id[key] = item

    refreshed = list(refreshed_by_id.values())
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
    semantic_counts, semantic_sources = _semantic_entity_counts(root)
    counts.update(semantic_counts)
    snapshot["counts"] = counts
    snapshot["semantic_freshness"] = "CURRENT_CANONICAL_ENTITY_SCAN"
    snapshot["semantic_count_sources"] = semantic_sources

    event_cursor = _latest_runtime_event_id(root)
    if event_cursor:
        snapshot["event_cursor"] = event_cursor
    _write_json(snapshot_path, snapshot)
    telemetry = _write_ai_roi_snapshot(root, refreshed, event_cursor)
    return {"active_work": len(refreshed), **telemetry}


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
