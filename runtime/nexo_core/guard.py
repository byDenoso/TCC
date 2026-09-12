from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from typing import Any, Collection

from runtime.nexo_core.models import CanonicalEntity, CanonicalEvent, TransitionResult


def make_payload_hash(payload: Any) -> str:
    canonical_payload = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical_payload.encode("utf-8")).hexdigest()


def make_dedupe_key(
    role: str,
    run_id: str,
    entity_ref: str,
    event_type: str,
    payload: Any,
) -> str:
    payload_hash = make_payload_hash(payload)
    return "|".join((role, run_id, entity_ref, event_type, payload_hash))


def apply_transition(
    entity: CanonicalEntity,
    event: CanonicalEvent,
    *,
    expected_version: int,
    owner_role: str,
    seen_dedupe_keys: Collection[str],
) -> TransitionResult:
    if event.dedupe_key in seen_dedupe_keys:
        return TransitionResult(status="NOOP", entity=entity, event=None)
    if event.source_role != owner_role or entity.writer_role != owner_role:
        return TransitionResult(status="WRITE_AUTHORITY_CONFLICT", entity=entity, event=None)
    if expected_version != entity.entity_version:
        return TransitionResult(status="WRITE_CONFLICT_RETRY_REQUIRED", entity=entity, event=None)
    if event.entity_ref != entity.entity_ref:
        return TransitionResult(status="ENTITY_REF_CONFLICT", entity=entity, event=None)
    if event.state_from != entity.state:
        return TransitionResult(status="STATE_CONFLICT_RETRY_REQUIRED", entity=entity, event=None)

    result_version = entity.entity_version + 1
    if event.expected_entity_version is not None and event.expected_entity_version != entity.entity_version:
        return TransitionResult(status="EVENT_VERSION_CONTRACT_CONFLICT", entity=entity, event=None)
    if event.result_entity_version is not None and event.result_entity_version != result_version:
        return TransitionResult(status="EVENT_VERSION_CONTRACT_CONFLICT", entity=entity, event=None)

    bound_event = replace(
        event,
        expected_entity_version=entity.entity_version,
        result_entity_version=result_version,
    )
    updated = replace(
        entity,
        state=bound_event.state_to,
        entity_version=result_version,
        last_event_id=bound_event.event_id,
        last_correlation_id=bound_event.correlation_id,
        writer_role=owner_role,
    )
    return TransitionResult(status="APPLIED", entity=updated, event=bound_event)


def verify_readback(expected: CanonicalEntity, actual: CanonicalEntity) -> str:
    return "PASS" if actual == expected else "CANONICAL_WRITE_UNVERIFIED"
