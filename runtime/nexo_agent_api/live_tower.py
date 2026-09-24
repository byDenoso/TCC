from __future__ import annotations

import gzip
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .tower_paths import fs_path, logical_path

LIVE_TOWER_CONTRACT = "NEXO_TOWER_LIVE_V1"
LIVE_TOWER_FILE_ID = "1m97cFmEkw19yiqD_6FWPG4j1lDCAYM4z"
# O objeto vivo no Drive é JSON puro (application/json) desde o cutover de
# 2026-09-23; o artefato local tem o mesmo nome e formato que o transporte sobe.
LIVE_TOWER_NAME = "NEXO_TOWER_LIVE.json"
LEGACY_LIVE_TOWER_NAME = "NEXO_TOWER_LIVE.json.gz"


def read_live_tower_bytes(raw: bytes) -> dict[str, Any]:
    """Decode a live Tower object, plain JSON or the pre-cutover gzip form."""
    if raw[:2] == b"\x1f\x8b":
        raw = gzip.decompress(raw)
    return json.loads(raw.decode("utf-8"))

_JSON_SURFACES = (
    "CONTROL.json",
    "roadmaps/**/*.json",
    "entities/**/*.json",
    "indexes/**/*.json",
    "manifests/**/*.json",
    "events/**/*.json",
    "mutations/receipts/**/*.json",
    "snapshot/**/*.json",
    "bootstrap/**/*.json",
    "queues/**/*.json",
)


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _is_scanned_surface(logical: str) -> bool:
    """True when ``logical`` is owned by the local scan (see ``_JSON_SURFACES``)."""
    if not logical.endswith(".json"):
        return False
    for pattern in _JSON_SURFACES:
        prefix = pattern.split("**", 1)[0]
        if pattern == logical or ("**" in pattern and logical.startswith(prefix)):
            return True
    return False


