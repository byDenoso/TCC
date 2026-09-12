from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Any

from runtime.nexo_core.projection import validate_snapshot

CONTRACT_VERSION = "nexo-one/0.5"
PRIVATE_PREFIXES = {"CLIENT", "MEASUREMENT", "CHECKIN", "PROFILE", "PLAN"}


class FrontendSnapshotError(ValueError):
    pass


def _canonical_bytes(snapshot: dict[str, Any]) -> bytes:
    return json.dumps(
        snapshot,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def _contains_private_scope(snapshot: dict[str, Any]) -> bool:
    olympus = snapshot.get("olympus") or {}
    if olympus.get("entity_refs"):
        return True
    for node in snapshot.get("nodes") or []:
        if not isinstance(node, dict):
            continue
        prefix = str(node.get("id", "")).split("::", 1)[0].upper()
        if prefix in PRIVATE_PREFIXES:
            return True
    return False


def build_frontend_envelope(
    snapshot: dict[str, Any], *, visibility: str = "private"
) -> dict[str, Any]:
    errors = validate_snapshot(snapshot)
    if errors:
        raise FrontendSnapshotError("invalid_snapshot:" + ";".join(errors))
    if visibility not in {"private", "public"}:
        raise FrontendSnapshotError("invalid_visibility")
    if visibility == "public" and _contains_private_scope(snapshot):
        raise FrontendSnapshotError("public_snapshot_contains_private_scope")

    materialized = deepcopy(snapshot)
    digest = hashlib.sha256(_canonical_bytes(materialized)).hexdigest()
    return {
        "contract_version": CONTRACT_VERSION,
        "visibility": visibility,
        "snapshot_sha256": digest,
        "snapshot": materialized,
    }


def validate_frontend_envelope(envelope: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if envelope.get("contract_version") != CONTRACT_VERSION:
        errors.append("contract_version")
    visibility = envelope.get("visibility")
    if visibility not in {"private", "public"}:
        errors.append("visibility")
    snapshot = envelope.get("snapshot")
    if not isinstance(snapshot, dict):
        errors.append("snapshot")
        return errors
    errors.extend(f"snapshot:{item}" for item in validate_snapshot(snapshot))
    expected = hashlib.sha256(_canonical_bytes(snapshot)).hexdigest()
    if envelope.get("snapshot_sha256") != expected:
        errors.append("snapshot_sha256")
    if visibility == "public" and _contains_private_scope(snapshot):
        errors.append("public_private_scope")
    return errors
