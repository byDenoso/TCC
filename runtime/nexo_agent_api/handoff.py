from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from .service import TowerAgentIssue

RUNTIME_ROLES = {"DAILY", "ADVISOR", "EXECUTOR", "LEARNER", "EMERGENT"}
SEND_ROLES = RUNTIME_ROLES | {"DIRECTOR"}
ACTIONABLE_STATES = {"PENDING", "ACK"}
TERMINAL_STATES = {"DONE", "FAILED"}
TERMINAL_WORK_STATES = {"DONE", "VERIFIED", "REJECTED", "FAILED", "SUPERSEDED"}
INBOX_LIMIT = 5


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _write_event(root: Path, payload: dict) -> dict:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    event_id = f"{stamp}-{uuid4().hex[:8]}"
    event = dict(payload)
    event["event_id"] = event_id
    event["created_at"] = _now()
    event_dir = root / "events" / datetime.now(timezone.utc).strftime("%Y-%m-%d")
    event_dir.mkdir(parents=True, exist_ok=True)
    (event_dir / f"{event_id}.json").write_text(json.dumps(event, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    return event


def _handoff_events(root: Path) -> list[dict]:
    event_root = root / "events"
    if not event_root.exists():
        return []
    events = []
    for path in sorted(event_root.rglob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(payload, dict) and payload.get("handoff_id"):
            events.append(payload)
    return events


def _latest_by_handoff(root: Path) -> dict[str, dict]:
    latest: dict[str, dict] = {}
    for event in _handoff_events(root):
        latest[str(event["handoff_id"])] = event
    return latest


def _work_envelope(self, entity_ref: str) -> dict | None:
    for item in self._work_items():
        if str(item.get("id")) == entity_ref:
            envelope = dict(item)
            envelope.setdefault("entity_version", 1)
            return envelope
    return None


def _handoff_is_stale(self, event: dict) -> bool:
    entity_ref = event.get("entity_ref")
    if not entity_ref:
        return False
    current = _work_envelope(self, str(entity_ref))
    if current is None:
        return False
    try:
        event_version = int(event.get("entity_version") or 0)
        current_version = int(current.get("entity_version") or 0)
    except (TypeError, ValueError):
        return False
    if current_version <= event_version:
        return False
    if str(current.get("status", "")).upper() in TERMINAL_WORK_STATES:
        return True
    current_owner = str(current.get("owner_role") or "").upper()
    recipient = str(event.get("to_role") or "").upper()
    return bool(current_owner and recipient and current_owner != recipient)


def emit_handoff(self, *, from_role: str, to_role: str, handoff_type: str, entity_ref: str, thread_id: str, next_action: str, correlation_id: str | None = None) -> dict:
    sender = from_role.upper()
    recipient = to_role.upper()
    if sender not in SEND_ROLES:
        raise TowerAgentIssue("HANDOFF_SENDER_NOT_SUPPORTED", "Unknown handoff sender.", {"from_role": sender})
    if recipient not in RUNTIME_ROLES:
        raise TowerAgentIssue("HANDOFF_RECIPIENT_NOT_SUPPORTED", "Unknown handoff recipient.", {"to_role": recipient})
    handoff_id = f"HO-{uuid4().hex}"
    envelope = _work_envelope(self, entity_ref)
    entity_path = f"entities/work/{entity_ref}.json"
    return _write_event(self.root, {
        "handoff_id": handoff_id,
        "correlation_id": correlation_id or handoff_id,
        "thread_id": thread_id,
        "from_role": sender,
        "to_role": recipient,
        "handoff_type": handoff_type,
        "entity_ref": entity_ref,
        "entity_path": entity_path,
        "entity_version": envelope.get("entity_version") if envelope else None,
        "work_envelope": envelope,
        "hydration_required": envelope is None,
        "state": "PENDING",
        "next_action": next_action,
        "event_type": "HANDOFF_CREATED",
        "writer_role": sender,
        "material": True,
        "opened_at": _now(),
    })


def inbox_for(self, role: str) -> list[dict]:
    recipient = role.upper()
    if recipient not in RUNTIME_ROLES:
        raise TowerAgentIssue("ROLE_NOT_SUPPORTED", "Unknown NEXO role.", {"role": recipient})
    items = [
        event
        for event in _latest_by_handoff(self.root).values()
        if event.get("to_role") == recipient
        and event.get("state") in ACTIONABLE_STATES
        and not _handoff_is_stale(self, event)
    ]
    items.sort(key=lambda item: (str(item.get("opened_at", "")), str(item.get("handoff_id", ""))))
    return items[:INBOX_LIMIT]


def transition_handoff(self, handoff_id: str, *, state: str, writer_role: str) -> dict:
    target = state.upper()
    writer = writer_role.upper()
    if target not in {"ACK", "DONE", "FAILED"}:
        raise TowerAgentIssue("HANDOFF_STATE_NOT_SUPPORTED", "Unsupported handoff state.", {"state": target})
    current = _latest_by_handoff(self.root).get(handoff_id)
    if not current:
        raise TowerAgentIssue("HANDOFF_NOT_FOUND", "Handoff does not exist.", {"handoff_id": handoff_id})
    if writer != current.get("to_role"):
        raise TowerAgentIssue("HANDOFF_WRITER_MISMATCH", "Only the recipient can transition a handoff.", {"writer_role": writer})
    current_state = str(current.get("state", ""))
    if current_state == target:
        return current
    allowed = {"PENDING": {"ACK", "DONE", "FAILED"}, "ACK": {"DONE", "FAILED"}}
    if target not in allowed.get(current_state, set()):
        raise TowerAgentIssue("HANDOFF_ILLEGAL_TRANSITION", "Illegal handoff state transition.", {"from": current_state, "to": target})
    payload = {key: current.get(key) for key in (
        "handoff_id", "correlation_id", "thread_id", "from_role", "to_role", "handoff_type",
        "entity_ref", "entity_path", "entity_version", "work_envelope", "hydration_required",
        "next_action", "opened_at",
    )}
    payload.update({"state": target, "event_type": f"HANDOFF_{target}", "writer_role": writer, "material": True})
    return _write_event(self.root, payload)


def install_handoff_protocol(agent_service_cls) -> None:
    if getattr(agent_service_cls, "_handoff_protocol_installed", False):
        return
    original_bootstrap = agent_service_cls.bootstrap

    def bootstrap(self, role: str) -> dict:
        payload = original_bootstrap(self, role)
        inbox = self.inbox_for(role)
        payload["inbox"] = inbox
        payload["inbox_count"] = len(inbox)
        payload["inbox_limit"] = INBOX_LIMIT
        return payload

    agent_service_cls.emit_handoff = emit_handoff
    agent_service_cls.inbox_for = inbox_for
    agent_service_cls.transition_handoff = transition_handoff
    agent_service_cls.bootstrap = bootstrap
    agent_service_cls._handoff_protocol_installed = True
