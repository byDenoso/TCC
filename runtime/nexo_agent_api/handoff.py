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
READ_ONLY_ROLES = {"REFEREE_1", "REFUTADOR"}
HANDOFF_READ_ROLES = RUNTIME_ROLES | READ_ONLY_ROLES
SEND_ROLES = RUNTIME_ROLES | {"DIRECTOR"}
ACTIONABLE_STATES = {"PENDING", "ACK"}
TERMINAL_STATES = {"DONE", "FAILED"}
TERMINAL_WORK_STATES = {"DONE", "VERIFIED", "REJECTED", "FAILED", "SUPERSEDED"}
INBOX_LIMIT = 5
RECOVERY_HANDOFF = "BLOCKER_RECOVERY"
RECOVERY_POLICY = "EXECUTION_RECOVERY_V1"
RECOVERY_COMPLETE_STATES = {"DONE", "VERIFIED", "COMPLETED", "CLOSED_VERIFIED"}

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
    now = datetime.now(timezone.utc)
    stamp = now.strftime("%Y%m%dT%H%M%S%fZ")
    event_dir = root / "events" / now.strftime("%Y-%m-%d")
    event_dir.mkdir(parents=True, exist_ok=True)
    sequence = 1
    for path in event_dir.glob(f"{stamp}-z*-*.json"):
        match = re.match(re.escape(stamp) + r"-z(\d{8})-", path.name)
        if match:
            sequence = max(sequence, int(match.group(1)) + 1)
    # Legacy IDs use a random lower-case hex suffix. The z marker sorts after those IDs,
    # while the fixed-width sequence preserves causal order under a frozen clock.
    event_id = f"{stamp}-z{sequence:08d}-{uuid4().hex[:8]}"
    event = dict(payload)
    event["event_id"] = event_id
    event["created_at"] = now.isoformat().replace("+00:00", "Z")
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


def _recovery_work(self, entity_ref: str) -> dict:
    """Recovery ownership is bound to an existing canonical WORK, never an index."""
    if not re.fullmatch(r"[A-Za-z0-9_.:-]+", entity_ref):
        raise TowerAgentIssue("HANDOFF_RECOVERY_WORK_REQUIRED", "A canonical recovery WORK is required.")
    path = entity_path(self.root, "work", entity_ref)
    try:
        work = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise TowerAgentIssue("HANDOFF_RECOVERY_WORK_REQUIRED", "A canonical recovery WORK is required.") from exc
    recovery = work.get("recovery") if isinstance(work, dict) else None
    if (not isinstance(work, dict) or work.get("id") != entity_ref
            or work.get("kind") != "DEPENDENCY_RECOVERY" or not work.get("test_id")
            or not isinstance(recovery, dict) or recovery.get("policy") != RECOVERY_POLICY
            or not recovery.get("fingerprint")):
        raise TowerAgentIssue("HANDOFF_RECOVERY_CONTRACT_INVALID", "The recovery WORK has no current recovery contract.")
    return work


def _recovery_context(self, event: dict) -> tuple[dict, dict | None]:
    work = _recovery_work(self, str(event.get("entity_ref") or ""))
    recovery = work["recovery"]
    if (recovery.get("fingerprint") != event.get("recovery_fingerprint")
            or recovery.get("target_role") != event.get("to_role")
            or recovery.get("route_generation") != ((event.get("work_envelope") or {}).get("recovery") or {}).get("route_generation")
            or work.get("test_id") != (event.get("work_envelope") or {}).get("test_id")):
        raise TowerAgentIssue("HANDOFF_RECOVERY_CONTRACT_CHANGED", "The recovery route changed after this handoff.")
    source = recovery.get("acceptance_source")
    accepted = (isinstance(source, dict) and source.get("handoff_id") == event.get("handoff_id")
                and source.get("request_id") == event.get("request_id")
                and source.get("from_role") == event.get("from_role")
                and source.get("to_role") == event.get("to_role")
                and recovery.get("ownership_state") == "ACCEPTED")
    expected_owner = event.get("to_role") if accepted else event.get("from_role")
    if str(work.get("owner_role") or "").upper() != expected_owner:
        raise TowerAgentIssue("HANDOFF_RECOVERY_OWNER_CHANGED", "The canonical owner no longer matches this recovery route.")
    if event.get("state") in {"ACK", "DONE"} and not accepted:
        raise TowerAgentIssue("HANDOFF_RECOVERY_ACCEPTANCE_MISSING", "The canonical recovery acceptance is missing.")
    return work, source if accepted else None


def _recovery_completion(self, work: dict) -> dict:
    if str(work.get("status") or "").upper() not in RECOVERY_COMPLETE_STATES:
        raise TowerAgentIssue("HANDOFF_RECOVERY_WORK_NOT_COMPLETE", "The recovery WORK is not complete.")
    test_id = str(work.get("test_id") or "")
    if not re.fullmatch(r"[A-Za-z0-9_.:-]+", test_id):
        raise TowerAgentIssue("HANDOFF_RECOVERY_EVIDENCE_REQUIRED", "The recovery TEST reference is invalid.")
    from . import scientific_integrity as integrity
    from .execution_recovery import evaluate_readiness

    try:
        test = integrity.entity(self.root, test_id)
        validation = evaluate_readiness(self.root, test, ignore_reservation=True) if test else {}
    except (OSError, ValueError, TypeError) as exc:
        raise TowerAgentIssue("HANDOFF_RECOVERY_EVIDENCE_REQUIRED", "Recovery evidence could not be validated.") from exc
    if validation.get("eligible") is not True:
        raise TowerAgentIssue("HANDOFF_RECOVERY_EVIDENCE_REQUIRED", "The recovery TEST is not currently eligible.",
                              {"test_id": test_id, "validation": validation})
    return {"test_id": test_id, "test_version": test.get("entity_version"), "validation": validation}


