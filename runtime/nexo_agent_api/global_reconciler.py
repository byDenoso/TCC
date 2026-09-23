from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from .mutations import apply_mutation_request
from .service import AgentService
from .tower_paths import entity_path

_VERIFIED_READBACK_STATES = {"PASS", "SUCCESS", "VERIFIED"}
_TERMINAL_WORK_STATES = {"DONE", "VERIFIED", "CLOSED", "CLOSED_VERIFIED"}
_RESUMABLE_STATES = {"READY", "RUNNING", "CHECKPOINTED"}


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None
    return value if isinstance(value, dict) else None


def _status(entity: dict[str, Any]) -> str:
    return str(entity.get("operational_status") or entity.get("status") or "").upper()


def _now(value: str | None = None) -> str:
    if value:
        return value
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _request_id(prefix: str, *parts: str) -> str:
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:20].upper()
    return f"{prefix}-{digest}"


def validate_terminal_render_readback(
    work: dict[str, Any],
    readback: dict[str, Any],
) -> dict[str, Any]:
    """Validate proof that a deployed/public artifact actually rendered."""
    state = str(readback.get("status") or "").upper()
    if state not in _VERIFIED_READBACK_STATES:
        raise ValueError("TERMINAL_READBACK_NOT_PASS")

    if readback.get("rendered") is not True:
        raise ValueError("TERMINAL_READBACK_RENDER_NOT_PROVEN")

    try:
        http_status = int(readback.get("http_status"))
    except (TypeError, ValueError) as exc:
        raise ValueError("TERMINAL_READBACK_HTTP_STATUS_INVALID") from exc
    if not 200 <= http_status < 300:
        raise ValueError("TERMINAL_READBACK_HTTP_NOT_SUCCESS")

    url = str(readback.get("url") or "").strip()
    if not url.startswith(("https://", "http://")):
        raise ValueError("TERMINAL_READBACK_URL_REQUIRED")

    marker = str(readback.get("render_marker") or "").strip()
    if not marker:
        raise ValueError("TERMINAL_READBACK_RENDER_MARKER_REQUIRED")

    expected_revision = str(
        work.get("expected_deploy_revision")
        or work.get("expected_revision")
        or ""
    ).strip()
    observed_revision = str(
        readback.get("observed_revision")
        or readback.get("revision")
        or readback.get("commit")
        or ""
    ).strip()
    if expected_revision and observed_revision != expected_revision:
        raise ValueError("TERMINAL_READBACK_REVISION_MISMATCH")

    expected_fingerprint = str(
        work.get("expected_projection_fingerprint")
        or work.get("projection_fingerprint")
        or ""
    ).strip()
    observed_fingerprint = str(readback.get("projection_fingerprint") or "").strip()
    if expected_fingerprint and observed_fingerprint != expected_fingerprint:
        raise ValueError("TERMINAL_READBACK_FINGERPRINT_MISMATCH")

    return {
        "status": "PASS",
        "rendered": True,
        "http_status": http_status,
        "url": url,
        "render_marker": marker,
        "observed_revision": observed_revision or None,
        "projection_fingerprint": observed_fingerprint or None,
        "readback_ref": str(readback.get("readback_ref") or "").strip() or None,
    }


def _next_executor_work(
    root: Path,
    *,
    exclude_work_id: str,
    allowed_domains: Iterable[str] | None,
) -> dict[str, Any] | None:
    """Choose continuation from canonical WORK state, not capability projection.

    SELECT_NEXT decides ownership/continuation. Capability resolution belongs to
    the executor after selection; using queue_for(EXECUTOR) here can incorrectly
    hide valid READY work whose capability is materialized lazily.
    """
    allowed = {str(value).upper() for value in (allowed_domains or []) if str(value).strip()}
    service = AgentService(root)
    priority_rank = {"P0": 0, "CRITICAL": 0, "HIGH": 1, "P1": 1, "MEDIUM": 2, "P2": 2, "LOW": 3, "P3": 3}
    state_rank = {"RUNNING": 0, "CHECKPOINTED": 1, "READY": 2}
    candidates: list[dict[str, Any]] = []
    for item in service._work_items():
        if str(item.get("id")) == exclude_work_id:
            continue
        if str(item.get("owner_role") or "").upper() != "EXECUTOR":
            continue
        state = _status(item)
        if state not in _RESUMABLE_STATES:
            continue
        if service._has_legitimate_blocker(item):
            continue
        if str(item.get("execution_policy") or "AUTO").upper() == "MANUAL":
            continue
        domain = str(item.get("target_domain") or item.get("domain") or "").upper()
        if allowed and domain not in allowed:
            continue
        candidates.append(item)
    candidates.sort(key=lambda item: (
        state_rank.get(_status(item), 9),
        priority_rank.get(str(item.get("priority") or "MEDIUM").upper(), 9),
        str(item.get("id") or ""),
    ))
    return candidates[0] if candidates else None


