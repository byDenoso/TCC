"""NEXO Core v0.5: canonical write guards and frontend state projection."""

from runtime.nexo_core.canary import run_v05_canary
from runtime.nexo_core.guard import apply_transition, make_dedupe_key, verify_readback
from runtime.nexo_core.models import CanonicalEntity, CanonicalEvent, TransitionResult
from runtime.nexo_core.projection import build_snapshot, validate_snapshot
from runtime.nexo_core.publisher import SnapshotValidationError, publish_snapshot
from runtime.nexo_core.ssot import event_row_to_event, work_row_to_entity

__all__ = [
    "CanonicalEntity",
    "CanonicalEvent",
    "TransitionResult",
    "apply_transition",
    "make_dedupe_key",
    "verify_readback",
    "build_snapshot",
    "validate_snapshot",
    "SnapshotValidationError",
    "publish_snapshot",
    "work_row_to_entity",
    "event_row_to_event",
    "run_v05_canary",
]