def _handoff_is_stale(self, event: dict) -> bool:
    if event.get("handoff_type") == RECOVERY_HANDOFF:
        try:
            _recovery_context(self, event)
        except TowerAgentIssue:
            return True
        # A completed recovery still needs its accepted recipient to close the
        # handoff after checking the current TEST evidence.
        return False
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
    if immutable["handoff_type"] == RECOVERY_HANDOFF:
        envelope = _recovery_work(self, immutable["entity_ref"])
        if str(envelope.get("owner_role") or "").upper() != sender:
            raise TowerAgentIssue("HANDOFF_RECOVERY_SENDER_NOT_OWNER", "Only the canonical owner may offer recovery ownership.")
        if envelope["recovery"].get("target_role") != recipient:
            raise TowerAgentIssue("HANDOFF_RECOVERY_TARGET_MISMATCH", "The recipient must match the current recovery route.")
        if str(envelope.get("status") or "").upper() in TERMINAL_WORK_STATES | RECOVERY_COMPLETE_STATES:
            raise TowerAgentIssue("HANDOFF_RECOVERY_WORK_TERMINAL", "Terminal recovery WORK cannot be reassigned.")
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
    if immutable["handoff_type"] == RECOVERY_HANDOFF:
        payload["recovery_fingerprint"] = envelope["recovery"]["fingerprint"]
    return _write_event(self.root, payload)


def inbox_for(self, role: str) -> list[dict]:
    recipient = role.upper()
    if recipient not in HANDOFF_READ_ROLES:
        raise TowerAgentIssue("ROLE_NOT_SUPPORTED", "Unknown NEXO role.", {"role": recipient})
    items = [
        event
        for event in _latest_by_handoff(self.root).values()
        if event.get("to_role") == recipient
        and event.get("state") in ACTIONABLE_STATES
        and not _handoff_is_stale(self, event)
    ]
    items.sort(key=lambda item: (str(item.get("opened_at", "")), str(item.get("handoff_id", ""))))
    # The five-card limit belongs to the bootstrap projection. Applying it to
    # the operational reader lets old ACKs permanently hide newer offers.
    return items


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
    recovery_work, acceptance = (None, None)
    if current.get("handoff_type") == RECOVERY_HANDOFF:
        recovery_work, acceptance = _recovery_context(self, current)
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
    if recovery_work is not None:
        if target == "DONE" and (current_state != "ACK" or acceptance is None):
            raise TowerAgentIssue("HANDOFF_RECOVERY_ACK_REQUIRED", "Recovery ownership must be accepted before completion.")
        if target == "ACK" and acceptance is None:
            if str(recovery_work.get("status") or "").upper() in TERMINAL_WORK_STATES | RECOVERY_COMPLETE_STATES:
                raise TowerAgentIssue("HANDOFF_RECOVERY_WORK_TERMINAL", "Terminal recovery WORK cannot be accepted.")
            acceptance = {"handoff_id": handoff_id, "request_id": current["request_id"],
                          "from_role": current["from_role"], "to_role": writer,
                          "accepted_at": _now(), "source_entity_version": recovery_work["entity_version"]}
            changes = {"owner_role": writer, "recovery": {**recovery_work["recovery"],
                       "ownership_state": "ACCEPTED", "acceptance_source": acceptance}}
            receipt = self.mutate("work", current["entity_ref"], expected_version=recovery_work["entity_version"],
                                  changes=changes, writer_role=writer, event_type="BLOCKER_RECOVERY_ACCEPTED")
            if not receipt.get("accepted") or receipt.get("readback") != "PASS":
                raise TowerAgentIssue("READBACK_FAILED", "Recovery acceptance mutation was not confirmed.")
            recovery_work, recorded_acceptance = _recovery_context(self, current)
            if recorded_acceptance != acceptance:
                raise TowerAgentIssue("READBACK_FAILED", "Recovery acceptance readback did not match.")
        if target == "DONE":
            payload["completion_evidence"] = _recovery_completion(self, recovery_work)
        if target == "FAILED":
            payload["route_failure"] = {"owner_role": recovery_work["owner_role"],
                                        "failed_by": writer, "failed_at": _now(),
                                        "accepted": acceptance is not None}
        payload.update({"recovery_fingerprint": current["recovery_fingerprint"],
                        "acceptance_source": acceptance, "entity_version": recovery_work["entity_version"],
                        "work_envelope": recovery_work, "hydration_required": False})
    payload.update({"state": target, "event_type": f"HANDOFF_{target}", "writer_role": writer, "material": True})
    return _write_event(self.root, payload)


def install_handoff_protocol(agent_service_cls) -> None:
    if getattr(agent_service_cls, "_handoff_protocol_installed", False):
        return
    original_bootstrap = agent_service_cls.bootstrap

    def bootstrap(self, role: str) -> dict:
        payload = original_bootstrap(self, role)
        inbox = self.inbox_for(role)
        payload["inbox"] = inbox[:INBOX_LIMIT]
        payload["inbox_count"] = len(inbox)
        payload["inbox_limit"] = INBOX_LIMIT
        payload["inbox_has_more"] = len(inbox) > INBOX_LIMIT
        return payload

    agent_service_cls.emit_handoff = emit_handoff
    agent_service_cls.inbox_for = inbox_for
    agent_service_cls.transition_handoff = transition_handoff
    agent_service_cls.bootstrap = bootstrap
    agent_service_cls._handoff_protocol_installed = True