def _select_and_start_next(
    root: Path,
    *,
    closed_work_id: str,
    allowed_domains: Iterable[str] | None,
    now: str,
) -> dict[str, Any]:
    candidate = _next_executor_work(
        root,
        exclude_work_id=closed_work_id,
        allowed_domains=allowed_domains,
    )
    if candidate is None:
        return {"action": "NO_OP", "reason": "NO_EXECUTOR_ELIGIBLE_WORK"}

    work_id = str(candidate["id"])
    state = _status(candidate)
    if state != "READY":
        return {
            "action": "SELECT_NEXT",
            "work_id": work_id,
            "state": state,
            "started": state == "RUNNING",
            "resume": state == "CHECKPOINTED",
        }

    receipt = apply_mutation_request(root, {
        "request_id": _request_id("SELECT-NEXT", closed_work_id, work_id),
        "entity_kind": "work",
        "entity_name": work_id,
        "expected_version": int(candidate.get("entity_version") or 1),
        "changes": {
            "status": "RUNNING",
            "operational_status": "RUNNING",
            "selection_state": "SELECT_NEXT",
            "selected_after": closed_work_id,
            "selected_at": now,
        },
        "writer_role": "EXECUTOR",
        "event_type": "WORK_SELECTED_NEXT",
    })
    if not receipt.get("accepted") or receipt.get("readback") != "PASS":
        return {
            "action": "SELECT_NEXT_FAILED",
            "work_id": work_id,
            "receipt": receipt,
        }

    return {
        "action": "SELECT_NEXT",
        "work_id": work_id,
        "state": "RUNNING",
        "started": True,
        "resume": False,
        "receipt": receipt,
    }


def reconcile_verified_work(
    root: str | Path,
    *,
    work_id: str,
    readback: dict[str, Any],
    allowed_domains: Iterable[str] | None = None,
    now: str | None = None,
) -> dict[str, Any]:
    """Close VERIFY_PENDING after render proof, persist CLOSED_VERIFIED, then select next."""
    root = Path(root)
    path = entity_path(root, "work", work_id)
    work = _read_json(path)
    if work is None:
        raise ValueError("WORK_NOT_FOUND")

    timestamp = _now(now)
    if str(work.get("closure_state") or "").upper() == "CLOSED_VERIFIED":
        continuation = _select_and_start_next(
            root,
            closed_work_id=work_id,
            allowed_domains=allowed_domains,
            now=timestamp,
        )
        return {
            "outcome": "CLOSED_VERIFIED",
            "work_id": work_id,
            "replay": True,
            "continuation": continuation,
        }

    state = _status(work)
    verification_state = str(work.get("verification_status") or "").upper()
    if state != "VERIFY_PENDING" and verification_state != "VERIFY_PENDING":
        raise ValueError("WORK_NOT_VERIFY_PENDING")

    proof = validate_terminal_render_readback(work, readback)
    receipt = apply_mutation_request(root, {
        "request_id": _request_id(
            "CLOSE-VERIFIED",
            work_id,
            str(proof.get("observed_revision") or ""),
            str(proof.get("projection_fingerprint") or ""),
            proof["url"],
            proof["render_marker"],
        ),
        "entity_kind": "work",
        "entity_name": work_id,
        "expected_version": int(work.get("entity_version") or 1),
        "changes": {
            "status": "DONE",
            "operational_status": "DONE",
            "closure_state": "CLOSED_VERIFIED",
            "verification_status": "PASS",
            "terminal_readback": proof,
            "closed_at": timestamp,
        },
        "writer_role": "EXECUTOR",
        "event_type": "WORK_CLOSED_VERIFIED",
    })
    if not receipt.get("accepted") or receipt.get("readback") != "PASS":
        return {
            "outcome": "VERIFY_PENDING",
            "work_id": work_id,
            "replay": False,
            "receipt": receipt,
            "continuation": {"action": "NO_OP", "reason": "CLOSURE_PERSIST_FAILED"},
        }

    persisted = _read_json(path) or {}
    if (
        _status(persisted) not in _TERMINAL_WORK_STATES
        or str(persisted.get("closure_state") or "").upper() != "CLOSED_VERIFIED"
        or str(persisted.get("verification_status") or "").upper() != "PASS"
    ):
        raise RuntimeError("CLOSED_VERIFIED_READBACK_MISMATCH")

    continuation = _select_and_start_next(
        root,
        closed_work_id=work_id,
        allowed_domains=allowed_domains,
        now=timestamp,
    )
    return {
        "outcome": "CLOSED_VERIFIED",
        "work_id": work_id,
        "replay": False,
        "receipt": receipt,
        "continuation": continuation,
    }
