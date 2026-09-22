"""Deterministic public projection of canonical Tower state.

This is the single generator of the public presentation surface. It lives on the
truth side on purpose: if the presentation repository compiled canonical state
itself, it would own the interpretation of that state, and an interpretation that
lives outside the Tower is how a second truth is born.

Properties this module guarantees:

* **Derived, never authoritative.** It reads canonical state and emits a snapshot
  labelled `projection_only` with `writeback: FORBIDDEN`.
* **Existence comes from entities.** A WORK id present in an index but with no
  `entities/work/<id>.json` never reaches the public surface. Indexes carry
  priority, never existence.
* **Deterministic.** The same canonical input yields the same bytes and the same
  `projection_fingerprint`. Wall-clock time is recorded but excluded from the
  fingerprint, so an unchanged Tower does not produce a churn-only republish.
* **Allowlisted fields.** Every emitted field is explicitly listed. A new field in
  a canonical entity does not leak to the public surface by default.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Iterable

SCHEMA_VERSION = "1"
PROJECTION_CONTRACT = "NEXO_PUBLIC_PROJECTION_V1"

# Only these fields ever reach the public surface. Anything else in a canonical
# entity stays canonical.
WORK_FIELDS = (
    "id",
    "kind",
    "status",
    "operational_status",
    "priority",
    "domain",
    "target_domain",
    "owner_role",
    "title",
    "campaign_id",
    "test_group_id",
    "blocker_class",
    "dependency_class",
)
TEST_FIELDS = (
    "id",
    "status",
    "domain",
    "target_domain",
    "title",
    "campaign_id",
    "test_group_id",
    "scientific_fingerprint",
)
CAMPAIGN_FIELDS = (
    "roadmap_id",
    "campaign_id",
    "title",
    "domain",
    "subdomain",
    "state",
    "priority",
    "created_at",
    "question",
    "semantic_description",
    "semantic_state",
    "claim_boundary",
)
ATLAS_PROJECTION_FIELDS = (
    "visible",
    "node_type",
    "parent_subdomain",
    "label",
    "show_tests",
    "show_hypothesis_nodes",
    "description_mode",
)
CAPABILITY_FIELDS = ("status", "backend", "contract_name")
INTERDOMAIN_FIELDS = (
    "id",
    "status",
    "relation_type",
    "source_domains",
    "target_domains",
    "advisor_disposition",
    "test_ref",
    "test_refs",
    "evidence_refs",
    "lesson_refs",
    "updated_at",
)

# Reproduced from CONTROL.json so the projection can state, in its own manifest,
# under which authority rules it was produced.
CONTROL_FIELDS = (
    "truth_owner",
    "write_model",
    "write_guard",
    "derived_indexes_authority",
    "atlas_role",
    "drive_role",
    "runtime_revision",
)


def _read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def _pick(payload: dict[str, Any], fields: Iterable[str]) -> dict[str, Any]:
    return {field: payload[field] for field in fields if payload.get(field) is not None}


def _canonical_blob(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _fingerprint(payload: Any) -> str:
    return "sha256:" + hashlib.sha256(_canonical_blob(payload).encode("utf-8")).hexdigest()


def _apply_target_domain_projection(payload: dict[str, Any]) -> dict[str, Any]:
    """Render target-owned work/tests under the target domain without erasing provenance."""
    projected = dict(payload)
    source_domain = projected.get("domain")
    target_domain = projected.get("target_domain")
    if target_domain and source_domain and target_domain != source_domain:
        projected["method_domain"] = source_domain
        projected["domain"] = target_domain
        projected["domain_projection"] = "TARGET_DOMAIN"
    return projected


def _load_cross_domain(root: Path) -> list[dict[str, Any]]:
    """Project canonical Interdomain relations as derived Learning filaments."""
    index = _read_json(root / "indexes" / "interdomain-active.json", {}) or {}
    entity_root = root / "entities" / "interdomain"
    projected: list[dict[str, Any]] = []
    for item in index.get("items") or []:
        if not isinstance(item, dict):
            continue
        relation_id = item.get("id")
        if not relation_id:
            continue
        entity = _read_json(entity_root / f"{relation_id}.json", {}) or {}
        source = entity if isinstance(entity, dict) and entity else item
        filament = _pick(source, INTERDOMAIN_FIELDS)
        filament["id"] = str(relation_id)
        filament["projection_label"] = "DERIVED_NOT_EVIDENCE"
        filament["via"] = (
            "LEARNING_INTERDOMAIN" if filament.get("lesson_refs") else "INTERDOMAIN"
        )
        projected.append(filament)
    return projected


def _load_entities(root: Path, kind: str, fields: Iterable[str]) -> dict[str, dict[str, Any]]:
    folder = root / "entities" / kind
    if not folder.is_dir():
        return {}
    loaded: dict[str, dict[str, Any]] = {}
    for path in sorted(folder.glob("*.json")):
        payload = _read_json(path)
        if not isinstance(payload, dict):
            continue
        entity_id = payload.get("id") or payload.get(f"{kind}_id")
        if not entity_id:
            continue
        loaded[str(entity_id)] = _pick(payload, fields)
    return loaded


def _campaign_source_links(payload: dict[str, Any]) -> list[dict[str, str]]:
    """Return public source links without projecting the full roadmap prior-art payload."""
    links: dict[str, dict[str, str]] = {}

    def add(url: str, label: str | None = None, kind: str = "REFERENCE") -> None:
        normalized = str(url or "").strip()
        if not normalized.startswith(("https://", "http://")):
            return
        links.setdefault(
            normalized,
            {
                "label": str(label or normalized).strip(),
                "url": normalized,
                "kind": kind,
            },
        )

    for item in payload.get("source_links") or []:
        if isinstance(item, str):
            add(item)
        elif isinstance(item, dict):
            add(
                str(item.get("url") or ""),
                str(item.get("label") or item.get("title") or item.get("url") or ""),
                str(item.get("kind") or "REFERENCE").upper(),
            )

    def walk(value: Any) -> None:
        if isinstance(value, dict):
            for nested in value.values():
                walk(nested)
            return
        if isinstance(value, list):
            for nested in value:
                walk(nested)
            return
        if not isinstance(value, str):
            return

        for url in re.findall(r"https?://[^\s\])}>\"']+", value):
            add(url.rstrip(".,;:"), value, "REFERENCE")
        for match in re.finditer(r"\barXiv\s*:\s*(\d{4}\.\d{4,5}(?:v\d+)?)", value, flags=re.IGNORECASE):
            arxiv_id = match.group(1)
            add(f"https://arxiv.org/abs/{arxiv_id}", value, "ARXIV")

    walk(payload.get("prior_art_snapshot"))
    kind_priority = {"OFFICIAL": 0, "PRIMARY": 1, "ARXIV": 2, "REFERENCE": 3}
    return sorted(
        links.values(),
        key=lambda item: (
            kind_priority.get(str(item.get("kind") or "REFERENCE").upper(), 4),
            str(item.get("url") or ""),
        ),
    )


def _load_campaigns(root: Path) -> list[dict[str, Any]]:
    """Project roadmap campaigns as first-class, public, read-only Atlas entities."""
    folder = root / "roadmaps"
    if not folder.is_dir():
        return []

    campaigns: list[dict[str, Any]] = []
    for path in sorted(folder.glob("*.json")):
        payload = _read_json(path)
        if not isinstance(payload, dict):
            continue
        campaign_id = str(payload.get("campaign_id") or "").strip()
        if not campaign_id:
            continue

        record = _pick(payload, CAMPAIGN_FIELDS)
        record["campaign_id"] = campaign_id
        atlas_projection = payload.get("atlas_projection")
        if isinstance(atlas_projection, dict):
            record["atlas_projection"] = _pick(atlas_projection, ATLAS_PROJECTION_FIELDS)
        sources = _campaign_source_links(payload)
        if sources:
            record["source_links"] = sources
        campaigns.append(record)

    campaigns.sort(key=lambda item: str(item.get("campaign_id") or ""))
    return campaigns


def build_public_projection(
    root: str | Path,
    *,
    tower_repository: str = "byDenoso/NEXO-Obsidian-Vault",
    tower_commit: str | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Compile the public projection from canonical state under `root`.

    `generated_at` is recorded for humans and deliberately excluded from the
    fingerprint: two runs over identical canonical state must agree.
    """
    root = Path(root)
    control = _read_json(root / "CONTROL.json", {}) or {}
    snapshot = _read_json(root / "snapshot" / "latest.json", {}) or {}
    active_index = _read_json(root / "indexes" / "active-work.json", {}) or {}

    work_entities = _load_entities(root, "work", WORK_FIELDS)
    human_flags = _load_entities(root, "work", ("human_action_required",))
    test_entities = _load_entities(root, "test", TEST_FIELDS)
    campaigns = _load_campaigns(root)

    # Index order is priority. Existence is the entity. An index entry without an
    # entity is reported as dropped, never rendered.
    ordered_ids: list[str] = []
    dropped: list[str] = []
    for item in active_index.get("work") or []:
        if not isinstance(item, dict):
            continue
        work_id = item.get("id") or item.get("work_id")
        if not work_id:
            continue
        work_id = str(work_id)
        if work_id in work_entities:
            if work_id not in ordered_ids:
                ordered_ids.append(work_id)
        else:
            dropped.append(work_id)

    work = [
        _apply_target_domain_projection(dict(work_entities[work_id], id=work_id))
        for work_id in ordered_ids
    ]
    human_work_ids = [
        work_id for work_id in ordered_ids
        if human_flags.get(work_id, {}).get("human_action_required") is True
    ]

    cross_domain = _load_cross_domain(root)

    capabilities_manifest = _read_json(root / "manifests" / "capabilities.json", {}) or {}
    capabilities = {
        str(capability_id): _pick(definition, CAPABILITY_FIELDS)
        for capability_id, definition in sorted((capabilities_manifest.get("capabilities") or {}).items())
        if isinstance(definition, dict)
    }

    content: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "contract": PROJECTION_CONTRACT,
        "authority_declaration": _pick(control, CONTROL_FIELDS),
        "event_cursor": snapshot.get("event_cursor"),
        "counts": {
            "active_work": len(work),
            "work_entities": len(work_entities),
            "tests": len(test_entities),
            "campaigns": len(campaigns),
            "cross_domain": len(cross_domain),
            "capabilities": len(capabilities),
            "index_only_dropped": len(dropped),
            "needs_dener": len(human_work_ids),
        },
        "human_gates": {"work_ids": human_work_ids, "count": len(human_work_ids)},
        "work": work,
        "tests": [
            _apply_target_domain_projection(dict(test_entities[key], id=key))
            for key in sorted(test_entities)
        ],
        "campaigns": campaigns,
        "crossDomain": cross_domain,
        "capabilities": capabilities,
        "index_only_dropped": sorted(dropped),
    }

    manifest = {
        "authority": "TOWER_V06",
        "projection_only": True,
        "writeback": "FORBIDDEN",
        "tower_repository": tower_repository,
        "tower_commit": tower_commit,
        "event_cursor": snapshot.get("event_cursor"),
        "projection_fingerprint": _fingerprint(content),
        "generated_at": generated_at,
    }
    return {"manifest": manifest, **content}


def projection_bytes(projection: dict[str, Any]) -> bytes:
    """Stable serialization: same projection, same bytes, LF terminated."""
    return (_canonical_blob(projection) + "\n").encode("utf-8")


def verify_projection(projection: dict[str, Any]) -> tuple[bool, str]:
    """Recompute the fingerprint from the content and compare with the manifest."""
    manifest = dict(projection.get("manifest") or {})
    declared = str(manifest.get("projection_fingerprint") or "")
    content = {key: value for key, value in projection.items() if key != "manifest"}
    actual = _fingerprint(content)
    if declared != actual:
        return False, f"declared={declared} actual={actual}"
    if manifest.get("authority") != "TOWER_V06":
        return False, f"authority={manifest.get('authority')!r}"
    if manifest.get("projection_only") is not True:
        return False, "projection_only is not true"
    if manifest.get("writeback") != "FORBIDDEN":
        return False, f"writeback={manifest.get('writeback')!r}"
    if not manifest.get("event_cursor"):
        return False, "event_cursor is missing"
    if not manifest.get("tower_commit"):
        return False, "tower_commit is missing"
    return True, actual
