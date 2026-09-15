from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

_RUNTIME_EVENT_NAME = re.compile(r"^\d{8}T\d{12}Z-[A-Za-z0-9]+\.json$")
TERMINAL_WORK_STATUSES = {"DONE", "VERIFIED", "REJECTED", "FAILED", "SUPERSEDED"}
HUMAN_WRITER_ROLES = {"DIRECTOR", "HUMAN"}
SEMANTIC_ENTITY_COUNT_KEYS = {
    "hypothesis": "hypotheses",
    "test": "tests",
    "campaign": "campaigns",
    "decision": "decisions",
    "program": "programs",
}


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True), encoding="utf-8")


def _semantic_entity_counts(root: Path) -> tuple[dict[str, int], dict[str, str]]:
    counts: dict[str, int] = {}
    sources: dict[str, str] = {}
    for folder_name, count_key in SEMANTIC_ENTITY_COUNT_KEYS.items():
        folder = root / "entities" / folder_name
        if not folder.exists():
            continue
        counts[count_key] = sum(1 for path in folder.glob("*.json") if path.is_file())
        sources[count_key] = f"entities/{folder_name}/*.json"
    return counts, sources


def _work_entities(root: Path) -> list[dict[str, Any]]:
    folder = root / "entities" / "work"
    if not folder.exists():
        return []
    result: list[dict[str, Any]] = []
    for path in sorted(folder.glob("*.json")):
        payload = _read_json(path)
        if payload:
            result.append(payload)
    return result


def _runtime_events(root: Path) -> list[dict[str, Any]]:
    events_root = root / "events"
    if not events_root.exists():
        return []
    result: list[dict[str, Any]] = []
    for path in sorted(events_root.rglob("*.json"), key=lambda item: item.name):
        if not _RUNTIME_EVENT_NAME.fullmatch(path.name):
            continue
        payload = _read_json(path)
        if payload:
            result.append(payload)
    return result


def _is_human_intervention(event: dict[str, Any]) -> bool:
    writer_role = str(event.get("writer_role", "")).upper()
    actor_type = str(event.get("actor_type", "")).upper()
    return event.get("human_intervention") is True or writer_role in HUMAN_WRITER_ROLES or actor_type == "HUMAN"


def enrich_materialized_state(root: str | Path) -> dict[str, Any]:
    root = Path(root)

    latest_path = root / "snapshot" / "latest.json"
    latest = _read_json(latest_path)
    counts = dict(latest.get("counts", {})) if isinstance(latest.get("counts", {}), dict) else {}
    semantic_counts, semantic_sources = _semantic_entity_counts(root)
    counts.update(semantic_counts)
    latest["counts"] = counts
    latest["semantic_freshness"] = "CURRENT_CANONICAL_ENTITY_SCAN"
    latest["semantic_count_sources"] = semantic_sources
    _write_json(latest_path, latest)

    roi_path = root / "snapshot" / "ai-roi.json"
    roi = _read_json(roi_path)
    events = _runtime_events(root)
    work = _work_entities(root)

    material_events = [event for event in events if event.get("material") is True]
    human_intervention_events = sum(1 for event in events if _is_human_intervention(event))
    human_material_events = sum(1 for event in material_events if _is_human_intervention(event))
    autonomous_material_events = len(material_events) - human_material_events
    autonomous_material_rate = round(autonomous_material_events / len(material_events), 4) if material_events else None
    terminal_work = sum(1 for item in work if str(item.get("status", "")).upper() in TERMINAL_WORK_STATUSES)
    verified_work = sum(1 for item in work if str(item.get("status", "")).upper() == "VERIFIED")
    duplicate_execution_prevented = sum(
        1 for event in events if str(event.get("event_type", "")) == "DUPLICATE_EXECUTION_PREVENTED"
    )

    roi["delivery"] = {
        "terminal_work": terminal_work,
        "verified_work": verified_work,
        "source": "entities/work/*.json",
    }
    roi["autonomy"] = {
        "human_intervention_events": human_intervention_events,
        "autonomous_material_events": autonomous_material_events,
        "autonomous_material_rate": autonomous_material_rate,
        "classification_rule": "explicit human_intervention=true OR writer_role in DIRECTOR|HUMAN OR actor_type=HUMAN",
    }
    roi["quality"] = {
        "duplicate_execution_prevented_events": duplicate_execution_prevented,
    }
    roi_section = roi.setdefault("roi", {})
    proxies = roi_section.setdefault("useful_output_proxies", {})
    proxies["terminal_work"] = terminal_work
    proxies["human_intervention_events"] = human_intervention_events
    _write_json(roi_path, roi)

    return {
        "semantic_counts": semantic_counts,
        "terminal_work": terminal_work,
        "verified_work": verified_work,
        "human_intervention_events": human_intervention_events,
        "autonomous_material_events": autonomous_material_events,
        "autonomous_material_rate": autonomous_material_rate,
        "duplicate_execution_prevented_events": duplicate_execution_prevented,
    }
