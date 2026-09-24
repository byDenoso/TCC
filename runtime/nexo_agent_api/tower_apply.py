"""Shared apply step of the Tower writer (CLI writer and the ChatGPT writer bundle)."""

from __future__ import annotations

import json
from pathlib import Path

from .tower_paths import fs_path


_DOCUMENT_PREFIXES = ("roadmaps/", "indexes/", "contracts/", "manifests/")


def apply_document(root: Path, request: dict) -> dict:
    """Deep-merge ``request['merge']`` into a Tower document (roadmaps, indexes, ...).

    Entities go through apply_mutation_request (versioned, governed); documents
    such as roadmaps are merged here, inside the same CAS write.
    ``list_merge`` names list fields whose items are merged by ``key``.
    """
    relative = str(request["document"]).lstrip("/")
    if not relative.startswith(_DOCUMENT_PREFIXES) or ".." in relative.split("/") or not relative.endswith(".json"):
        return {"request_id": request.get("request_id"), "accepted": False, "issue": {"code": "DOCUMENT_PATH_NOT_ALLOWED", "message": relative}}
    path = fs_path(root, relative)
    current = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}

    def merge(base, patch, key_fields):
        for key, value in patch.items():
            if key in key_fields and isinstance(value, list) and isinstance(base.get(key), list):
                id_key = key_fields[key]
                by_id = {item.get(id_key): item for item in base[key] if isinstance(item, dict)}
                for item in value:
                    if isinstance(item, dict) and item.get(id_key) in by_id:
                        by_id[item[id_key]].update(item)
                    else:
                        base[key].append(item)
            elif isinstance(value, dict) and isinstance(base.get(key), dict):
                merge(base[key], value, {})
            else:
                base[key] = value
        return base

    merged = merge(current, dict(request.get("merge") or {}), dict(request.get("list_merge") or {}))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(merged, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return {"request_id": request.get("request_id"), "accepted": True, "document": relative, "readback": "PASS"}




def apply_requests(root: Path, requests: list[dict]) -> list[dict]:
    """Apply entity mutations and document merges to a materialized Tower root, in order."""
    from .mutations import apply_mutation_request

    receipts = [apply_document(root, r) if "document" in r else apply_mutation_request(root, r) for r in requests]
    if any("document" in r for r in requests):
        from .live_tower import publish_live_tower

        publish_live_tower(root)
    return receipts
