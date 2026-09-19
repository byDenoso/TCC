from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any


def _canonical_bytes(payload: Any) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def cache_key(namespace: str, payload: Any, provenance: Any | None = None) -> str:
    envelope = {
        "namespace": str(namespace),
        "payload": payload,
        "provenance": provenance or {},
    }
    return hashlib.sha256(_canonical_bytes(envelope)).hexdigest()


def cache_root() -> Path:
    explicit = str(os.getenv("NEXO_COSMOLOGY_CACHE_DIR") or "").strip()
    if explicit:
        root = Path(explicit)
    else:
        base = str(os.getenv("NEXO_RUNTIME_CACHE_DIR") or "").strip()
        root = (Path(base) if base else Path(".nexo_cache")) / "cosmology"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _path(namespace: str, key: str) -> Path:
    safe_namespace = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in namespace)
    directory = cache_root() / safe_namespace
    directory.mkdir(parents=True, exist_ok=True)
    return directory / f"{key}.json"


def load_json(namespace: str, payload: Any, provenance: Any | None = None) -> dict[str, Any] | None:
    key = cache_key(namespace, payload, provenance)
    path = _path(namespace, key)
    if not path.is_file():
        return None
    try:
        cached = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(cached, dict):
        return None
    if cached.get("_cache_key") != key:
        return None
    value = cached.get("value")
    return value if isinstance(value, dict) else None


def store_json(namespace: str, payload: Any, value: dict[str, Any], provenance: Any | None = None) -> Path:
    key = cache_key(namespace, payload, provenance)
    path = _path(namespace, key)
    envelope = {
        "_cache_key": key,
        "_namespace": namespace,
        "_provenance": provenance or {},
        "value": value,
    }
    encoded = json.dumps(envelope, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    fd, tmp_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
    finally:
        try:
            os.unlink(tmp_name)
        except FileNotFoundError:
            pass
    return path
