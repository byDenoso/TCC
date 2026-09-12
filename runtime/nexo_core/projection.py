from __future__ import annotations

from collections import Counter
from typing import Any, Iterable

from runtime.nexo_core.models import CanonicalEntity

EDGE_TYPES = {
    "DEPENDS_ON",
    "BELONGS_TO",
    "DERIVED_FROM",
    "PRODUCED",
    "BLOCKED_BY",
    "EVIDENCED_BY",
    "EXECUTED_BY",
}


def _listify(value: Any) -> list[str]:
    if value is None or value == "":
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, (list, tuple, set)):
        return [str(item) for item in value if item]
    return [str(value)]


def _scope_for(entity: CanonicalEntity) -> str:
    prefix = entity.entity_ref.split("::", 1)[0].upper()
    domain = str(entity.data.get("domain", "")).upper()
    explicit = str(entity.data.get("scope", "")).lower()
    if explicit in {"research", "olympus", "nexo", "system"}:
        return explicit
    if prefix in {"CLIENT", "MEASUREMENT", "CHECKIN", "PROFILE", "PLAN"} or domain == "OLYMPUS":
        return "olympus"
    if prefix in {"AGENT", "AUTOMATION", "RUNTIME"} or domain == "NEXO":
        return "nexo"
    if prefix in {"SYSTEM", "DEPLOYMENT", "REPOSITORY", "SNAPSHOT"}:
        return "system"
    return "research"


def build_snapshot(
    entities: Iterable[CanonicalEntity],
    *,
    snapshot_id: str,
    generated_at: str,
    event_cursor: str,
) -> dict[str, Any]:
    materialized = list(entities)
    states = Counter(entity.state.lower() for entity in materialized)

    nodes: dict[str, dict[str, Any]] = {}
    edges: list[dict[str, str]] = []
    edge_seen: set[tuple[str, str, str]] = set()
    sections: dict[str, list[str]] = {"research": [], "olympus": [], "nexo": [], "system": []}

    for entity in materialized:
        prefix = entity.entity_ref.split("::", 1)[0]
        nodes[entity.entity_ref] = {
            "id": entity.entity_ref,
            "type": prefix,
            "label": entity.data.get("label", entity.entity_ref),
            "domain": entity.data.get("domain"),
            "status": entity.state,
            "version": entity.entity_version,
        }
        sections[_scope_for(entity)].append(entity.entity_ref)

    def add_edge(source: str, target: str, edge_type: str) -> None:
        key = (source, target, edge_type)
        if key in edge_seen:
            return
        edge_seen.add(key)
        edges.append({"source": source, "target": target, "type": edge_type})
        if target not in nodes:
            prefix = target.split("::", 1)[0]
            nodes[target] = {
                "id": target,
                "type": prefix,
                "label": target,
                "domain": None,
                "status": "UNKNOWN",
                "version": 0,
            }

    for entity in materialized:
        data = entity.data
        for target in _listify(data.get("dependency_ids")):
            add_edge(entity.entity_ref, target, "DEPENDS_ON")
        parent = data.get("parent_id")
        if parent:
            add_edge(entity.entity_ref, str(parent), "BELONGS_TO")
        for target in _listify(data.get("evidence_refs") or data.get("evidence_ref")):
            add_edge(entity.entity_ref, target, "EVIDENCED_BY")
        result_ref = data.get("result_ref")
        if result_ref:
            add_edge(entity.entity_ref, str(result_ref), "PRODUCED")
        for target in _listify(data.get("blocked_by")):
            add_edge(entity.entity_ref, target, "BLOCKED_BY")
        for target in _listify(data.get("executed_by")):
            add_edge(entity.entity_ref, target, "EXECUTED_BY")
        for target in _listify(data.get("derived_from")):
            add_edge(entity.entity_ref, target, "DERIVED_FROM")

    overview: dict[str, Any] = {"entities": len(materialized)}
    overview.update(states)

    return {
        "schema_version": "0.5",
        "snapshot_id": snapshot_id,
        "generated_at": generated_at,
        "event_cursor": event_cursor,
        "overview": overview,
        "research": {"entity_refs": sections["research"]},
        "olympus": {"entity_refs": sections["olympus"]},
        "nexo": {"entity_refs": sections["nexo"]},
        "system": {"entity_refs": sections["system"]},
        "nodes": list(nodes.values()),
        "edges": edges,
    }


def validate_snapshot(snapshot: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    required = {
        "schema_version",
        "snapshot_id",
        "generated_at",
        "event_cursor",
        "overview",
        "research",
        "olympus",
        "nexo",
        "system",
        "nodes",
        "edges",
    }
    for key in sorted(required):
        if key not in snapshot:
            errors.append(f"missing:{key}")
    if snapshot.get("schema_version") != "0.5":
        errors.append("schema_version")
    for key in ("snapshot_id", "generated_at", "event_cursor"):
        if not snapshot.get(key):
            errors.append(f"empty:{key}")
    if not isinstance(snapshot.get("nodes"), list):
        errors.append("nodes:not_list")
        return errors
    if not isinstance(snapshot.get("edges"), list):
        errors.append("edges:not_list")
        return errors

    node_ids = [node.get("id") for node in snapshot["nodes"] if isinstance(node, dict)]
    if len(node_ids) != len(set(node_ids)):
        errors.append("nodes:duplicate_id")
    known = set(node_ids)
    for edge in snapshot["edges"]:
        if not isinstance(edge, dict):
            errors.append("edge:not_object")
            continue
        if edge.get("type") not in EDGE_TYPES:
            errors.append(f"edge:invalid_type:{edge.get('type')}")
        if edge.get("source") not in known:
            errors.append(f"edge:missing_source:{edge.get('source')}")
        if edge.get("target") not in known:
            errors.append(f"edge:missing_target:{edge.get('target')}")
    return errors
