from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .governance import evaluate_governance
from .service import AgentService, TowerAgentIssue

_SAFE_NAME = re.compile(r"^[A-Za-z0-9_.:-]+$")
_CREATABLE_ENTITY_KINDS = {
    "work",
    "project",
    "hypothesis",
    "campaign",
    "test_group",
    "test",
    "run",
    "result",
    "artifact",
}


def _integer_version(value: Any) -> int:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("version must be numeric") from exc
    if not number.is_integer() or number < 0:
        raise ValueError("version must be a non-negative integer")
    return int(number)


def _invalid(request_id: str, message: str) -> dict[str, Any]:
    return {
        "request_id": request_id,
        "accepted": False,
        "issue": {"code": "INVALID_MUTATION_REQUEST", "message": message, "details": {}},
    }


def apply_mutation_request(root: str | Path, request: dict[str, Any]) -> dict[str, Any]:
    root = Path(root)
    request_id = str(request.get("request_id") or "")
    if not request_id or not _SAFE_NAME.fullmatch(request_id):
        return _invalid(request_id, "request_id is required and must be path-safe")

    entity_kind = str(request.get("entity_kind") or "")
    entity_name = str(request.get("entity_name") or "")
    writer_role = str(request.get("writer_role") or "").upper()
    event_type = str(request.get("event_type") or "")
    changes = request.get("changes")

    if not entity_kind or not _SAFE_NAME.fullmatch(entity_kind):
        return _invalid(request_id, "entity_kind must be path-safe")
    if not entity_name or not _SAFE_NAME.fullmatch(entity_name):
        return _invalid(request_id, "entity_name must be path-safe")
    if writer_role not in AgentService.ROLES:
        return _invalid(request_id, "writer_role is not supported")
    if not event_type or not _SAFE_NAME.fullmatch(event_type):
        return _invalid(request_id, "event_type must be path-safe")
    if not isinstance(changes, dict):
        return _invalid(request_id, "changes must be an object")

    try:
        expected_version = _integer_version(request.get("expected_version"))
    except ValueError:
        return _invalid(request_id, "expected_version must be an integer")

    changes = dict(changes)
    if entity_kind in _CREATABLE_ENTITY_KINDS and expected_version == 0 and "id" in changes:
        if str(changes["id"]) != entity_name:
            return _invalid(request_id, "create identity must match entity_name")
        changes.pop("id")

    governance_request = dict(request)
    governance_request["changes"] = changes
    governance = evaluate_governance(governance_request)
    governance_meta = {
        "autonomy_level": governance.autonomy_level,
        "governance_gate": governance.gate,
    }
    if governance.proposal_hash:
        governance_meta["proposal_hash"] = governance.proposal_hash
    if not governance.allowed:
        return {
            "request_id": request_id,
            "accepted": False,
            **governance_meta,
            "issue": {
                "code": governance.issue_code,
                "message": governance.message,
                "details": {},
            },
        }

    service = AgentService(root)
    path = root / "entities" / entity_kind / f"{entity_name}.json"
    seeded_new_entity = False
    if not path.exists() and expected_version == 0 and entity_kind in _CREATABLE_ENTITY_KINDS:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps({"id": entity_name, "entity_version": 0}, ensure_ascii=False, sort_keys=True),
            encoding="utf-8",
        )
        seeded_new_entity = True
    elif entity_kind == "work" and not path.exists():
        try:
            hydrated = service._hydrate_work(entity_name)
        except TowerAgentIssue as exc:
            return {
                "request_id": request_id,
                "accepted": False,
                **governance_meta,
                "issue": {"code": exc.code, "message": exc.message, "details": exc.details},
            }
        try:
            hydrated["entity_version"] = _integer_version(hydrated.get("entity_version", 1))
        except ValueError:
            return _invalid(request_id, "hydrated entity_version is invalid")
        path.write_text(json.dumps(hydrated, ensure_ascii=False, sort_keys=True), encoding="utf-8")

    try:
        result = service.mutate(
            entity_kind,
            entity_name,
            expected_version=expected_version,
            changes=changes,
            writer_role=writer_role,
            event_type=event_type,
            material=bool(request.get("material", True)),
        )
    except TowerAgentIssue as exc:
        if seeded_new_entity and path.exists():
            try:
                seeded = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                seeded = None
            if isinstance(seeded, dict) and int(seeded.get("entity_version", -1)) == 0:
                path.unlink(missing_ok=True)
        return {
            "request_id": request_id,
            "accepted": False,
            **governance_meta,
            "issue": {"code": exc.code, "message": exc.message, "details": exc.details},
        }

    receipt = {"request_id": request_id, **governance_meta, **result}

    # Work entities drive active-work, role views, and AI-ROI projections. Refresh
    # them immediately after the canonical CAS write/readback so a terminal work
    # mutation cannot remain visible as READY/CHECKPOINTED/WAIT_DEPENDENCY.
    # Projection refresh is intentionally non-authoritative: if it fails, the
    # canonical mutation remains accepted and callers receive an explicit receipt
    # instead of retrying an already-committed write.
    if entity_kind == "work":
        try:
            from .views import materialize_role_views

            projection = materialize_role_views(root)
            receipt["projection_refresh"] = {"status": "PASS", **projection}
        except Exception as exc:  # projection failure must not invalidate committed CAS
            receipt["projection_refresh"] = {
                "status": "FAILED",
                "error_type": type(exc).__name__,
                "message": str(exc),
            }

    if governance.autonomy_level == "L3":
        receipt["l3_report"] = {
            "status": "EXECUTED",
            "intent": request.get("l3_intent"),
            "requested_changes": changes,
            "entity_kind": entity_kind,
            "entity_name": entity_name,
            "entity_version": result.get("entity_version"),
            "readback": result.get("readback"),
            "event_id": result.get("event_id"),
        }
    return receipt
