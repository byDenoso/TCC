from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
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


def _runtime_artifacts(root: Path) -> list[dict[str, Any]]:
    folder = root / "runtime" / "artifacts"
    if not folder.exists():
        return []
    result: list[dict[str, Any]] = []
    for path in sorted(folder.glob("*.json")):
        payload = _read_json(path)
        if payload:
            result.append(payload)
    return result


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _numeric_summary(values: list[float], *, integer_total: bool = False) -> dict[str, Any]:
    if not values:
        return {"samples": 0, "status": "UNAVAILABLE"}
    total = sum(values)
    if integer_total:
        total_value: int | float = int(total)
    else:
        total_value = round(float(total), 6)
    average = round(float(total) / len(values), 6)
    return {"samples": len(values), "total": total_value, "average": average}


def _capability_performance(root: Path) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for artifact in _runtime_artifacts(root):
        capability_id = str(artifact.get("capability_id") or "").strip()
        if capability_id:
            grouped[capability_id].append(artifact)

    by_capability: dict[str, dict[str, Any]] = {}
    for capability_id in sorted(grouped):
        artifacts = grouped[capability_id]
        attempts = len(artifacts)
        validation_states = [str(item.get("validation_status") or "").strip().upper() for item in artifacts]
        successes = sum(1 for state in validation_states if state == "PASS")
        failures = sum(1 for state in validation_states if state in {"FAIL", "FAILED", "ERROR"})

        runtime_values = [float(item["runtime_ms"]) for item in artifacts if _is_number(item.get("runtime_ms"))]
        retry_values = [float(item["retry_count"]) for item in artifacts if _is_number(item.get("retry_count"))]
        cost_values = [float(item["measured_cost_usd"]) for item in artifacts if _is_number(item.get("measured_cost_usd"))]

        by_capability[capability_id] = {
            "attempts": attempts,
            "successes": successes,
            "failures": failures,
            "success_rate": round(successes / attempts, 4) if attempts else None,
            "runtime_ms": _numeric_summary(runtime_values),
            "retries": _numeric_summary(retry_values, integer_total=True),
            "cost_usd": _numeric_summary(cost_values),
        }

    return {
        "by_capability_id": by_capability,
        "source": "runtime/artifacts/*.json explicit capability/runtime/retry/cost fields only",
    }


def _is_human_intervention(event: dict[str, Any]) -> bool:
    writer_role = str(event.get("writer_role", "")).upper()
    actor_type = str(event.get("actor_type", "")).upper()
    return event.get("human_intervention") is True or writer_role in HUMAN_WRITER_ROLES or actor_type == "HUMAN"


def _dependency_wait_metrics(work: list[dict[str, Any]]) -> dict[str, Any]:
    waiting = [item for item in work if str(item.get("status", "")).upper() == "WAIT_DEPENDENCY"]
    by_class: Counter[str] = Counter()
    human_attention = 0
    retryable = 0
    unclassified = 0

    for item in waiting:
        dependency_class = str(item.get("dependency_class") or "").strip().upper() or "UNCLASSIFIED"
        by_class[dependency_class] += 1
        if item.get("human_action_required") is True:
            human_attention += 1
        if item.get("auto_retry_eligible") is True:
            retryable += 1
        if dependency_class == "UNCLASSIFIED":
            unclassified += 1

    return {
        "total": len(waiting),
        "human_attention": human_attention,
        "retryable": retryable,
        "unclassified": unclassified,
        "by_class": dict(sorted(by_class.items())),
        "source": "entities/work/*.json explicit dependency classification fields only",
    }


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
    dependency_wait = _dependency_wait_metrics(work)
    capability_performance = _capability_performance(root)

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
        "dependency_wait": dependency_wait,
    }
    roi["quality"] = {
        "duplicate_execution_prevented_events": duplicate_execution_prevented,
    }
    roi["capability_performance"] = capability_performance
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
        "dependency_wait": dependency_wait,
        "capability_performance": capability_performance,
    }
