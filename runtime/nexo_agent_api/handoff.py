from __future__ import annotations

import hashlib
import json
import re
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import urlparse
from uuid import uuid4

from .service import TowerAgentIssue
from .tower_paths import entity_path, json_file

RUNTIME_ROLES = {"DAILY", "ADVISOR", "EXECUTOR", "LEARNER", "EMERGENT"}
SEND_ROLES = RUNTIME_ROLES | {"DIRECTOR"}
ACTIONABLE_STATES = {"PENDING", "ACK"}
TERMINAL_STATES = {"DONE", "FAILED"}
TERMINAL_WORK_STATES = {"DONE", "VERIFIED", "REJECTED", "FAILED", "SUPERSEDED"}
INBOX_LIMIT = 5

_SOURCE_LINK_FIELDS = {
    "label",
    "url",
    "access_date",
    "publisher",
    "authors",
    "date",
    "supports",
    "uncertainty",
    "next_test_impact",
}

# Human-facing handoff fields are deliberately separate from canonical IDs/state.
# These tokens already have structured private fields and should not be copied into
# prose intended for a person. Scientific jargon is allowed; internal transport
# jargon is not.
_MACHINE_ONLY_PLAIN_TOKENS = {
    "ACK", "PENDING", "DONE", "FAILED", "READY", "RUNNING", "CHECKPOINTED",
    "CONFIRMED", "REFUTED", "CANONICAL", "BLOCKED", "HIGH", "MEDIUM", "LOW", "UNKNOWN",
    "READBACK", "FINGERPRINT", "PAYLOAD", "HANDOFF", "CANARY",
    "REQUEST_ID", "TOPIC_ID", "ENTITY_REF", "EVIDENCE_REFS", "SOURCE_LINKS",
}
_PRIVATE_REF_RE = re.compile(
    r"\b(?:REQ|HO|INC|TEST|WORK|HYP|LESSON|RM|ART)(?:::|[-:])[A-Z0-9_.:-]+\b",
    re.IGNORECASE,
)
_SNAKE_FIELD_RE = re.compile(
    r"\b(?:request_id|topic_id|entity_ref|evidence_refs|source_links|correlation_id|parent_handoff_id)\b",
    re.IGNORECASE,
)


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
    json_file(event_dir, event_id).write_text(json.dumps(event, ensure_ascii=False, sort_keys=True), encoding="utf-8")
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


def _latest_by_request_id(root: Path) -> dict[str, dict]:
    latest: dict[str, dict] = {}
    for event in _handoff_events(root):
        request_id = str(event.get("request_id") or "")
        if request_id:
            latest[request_id] = event
    return latest


