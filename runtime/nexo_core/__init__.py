"""NEXO Core v0.5: canonical write guards and frontend state projection."""

from runtime.nexo_core.guard import apply_transition, make_dedupe_key, verify_readback
from runtime.nexo_core.models import CanonicalEntity, CanonicalEvent, TransitionResult
from runtime.nexo_core.projection import build_snapshot, validate_snapshot
from runtime.nexo_core.publisher import SnapshotValidationError, publish_snapshot

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
]