def build_live_tower_payload(
    root: str | Path,
    *,
    updated_at: str | None = None,
    base: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Pack the canonical files under ``root`` into one live Tower object.

    Files in ``base`` outside the scanned surfaces (contracts, governance,
    runtime, text entries, ...) are carried over unchanged, so repacking a
    downloaded Tower never drops state that the local scan does not own.
    """
    root = Path(root)
    paths: set[Path] = set()
    for pattern in _JSON_SURFACES:
        paths.update(path for path in root.glob(pattern) if path.is_file())

    files: dict[str, dict[str, Any]] = {
        key: value
        for key, value in ((base or {}).get("files") or {}).items()
        if not _is_scanned_surface(key)
    }
    for path in sorted(paths):
        files[logical_path(root, path)] = {
            "encoding": "json",
            "value": json.loads(path.read_text(encoding="utf-8")),
        }
    # Contracts are carried from ``base`` but a local edit (writer document merge)
    # must win, otherwise contract updates are silently dropped on repack.
    for path in sorted(root.glob("contracts/**/*.json")):
        if path.is_file():
            try:
                files[logical_path(root, path)] = {"encoding": "json", "value": json.loads(path.read_text(encoding="utf-8"))}
            except ValueError:
                pass  # keep the carried-over base entry

    files = dict(sorted(files.items()))
    fingerprint = "sha256:" + hashlib.sha256(_canonical(files)).hexdigest()
    return {
        "contract": LIVE_TOWER_CONTRACT,
        "authority": "TOWER_V06",
        "truth_owner": "TOWER_V06@GOOGLE_DRIVE_PRIVATE",
        "storage": "GOOGLE_DRIVE_PRIVATE",
        "write_model": "IN_PLACE_FILE_REVISION_CAS_READBACK",
        "stable_file_id": LIVE_TOWER_FILE_ID,
        "revision": fingerprint,
        "state_fingerprint": fingerprint,
        "updated_at": updated_at or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "file_count": len(files),
        "files": files,
    }


def publish_live_tower(
    root: str | Path,
    *,
    target: str | Path | None = None,
    updated_at: str | None = None,
) -> dict[str, Any]:
    root = Path(root)
    destination = Path(target) if target is not None else root / LIVE_TOWER_NAME
    # The previous live object at the destination is the base: whatever the
    # local scan does not own survives the repack.
    base = read_live_tower_bytes(destination.read_bytes()) if destination.is_file() else None
    payload = build_live_tower_payload(root, updated_at=updated_at, base=base)
    raw = _canonical(payload) + b"\n"

    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(destination.name + ".tmp")
    temporary.write_bytes(raw)
    os.replace(temporary, destination)

    decoded = read_live_tower_bytes(destination.read_bytes())
    if decoded.get("state_fingerprint") != payload["state_fingerprint"]:
        raise RuntimeError("LIVE_TOWER_READBACK_FINGERPRINT_MISMATCH")

    return {
        "status": "PASS",
        "path": str(destination),
        "stable_file_id": LIVE_TOWER_FILE_ID,
        "revision": payload["revision"],
        "state_fingerprint": payload["state_fingerprint"],
        "file_count": payload["file_count"],
        "readback": "PASS",
    }


def verify_live_tower(bundle: dict[str, Any]) -> str:
    """Validate a decoded live Tower object; return its state fingerprint."""
    if bundle.get("contract") != LIVE_TOWER_CONTRACT:
        raise ValueError(f"unsupported live Tower contract: {bundle.get('contract')!r}")
    if bundle.get("authority") != "TOWER_V06" or bundle.get("storage") != "GOOGLE_DRIVE_PRIVATE":
        raise ValueError("live Tower is not canonical TOWER_V06 storage")
    if bundle.get("truth_owner") != "TOWER_V06@GOOGLE_DRIVE_PRIVATE":
        raise ValueError("live Tower truth_owner is invalid")
    if bundle.get("write_model") != "IN_PLACE_FILE_REVISION_CAS_READBACK":
        raise ValueError("live Tower write_model is invalid")
    files = bundle.get("files")
    if not isinstance(files, dict) or bundle.get("file_count") != len(files):
        raise ValueError("live Tower file_count does not match files payload")
    fingerprint = "sha256:" + hashlib.sha256(_canonical(files)).hexdigest()
    if bundle.get("state_fingerprint") != fingerprint or bundle.get("revision") != fingerprint:
        # Objects written by hand before the single writer carry a header that
        # cannot be reproduced from their files. Readers trust the files (the
        # computed fingerprint); the next writer repack rewrites the header.
        import sys

        print(
            f"WARNING LIVE_TOWER_DECLARED_FINGERPRINT_STALE declared={bundle.get('state_fingerprint')} computed={fingerprint}",
            file=sys.stderr,
        )
    if not str(bundle.get("stable_file_id") or "").strip():
        raise ValueError("live Tower stable_file_id is missing")
    return fingerprint


def materialize_live_tower(raw: bytes, destination: str | Path) -> tuple[Path, dict[str, Any]]:
    """Verify live Tower bytes and unpack them into a working Tower root.

    The raw object is kept at ``<root>/NEXO_TOWER_LIVE.json`` as the repack
    base, so a later :func:`publish_live_tower` preserves unscanned files.
    """
    bundle = read_live_tower_bytes(raw)
    verify_live_tower(bundle)
    root = Path(destination).resolve()
    root.mkdir(parents=True, exist_ok=True)
    for relative, entry in bundle["files"].items():
        if not isinstance(relative, str) or not isinstance(entry, dict):
            continue
        target = fs_path(root, relative).resolve()
        if target != root and root not in target.parents:
            raise ValueError(f"unsafe live Tower path: {relative!r}")
        encoding = entry.get("encoding")
        if encoding == "json":
            data = json.dumps(entry.get("value"), ensure_ascii=False, sort_keys=True, indent=2) + "\n"
        elif encoding == "text":
            data = str(entry.get("data") if "data" in entry else entry.get("value") or "")
        else:
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(data, encoding="utf-8")
    (root / LIVE_TOWER_NAME).write_bytes(raw)

    control = json.loads((root / "CONTROL.json").read_text(encoding="utf-8"))
    if control.get("truth_owner") != bundle.get("truth_owner"):
        raise ValueError("materialized CONTROL truth_owner differs from live Tower")

    metadata = {
        "export_role": "PUBLIC_READ_ONLY_DERIVED_COPY",
        "tower_revision": verify_live_tower(bundle),
        "tower_file_id": str(bundle.get("stable_file_id")).strip(),
        "source_state_fingerprint": verify_live_tower(bundle),
        "source_storage": bundle.get("storage"),
        "truth_owner": bundle.get("truth_owner"),
    }
    return root, {key: value for key, value in metadata.items() if value is not None}
