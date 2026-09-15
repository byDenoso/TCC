from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from .service import TowerAgentIssue

TERMINAL_WORK_STATES = {"DONE", "VERIFIED", "REJECTED", "FAILED", "SUPERSEDED"}
MAX_REQUEST_REFS = 20


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _norm(value: str | None) -> str:
    return " ".join(str(value or "").strip().split()).lower()


def _compact_list(values: list[str] | None) -> list[str]:
    result: list[str] = []
    for value in values or []:
        clean = " ".join(str(value).strip().split())
        if clean and clean not in result:
            result.append(clean[:500])
    return result[:MAX_REQUEST_REFS]


def _fingerprint(*, action: str, subject: str, scope: str, domain: str, target_work_id: str | None) -> str:
    material = {
        "action": _norm(action),
        "subject": _norm(subject),
        "scope": _norm(scope),
        "domain": _norm(domain),
        "target_work_id": _norm(target_work_id),
    }
    blob = json.dumps(material, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _write_event(root: Path, *, event_type: str, work_id: str, entity_version: int, request_fingerprint: str, thread_id: str, correlation_id: str, outcome: str) -> dict:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    event_id = f"{stamp}-{uuid4().hex[:8]}"
    event = {
        "event_id": event_id,
        "event_type": event_type,
        "entity_kind": "work",
        "entity_name": work_id,
        "entity_version": entity_version,
        "request_fingerprint": request_fingerprint,
        "thread_id": thread_id,
        "correlation_id": correlation_id,
        "outcome": outcome,
        "writer_role": "DIRECTOR",
        "material": True,
        "created_at": _now(),
    }
    event_dir = root / "events" / datetime.now(timezone.utc).strftime("%Y-%m-%d")
    event_dir.mkdir(parents=True, exist_ok=True)
    (event_dir / f"{event_id}.json").write_text(json.dumps(event, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    return event


def _summary(*, action: str, subject: str, scope: str, constraints: list[str], acceptance: list[str]) -> dict:
    return {
        "action": " ".join(action.strip().split())[:120],
        "subject": " ".join(subject.strip().split())[:300],
        "scope": " ".join(scope.strip().split())[:500],
        "constraints": constraints,
        "acceptance": acceptance,
    }


def _append_unique_bounded(existing: list[str] | None, value: str) -> list[str]:
    items = [str(item) for item in (existing or []) if str(item)]
    if value in items:
        items.remove(value)
    items.append(value)
    return items[-MAX_REQUEST_REFS:]


def _append_ref_bounded(existing: list[dict] | None, ref: dict) -> list[dict]:
    items = [item for item in (existing or []) if isinstance(item, dict)]
    items.append(ref)
    return items[-MAX_REQUEST_REFS:]


def _work_path(root: Path, work_id: str) -> Path:
    return root / "entities" / "work" / f"{work_id}.json"


def _read_work(root: Path, work_id: str) -> dict | None:
    path = _work_path(root, work_id)
    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else None


def _merge_request(self, work: dict, *, thread_id: str, correlation_id: str, request_fingerprint: str, request_summary: dict, constraints: list[str], acceptance: list[str], priority: str) -> dict:
    work_id = str(work.get("id") or work.get("work_id"))
    status = str(work.get("status", "")).upper()
    if status in TERMINAL_WORK_STATES:
        event = _write_event(
            self.root,
            event_type="REQUEST_TERMINAL_MATCH",
            work_id=work_id,
            entity_version=int(work.get("entity_version", 1)),
            request_fingerprint=request_fingerprint,
            thread_id=thread_id,
            correlation_id=correlation_id,
            outcome="TERMINAL_MATCH",
        )
        readback = _read_work(self.root, work_id)
        if not readback or str(readback.get("status", "")).upper() != status:
            raise TowerAgentIssue("READBACK_FAILED", "Terminal request match readback failed.", {"work_id": work_id})
        return {
            "admitted": True,
            "outcome": "TERMINAL_MATCH",
            "work_id": work_id,
            "request_fingerprint": request_fingerprint,
            "readback": "PASS",
            "event_id": event["event_id"],
        }

    observed_at = _now()
    request_ref = {
        "thread_id": thread_id,
        "correlation_id": correlation_id,
        "observed_at": observed_at,
        "fingerprint": request_fingerprint,
    }
    changes = {
        "thread_id": thread_id,
        "last_request": request_summary,
        "last_request_fingerprint": request_fingerprint,
        "last_request_at": observed_at,
        "request_count": int(work.get("request_count", 0)) + 1,
        "request_refs": _append_ref_bounded(work.get("request_refs"), request_ref),
        "source_threads": _append_unique_bounded(work.get("source_threads"), thread_id),
        "request_fingerprints": _append_unique_bounded(work.get("request_fingerprints"), request_fingerprint),
        "constraints": _compact_list(list(work.get("constraints", [])) + constraints),
        "acceptance": _compact_list(list(work.get("acceptance", [])) + acceptance),
        "priority": priority,
    }
    result = self.mutate(
        "work",
        work_id,
        expected_version=int(work.get("entity_version", 1)),
        changes=changes,
        writer_role="DIRECTOR",
        event_type="REQUEST_MERGED",
    )
    readback = _read_work(self.root, work_id)
    if not readback or readback.get("last_request_fingerprint") != request_fingerprint:
        raise TowerAgentIssue("READBACK_FAILED", "Merged request readback failed.", {"work_id": work_id})
    return {
        "admitted": True,
        "outcome": "MERGED",
        "work_id": work_id,
        "request_fingerprint": request_fingerprint,
        "readback": result["readback"],
        "event_id": result["event_id"],
    }


def ingest_request(
    self,
    *,
    thread_id: str,
    action: str,
    subject: str,
    domain: str,
    owner_role: str,
    scope: str = "",
    constraints: list[str] | None = None,
    acceptance: list[str] | None = None,
    priority: str = "NORMAL",
    correlation_id: str | None = None,
    target_work_id: str | None = None,
    actionable: bool = True,
) -> dict:
    if not actionable:
        return {"admitted": False, "outcome": "REJECTED_NON_ACTIONABLE", "readback": "NOT_APPLICABLE"}

    clean_thread = " ".join(str(thread_id).strip().split())
    clean_action = " ".join(str(action).strip().split())
    clean_subject = " ".join(str(subject).strip().split())
    clean_domain = " ".join(str(domain).strip().split()).upper()
    clean_owner = " ".join(str(owner_role).strip().split()).upper()
    clean_scope = " ".join(str(scope).strip().split())
    if not all((clean_thread, clean_action, clean_subject, clean_domain, clean_owner)):
        raise TowerAgentIssue("REQUEST_INGRESS_INVALID", "Actionable request is missing a required compact intent field.")
    if clean_owner not in self.ROLES:
        raise TowerAgentIssue("REQUEST_OWNER_NOT_SUPPORTED", "Request owner role is not supported.", {"owner_role": clean_owner})

    clean_constraints = _compact_list(constraints)
    clean_acceptance = _compact_list(acceptance)
    clean_priority = " ".join(str(priority).strip().split()).upper() or "NORMAL"
    clean_target = " ".join(str(target_work_id or "").strip().split()) or None
    corr = " ".join(str(correlation_id or f"REQ-{uuid4().hex}").strip().split())
    request_fingerprint = _fingerprint(
        action=clean_action,
        subject=clean_subject,
        scope=clean_scope,
        domain=clean_domain,
        target_work_id=clean_target,
    )
    request_summary = _summary(
        action=clean_action,
        subject=clean_subject,
        scope=clean_scope,
        constraints=clean_constraints,
        acceptance=clean_acceptance,
    )

    items = self._work_items()
    if clean_target:
        target = next((item for item in items if str(item.get("id") or item.get("work_id")) == clean_target), None)
        if target is None:
            target = _read_work(self.root, clean_target)
        if target is None:
            raise TowerAgentIssue("TARGET_WORK_NOT_FOUND", "Explicit target WORK does not exist.", {"target_work_id": clean_target})
        return _merge_request(
            self,
            target,
            thread_id=clean_thread,
            correlation_id=corr,
            request_fingerprint=request_fingerprint,
            request_summary=request_summary,
            constraints=clean_constraints,
            acceptance=clean_acceptance,
            priority=clean_priority,
        )

    duplicate = next((item for item in items if item.get("request_fingerprint") == request_fingerprint), None)
    if duplicate is not None:
        return _merge_request(
            self,
            duplicate,
            thread_id=clean_thread,
            correlation_id=corr,
            request_fingerprint=request_fingerprint,
            request_summary=request_summary,
            constraints=clean_constraints,
            acceptance=clean_acceptance,
            priority=clean_priority,
        )

    work_id = f"WORK::REQ::{request_fingerprint[:16]}"
    existing = _read_work(self.root, work_id)
    if existing is not None:
        return _merge_request(
            self,
            existing,
            thread_id=clean_thread,
            correlation_id=corr,
            request_fingerprint=request_fingerprint,
            request_summary=request_summary,
            constraints=clean_constraints,
            acceptance=clean_acceptance,
            priority=clean_priority,
        )

    observed_at = _now()
    request_ref = {
        "thread_id": clean_thread,
        "correlation_id": corr,
        "observed_at": observed_at,
        "fingerprint": request_fingerprint,
    }
    work = {
        "id": work_id,
        "entity_version": 1,
        "status": "READY",
        "kind": "ACTION",
        "owner_role": clean_owner,
        "domain": clean_domain,
        "priority": clean_priority,
        "question": clean_subject,
        "next_action": f"{clean_action}: {clean_subject}",
        "thread_id": clean_thread,
        "request_fingerprint": request_fingerprint,
        "request_fingerprints": [request_fingerprint],
        "request_count": 1,
        "request_refs": [request_ref],
        "source_threads": [clean_thread],
        "first_request_at": observed_at,
        "last_request_at": observed_at,
        "last_request": request_summary,
        "last_request_fingerprint": request_fingerprint,
        "constraints": clean_constraints,
        "acceptance": clean_acceptance,
        "writer_role": "DIRECTOR",
    }
    path = _work_path(self.root, work_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("x", encoding="utf-8") as handle:
            json.dump(work, handle, ensure_ascii=False, sort_keys=True)
    except FileExistsError:
        existing = _read_work(self.root, work_id)
        if existing is None:
            raise TowerAgentIssue("WRITE_CONFLICT_RETRY_REQUIRED", "WORK appeared concurrently but could not be read back.")
        return _merge_request(
            self,
            existing,
            thread_id=clean_thread,
            correlation_id=corr,
            request_fingerprint=request_fingerprint,
            request_summary=request_summary,
            constraints=clean_constraints,
            acceptance=clean_acceptance,
            priority=clean_priority,
        )

    readback = _read_work(self.root, work_id)
    if not readback or readback.get("request_fingerprint") != request_fingerprint:
        raise TowerAgentIssue("READBACK_FAILED", "Created request WORK readback failed.", {"work_id": work_id})
    event = _write_event(
        self.root,
        event_type="REQUEST_INGESTED",
        work_id=work_id,
        entity_version=1,
        request_fingerprint=request_fingerprint,
        thread_id=clean_thread,
        correlation_id=corr,
        outcome="CREATED",
    )
    return {
        "admitted": True,
        "outcome": "CREATED",
        "work_id": work_id,
        "request_fingerprint": request_fingerprint,
        "readback": "PASS",
        "event_id": event["event_id"],
    }


def install_request_ingress_protocol(agent_service_cls) -> None:
    if getattr(agent_service_cls, "_request_ingress_protocol_installed", False):
        return
    agent_service_cls.ingest_request = ingest_request
    agent_service_cls._request_ingress_protocol_installed = True
