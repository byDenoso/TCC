from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from .governance import evaluate_governance
from .service import AgentService, TowerAgentIssue
from .tower_paths import entity_path

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
    "lesson",
}
_RESULT_TRANSPORT_FIELDS = {"executed_at", "inbox_ref"}


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


def _json_equal(left: Any, right: Any) -> bool:
    """Type-sensitive equality for canonical JSON (``1``, ``1.0`` and ``true`` differ)."""
    return json.dumps(left, ensure_ascii=False, sort_keys=True, separators=(",", ":")) == json.dumps(
        right, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _result_replay_receipt(current: dict[str, Any], changes: dict[str, Any], *,
                           request_id: str, expected_version: int,
                           governance_meta: dict[str, Any]) -> dict[str, Any] | None:
    """Classify immutable result replays before they can bump version or emit an event.

    Transport time/reference do not make an otherwise byte-equivalent scientific
    payload a new result.  Reusing the same inbox identity with different result
    content is a conflict; it must never rewrite the first canonical result.
    """
    if int(current.get("entity_version") or 0) != expected_version:
        return None
    if not any(current.get(key) not in (None, "", [], {})
               for key in ("verdict", "decision", "result_summary", "statistics", "reproducibility")):
        return None
    comparable = {key: value for key, value in changes.items() if key not in _RESULT_TRANSPORT_FIELDS}
    different = sorted(key for key, value in comparable.items() if not _json_equal(current.get(key), value))
    if not different:
        return {
            "request_id": request_id,
            "accepted": True,
            **governance_meta,
            "status": "NO_OP",
            "reason": "RESULT_PAYLOAD_ALREADY_CANONICAL",
            "entity_version": expected_version,
            "readback": "PASS",
        }
    incoming_ref = str(changes.get("inbox_ref") or "")
    if incoming_ref and incoming_ref == str(current.get("inbox_ref") or ""):
        return {
            "request_id": request_id,
            "accepted": False,
            **governance_meta,
            "issue": {
                "code": "INBOX_RESULT_IDENTITY_CONFLICT",
                "message": "The same result source identity has different canonical content.",
                "details": {"different_fields": different},
            },
        }
    def instant(value: Any) -> datetime | None:
        try:
            stamp = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except (TypeError, ValueError):
            return None
        return stamp if stamp.tzinfo is not None else None

    incoming_raw, current_raw = changes.get("executed_at"), current.get("executed_at")
    incoming_at, current_at = instant(incoming_raw), instant(current_raw)
    if (incoming_at is None or (current_raw not in (None, "") and current_at is None)
            or (current_at is not None and incoming_at <= current_at)):
        return {
            "request_id": request_id,
            "accepted": False,
            **governance_meta,
            "issue": {
                "code": "INBOX_RESULT_ORDER_CONFLICT",
                "message": "A different result cannot replace canonical content without a later execution time.",
                "details": {"different_fields": different},
            },
        }
    return None


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
    path = entity_path(root, entity_kind, entity_name)
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

    if path.exists():
        try:
            current = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            current = None
        durable_record_replay = (
            entity_kind == "artifact" and expected_version == 0
            and set(changes) == {"kind", "status", "source", "created_at", "payload"}
            and changes.get("status") == "RECORDED"
            and event_type == f"{changes.get('kind')}_RECORDED"
        )
        if (isinstance(current, dict) and durable_record_replay
                and all(_json_equal(current.get(key), value) for key, value in changes.items())):
            return {
                "request_id": request_id,
                "accepted": True,
                **governance_meta,
                "status": "NO_OP",
                "reason": "MUTATION_ALREADY_CANONICAL",
                "entity_version": int(current.get("entity_version") or 0),
                "readback": "PASS",
            }
        if (isinstance(current, dict) and entity_kind == "test"
                and event_type == "TEST_RESULT_RECORDED"):
            replay = _result_replay_receipt(
                current, changes, request_id=request_id, expected_version=expected_version,
                governance_meta=governance_meta)
            if replay is not None:
                return replay

    try:
        internal_context = {}
        if "_scientific_review_authority" in request:
            internal_context["_scientific_review_authority"] = request["_scientific_review_authority"]
        if "_runner_observation_authority" in request:
            internal_context["_runner_observation_authority"] = request["_runner_observation_authority"]
        result = service.mutate(
            entity_kind,
            entity_name,
            expected_version=expected_version,
            changes=changes,
            writer_role=writer_role,
            event_type=event_type,
            material=bool(request.get("material", True)),
            **internal_context,
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

    # Keep derived role/index state coherent before packing the live Tower.
    # A projection failure never invalidates a canonical CAS mutation.
    if bool(request.get("material", True)):
        try:
            from .views import materialize_role_views

            role_views = materialize_role_views(root)
            receipt["role_view_refresh"] = {"status": "PASS", **role_views}
        except Exception as exc:
            receipt["role_view_refresh"] = {
                "status": "FAILED",
                "error_type": type(exc).__name__,
                "message": str(exc),
            }

    # Every material canonical mutation closes the state loop immediately:
    # canonical files -> stable live Tower -> derived Atlas/public projection.
    # External transport replaces the bytes of the same Drive file ID; this
    # runtime receipt exposes the exact revision/fingerprint to publish/read back.
    if bool(request.get("material", True)):
        live_tower = None
        try:
            from .live_tower import publish_live_tower

            live_tower = publish_live_tower(root)
            receipt["live_tower_refresh"] = live_tower
        except Exception as exc:
            receipt["live_tower_refresh"] = {
                "status": "FAILED",
                "error_type": type(exc).__name__,
                "message": str(exc),
            }

        if live_tower and live_tower.get("status") == "PASS":
            try:
                from datetime import datetime, timezone
                from .public_projection import (
                    build_public_projection,
                    projection_bytes,
                    verify_projection,
                )

                public = build_public_projection(
                    root,
                    tower_revision=str(live_tower["revision"]),
                    tower_file_id=str(live_tower["stable_file_id"]),
                    generated_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                )
                ok, detail = verify_projection(public)
                if not ok:
                    raise RuntimeError("PUBLIC_PROJECTION_VERIFY_FAILED:" + detail)

                destination = root / "projections" / "public" / "latest.json"
                destination.parent.mkdir(parents=True, exist_ok=True)
                temporary = destination.with_name(destination.name + ".tmp")
                temporary.write_bytes(projection_bytes(public))
                temporary.replace(destination)

                receipt["projection_refresh"] = {
                    "status": "PASS",
                    "projection_state": "CURRENT",
                    "path": str(destination),
                    "tower_file_id": live_tower["stable_file_id"],
                    "tower_revision": live_tower["revision"],
                    "projection_fingerprint": public["manifest"]["projection_fingerprint"],
                    "readback": "PASS",
                }
            except Exception as exc:
                receipt["projection_refresh"] = {
                    "status": "FAILED",
                    "projection_state": "PROJECTION_STALE",
                    "tower_file_id": live_tower["stable_file_id"],
                    "tower_revision": live_tower["revision"],
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
