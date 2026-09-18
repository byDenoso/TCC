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
    "title",
    "campaign_id",
    "test_group_id",
    "scientific_fingerprint",
)
CAPABILITY_FIELDS = ("status", "backend", "contract_name")

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
    test_entities = _load_entities(root, "test", TEST_FIELDS)

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

    work = [dict(work_entities[work_id], id=work_id) for work_id in ordered_ids]

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
            "capabilities": len(capabilities),
            "index_only_dropped": len(dropped),
        },
        "work": work,
        "tests": [dict(test_entities[key], id=key) for key in sorted(test_entities)],
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
