from __future__ import annotations

from typing import Any

from peer_decisive_followups.production_contract import sha256_json

ACT_COMMIT = "627aeafb88ae5ad1aa66b406bea2d65cfa66a27d"
EXPECTED_RUNTIME = {
    "schema": "peer-nested-runtime-v1",
    "python": "3.11",
    "cobaya": "3.6.2",
    "camb": "1.6.6",
    "cosmorec": "2.0.3",
    "polychord": "1.20.1",
    "act_commit": ACT_COMMIT,
}


class RuntimeContractError(RuntimeError):
    pass


def build_runtime_manifest(*, payload_hashes: dict[str, str] | None = None,
                           source: dict[str, Any] | None = None) -> dict[str, Any]:
    core: dict[str, Any] = {
        **EXPECTED_RUNTIME,
        "payload_hashes": dict(sorted((payload_hashes or {}).items())),
        "source": source or {},
    }
    return {**core, "identity_sha256": sha256_json(core)}


def verify_runtime_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(manifest, dict):
        raise RuntimeContractError("runtime manifest must be a mapping")
    labels = {
        "python": "Python",
        "cobaya": "Cobaya",
        "camb": "CAMB",
        "cosmorec": "CosmoRec",
        "polychord": "PolyChord",
        "act_commit": "ACT commit",
        "schema": "schema",
    }
    for key, expected in EXPECTED_RUNTIME.items():
        if manifest.get(key) != expected:
            raise RuntimeContractError(
                f"{labels.get(key, key)} runtime mismatch: expected {expected!r}, got {manifest.get(key)!r}"
            )
    core = {key: value for key, value in manifest.items() if key != "identity_sha256"}
    expected_identity = sha256_json(core)
    identity = manifest.get("identity_sha256")
    if identity is not None and identity != expected_identity:
        raise RuntimeContractError("runtime identity hash mismatch")
    verified = dict(manifest)
    verified["identity_sha256"] = expected_identity
    return verified
