"""Validated private Sheet ingress for the existing single Tower Writer.

The GitHub Actions Writer is the ONLY caller that may assert provenance from
NEXO_SCHEDULED_SPOOL (pinned owner/Writer Drive ACL). It constructs a runner-local
file from the authenticated Sheet export. This module does not authenticate,
write a Tower, discover credentials or relax an existing human gate.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any

CONTRACT = "NEXO_PRIVATE_SCHEDULED_SPOOL_V2"
_MAX_ENVELOPE_BYTES = 24576
_SPOOL_ID = re.compile(r"^sched-v2-[a-z0-9-]{1,51}$")
_RUNTIME_ROLES = frozenset({
    "PITIA", "LEARNER", "EXECUTOR", "ADVISOR", "ENGINEER",
    "REFEREE_1", "REFUTADOR", "GUARDIAO", "SENTINEL",
    "DAILY", "EMERGENT", "CONVERSA",
})
# Existing governed proposal types only. All require the original Writer checks.
# Human approvals, credential operations, autonomous mandates and raw runner
# observations intentionally cannot enter via this unattended transport.
_ALLOWED_KINDS = frozenset({
    "BOARD_POST", "INTEGRITY_REPORT", "LEARNING_SIGNAL",
    "HANDOFF", "HANDOFF_TRANSITION",
    "HYPOTHESIS_PROPOSAL", "LESSON_PROPOSAL", "SEMANTIC_BACKFILL",
    "DATA_BINDING", "RECIPE_BIND", "ROADMAP_ATTACH",
    "ROADMAP_CHARTER", "FAMILY_CHARTER",
    "MUTATION_PROPOSAL", "CONTEST", "VERDICT_REVIEW",
    "TEST_BATTERY", "FITNESS_REPORT", "NEXO_THOUGHT",
})
_HANDOFF_ROLES = frozenset({"LEARNER", "ADVISOR", "EXECUTOR", "DAILY", "EMERGENT"})


class PrivateSpoolError(ValueError):
    """Invalid or conflicting private ingress. No Tower mutation occurred."""


def _runtime_role(value: Any) -> str:
    role = str(value or "").strip().upper()
    return "ADVISOR" if role == "ENGINEER" else role


def _actor_matches(envelope: dict, field: str, wrapper: str) -> bool:
    payload = envelope["payload"]
    body = payload.get(wrapper) if isinstance(payload.get(wrapper), dict) else payload
    return isinstance(body.get(field), str) and _runtime_role(body[field]) == _runtime_role(envelope["source"])


def _validate_envelope(envelope: Any) -> None:
    if not isinstance(envelope, dict) or set(envelope) != {
        "kind", "source", "created_at", "intent_id", "payload",
    }:
        raise PrivateSpoolError("PRIVATE_SPOOL_ENVELOPE_FIELDS_INVALID")
    kind, source = envelope["kind"], envelope["source"]
    if not isinstance(kind, str) or kind not in _ALLOWED_KINDS:
        raise PrivateSpoolError("PRIVATE_SPOOL_KIND_NOT_ALLOWED")
    if not isinstance(source, str) or source not in _RUNTIME_ROLES:
        raise PrivateSpoolError("PRIVATE_SPOOL_ROLE_NOT_ALLOWED")
    if not isinstance(envelope["payload"], dict):
        raise PrivateSpoolError("PRIVATE_SPOOL_PAYLOAD_INVALID")
    identity = envelope["intent_id"]
    if not isinstance(identity, str) or not identity or len(identity) > 160 or identity != identity.strip():
        raise PrivateSpoolError("PRIVATE_SPOOL_INTENT_INVALID")
    ts = envelope["created_at"]
    if not isinstance(ts, str) or not ts.endswith(("Z", "+00:00")):
        raise PrivateSpoolError("PRIVATE_SPOOL_TIMESTAMP_INVALID")
    try:
        when = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        if when.tzinfo is None or when.utcoffset() != timezone.utc.utcoffset(when):
            raise ValueError("not UTC")
    except ValueError:
        raise PrivateSpoolError("PRIVATE_SPOOL_TIMESTAMP_INVALID") from None
    if kind in {"HANDOFF", "HANDOFF_TRANSITION"}:
        if _runtime_role(source) not in _HANDOFF_ROLES:
            raise PrivateSpoolError("PRIVATE_SPOOL_HANDOFF_ROLE_INVALID")
        field, wrapper = ("from_role", "handoff") if kind == "HANDOFF" else ("writer_role", "transition")
        if not _actor_matches(envelope, field, wrapper):
            raise PrivateSpoolError("PRIVATE_SPOOL_HANDOFF_ACTOR_MISMATCH")
    if kind == "CONTEST" and _runtime_role(source) not in {"REFEREE_1", "REFUTADOR", "SENTINEL"}:
        raise PrivateSpoolError("PRIVATE_SPOOL_CONTEST_ROLE_INVALID")
    if kind == "VERDICT_REVIEW" and _runtime_role(source) not in {"REFEREE_1", "REFUTADOR"}:
        raise PrivateSpoolError("PRIVATE_SPOOL_REVIEW_ROLE_INVALID")
    if kind == "MUTATION_PROPOSAL" and source != "EXECUTOR":
        raise PrivateSpoolError("PRIVATE_SPOOL_RESULT_ROLE_INVALID")
    # The exact JSON bytes are persisted as an operation-receipt hash by Writer.
    try:
        raw = json.dumps(envelope, sort_keys=True, ensure_ascii=False,
                         separators=(",", ":"), allow_nan=False).encode("utf-8")
    except (ValueError, TypeError):
        raise PrivateSpoolError("PRIVATE_SPOOL_ENCODING_INVALID") from None
    if len(raw) > _MAX_ENVELOPE_BYTES:
        raise PrivateSpoolError("PRIVATE_SPOOL_ENVELOPE_TOO_LARGE")


def validated_private_sheet_items(document: Any) -> list[dict]:
    """Runner-generated, authenticated Sheet rows to trusted Writer items.

    Do not expose this function to public gateway clients: only the Writer job
    may supply the private spool document through a fixed runner-local path.
    """
    if not isinstance(document, dict) or document.get("contract") != CONTRACT or not isinstance(document.get("items"), list):
        raise PrivateSpoolError("PRIVATE_SPOOL_CONTRACT_INVALID")
    entries = []
    seen = {}
    for row in document["items"]:
        if not isinstance(row, dict) or set(row) != {"stable_id", "envelope"}:
            raise PrivateSpoolError("PRIVATE_SPOOL_ROW_INVALID")
        stable = row["stable_id"]
        if not isinstance(stable, str) or not _SPOOL_ID.fullmatch(stable):
            raise PrivateSpoolError("PRIVATE_SPOOL_STABLE_ID_INVALID")
        envelope = row["envelope"]
        _validate_envelope(envelope)
        signature = json.dumps(envelope, ensure_ascii=False, sort_keys=True,
                               separators=(",", ":"), allow_nan=False)
        prior = seen.get(stable)
        if prior is not None:
            if prior != signature:
                raise PrivateSpoolError("PRIVATE_SPOOL_STABLE_ID_CONFLICT")
            continue
        seen[stable] = signature
        entries.append({
            **envelope, "_inbox_source": "DRIVE_SHEET",
            "_inbox_name": "scheduled-ps-" + stable,
            "_inbox_id": "drive-sheet:" + stable,
        })
    return entries