def _required_plain(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise TowerAgentIssue(
            "HANDOFF_PLAIN_FIELD_REQUIRED",
            f"{field} is required and must be non-empty plain text.",
            {"field": field},
        )
    text = " ".join(value.strip().split())
    if _PRIVATE_REF_RE.search(text) or _SNAKE_FIELD_RE.search(text):
        raise TowerAgentIssue(
            "HANDOFF_PLAIN_FIELD_LEAKS_INTERNAL_REF",
            "Human-facing handoff text must explain the meaning without copying internal IDs or field names.",
            {"field": field},
        )
    words = {token.upper() for token in re.findall(r"[A-Za-z_]+", text)}
    leaked = sorted(words.intersection(_MACHINE_ONLY_PLAIN_TOKENS))
    if leaked:
        raise TowerAgentIssue(
            "HANDOFF_PLAIN_FIELD_MACHINE_LANGUAGE",
            "Human-facing handoff text must use ordinary Portuguese instead of internal transport/state jargon.",
            {"field": field, "tokens": leaked},
        )
    return text


def _normalize_evidence_refs(value: object) -> list[dict]:
    if value in (None, []):
        return []
    if not isinstance(value, list):
        raise TowerAgentIssue("HANDOFF_EVIDENCE_REFS_INVALID", "evidence_refs must be a list.", {})
    result = []
    for index, item in enumerate(value):
        if not isinstance(item, dict) or not str(item.get("ref") or "").strip():
            raise TowerAgentIssue(
                "HANDOFF_EVIDENCE_REF_INVALID",
                "Each evidence_refs item must be an object with a canonical ref.",
                {"index": index},
            )
        normalized = {"ref": str(item["ref"]).strip()}
        for key in ("kind", "relation", "note"):
            if item.get(key) not in (None, ""):
                normalized[key] = item[key]
        result.append(normalized)
    return result


def _normalize_source_links(value: object) -> list[dict]:
    if value in (None, []):
        return []
    if not isinstance(value, list):
        raise TowerAgentIssue("HANDOFF_SOURCE_LINKS_INVALID", "source_links must be a list.", {})
    result = []
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            raise TowerAgentIssue("HANDOFF_SOURCE_LINK_INVALID", "Each source link must be an object.", {"index": index})
        label = str(item.get("label") or "").strip()
        url = str(item.get("url") or "").strip()
        access_date = str(item.get("access_date") or "").strip()
        parsed = urlparse(url)
        try:
            date.fromisoformat(access_date)
        except ValueError as exc:
            raise TowerAgentIssue(
                "HANDOFF_SOURCE_ACCESS_DATE_INVALID",
                "source_links access_date must be YYYY-MM-DD.",
                {"index": index, "access_date": access_date},
            ) from exc
        if not label or parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise TowerAgentIssue(
                "HANDOFF_SOURCE_LINK_INVALID",
                "Each source link requires label, http(s) URL and access_date.",
                {"index": index},
            )
        normalized = {key: item[key] for key in _SOURCE_LINK_FIELDS if item.get(key) not in (None, "", [])}
        normalized.update({"label": label, "url": url, "access_date": access_date})
        authors = normalized.get("authors")
        if authors is not None and not isinstance(authors, (str, list)):
            raise TowerAgentIssue(
                "HANDOFF_SOURCE_AUTHORS_INVALID",
                "source_links authors must be a string or list.",
                {"index": index},
            )
        result.append(normalized)
    return result


def _request_fingerprint(payload: dict) -> str:
    blob = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return "sha256:" + hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _work_envelope(self, entity_ref: str) -> dict | None:
    canonical_path = entity_path(self.root, "work", entity_ref)
    if canonical_path.exists():
        try:
            payload = json.loads(canonical_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            payload = None
        if isinstance(payload, dict):
            envelope = dict(payload)
            envelope.setdefault("entity_version", 1)
            return envelope
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


def emit_handoff(
    self,
    *,
    request_id: str,
    from_role: str,
    to_role: str,
    handoff_type: str,
    entity_ref: str,
    thread_id: str,
    summary_plain: str,
    why_it_matters: str,
    next_action: str,
    objective_ref: str | None = None,
    confidence_plain: str | None = None,
    evidence_refs: list[dict] | None = None,
    source_links: list[dict] | None = None,
    correlation_id: str | None = None,
    parent_handoff_id: str | None = None,
) -> dict:
    request_id = str(request_id or "").strip()
    if not request_id:
        raise TowerAgentIssue("HANDOFF_REQUEST_ID_REQUIRED", "request_id is required.", {})
    sender = from_role.upper()
    recipient = to_role.upper()
    if sender not in SEND_ROLES:
        raise TowerAgentIssue("HANDOFF_SENDER_NOT_SUPPORTED", "Unknown handoff sender.", {"from_role": sender})
    if recipient not in RUNTIME_ROLES:
        raise TowerAgentIssue("HANDOFF_RECIPIENT_NOT_SUPPORTED", "Unknown handoff recipient.", {"to_role": recipient})

    immutable = {
        "request_id": request_id,
        "from_role": sender,
        "to_role": recipient,
        "handoff_type": str(handoff_type or "").strip(),
        "entity_ref": str(entity_ref or "").strip(),
        "thread_id": str(thread_id or "").strip(),
        "summary_plain": _required_plain(summary_plain, "summary_plain"),
        "why_it_matters": _required_plain(why_it_matters, "why_it_matters"),
        "next_action": _required_plain(next_action, "next_action"),
        "objective_ref": str(objective_ref).strip() if objective_ref else None,
        "confidence_plain": _required_plain(confidence_plain, "confidence_plain") if confidence_plain else None,
        "evidence_refs": _normalize_evidence_refs(evidence_refs),
        "source_links": _normalize_source_links(source_links),
        "parent_handoff_id": str(parent_handoff_id).strip() if parent_handoff_id else None,
    }
    if not immutable["handoff_type"] or not immutable["entity_ref"] or not immutable["thread_id"]:
        raise TowerAgentIssue(
            "HANDOFF_ROUTE_FIELDS_REQUIRED",
            "handoff_type, entity_ref and thread_id are required.",
            {},
        )

    fingerprint = _request_fingerprint(immutable)
    previous = _latest_by_request_id(self.root).get(request_id)
    if previous:
        if previous.get("request_fingerprint") != fingerprint:
            raise TowerAgentIssue(
                "HANDOFF_REQUEST_ID_CONFLICT",
                "request_id was already used with different handoff content.",
                {"request_id": request_id, "handoff_id": previous.get("handoff_id")},
            )
        return previous

    handoff_id = "HO-" + hashlib.sha256(request_id.encode("utf-8")).hexdigest()[:32]
    envelope = _work_envelope(self, immutable["entity_ref"])
    payload = {
        **immutable,
        "handoff_id": handoff_id,
        "request_fingerprint": fingerprint,
        "correlation_id": correlation_id or handoff_id,
        "entity_path": f"entities/work/{immutable['entity_ref']}.json",
        "entity_version": envelope.get("entity_version") if envelope else None,
        "work_envelope": envelope,
        "hydration_required": envelope is None,
        "state": "PENDING",
        "event_type": "HANDOFF_CREATED",
        "writer_role": sender,
        "material": True,
        "opened_at": _now(),
    }
    return _write_event(self.root, payload)


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
        "handoff_id", "request_id", "request_fingerprint", "correlation_id", "parent_handoff_id",
        "thread_id", "from_role", "to_role", "handoff_type", "objective_ref",
        "entity_ref", "entity_path", "entity_version", "work_envelope", "hydration_required",
        "summary_plain", "why_it_matters", "next_action", "confidence_plain", "evidence_refs",
        "source_links", "opened_at",
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
