from __future__ import annotations

import gzip
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

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


def build_live_tower_payload(
    root: str | Path,
    *,
    updated_at: str | None = None,
) -> dict[str, Any]:
    root = Path(root)
    paths: set[Path] = set()
    for pattern in _JSON_SURFACES:
        paths.update(path for path in root.glob(pattern) if path.is_file())

    files: dict[str, dict[str, Any]] = {}
    for path in sorted(paths):
        files[path.relative_to(root).as_posix()] = {
            "encoding": "json",
            "value": json.loads(path.read_text(encoding="utf-8")),
        }

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
    payload = build_live_tower_payload(root, updated_at=updated_at)
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
