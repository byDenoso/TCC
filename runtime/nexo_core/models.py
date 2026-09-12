from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class CanonicalEntity:
    entity_ref: str
    state: str
    entity_version: int
    writer_role: str
    last_event_id: str | None = None
    last_correlation_id: str | None = None
    data: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CanonicalEvent:
    event_id: str
    entity_ref: str
    event_type: str
    correlation_id: str
    source_role: str
    state_from: str
    state_to: str
    resource_key: str
    dedupe_key: str
    payload_ref: str | None = None
    run_id: str | None = None
    timestamp: str | None = None


@dataclass(frozen=True)
class TransitionResult:
    status: str
    entity: CanonicalEntity
    event: CanonicalEvent | None = None
