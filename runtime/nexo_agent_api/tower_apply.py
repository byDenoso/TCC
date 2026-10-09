"""Shared apply step of the Tower writer (CLI writer and the ChatGPT writer bundle)."""

from __future__ import annotations

import json
from pathlib import Path

from .tower_paths import fs_path


_DOCUMENT_PREFIXES = ("roadmaps/", "indexes/", "contracts/", "manifests/", "evolution/")


def apply_document(root: Path, request: dict) -> dict:
    """Deep-merge ``request['merge']`` into a Tower document (roadmaps, indexes, ...).

    Entities go through apply_mutation_request (versioned, governed); documents
    such as roadmaps are merged here, inside the same CAS write.
    ``list_merge`` names list fields whose items are merged by ``key``.
    """
    relative = str(request["document"])
    # Reject aliases before the authority check. On Windows, backslashes,
    # repeated separators and dot components can otherwise reach the same file
    # through a spelling that escapes the protected-document allowlist.
    if "\\" in relative or ":" in relative or any(part in {"", ".", ".."} for part in relative.split("/")):
        return {"request_id": request.get("request_id"), "accepted": False,
                "issue": {"code": "DOCUMENT_PATH_NOT_CANONICAL", "message": relative}}
    from .autonomy import guard_document
    refused = guard_document(root, request)
    if refused is not None:
        return refused
    if (relative != "CONTROL.json" and not relative.startswith(_DOCUMENT_PREFIXES)) or ".." in relative.split("/") or not relative.endswith(".json"):
        return {"request_id": request.get("request_id"), "accepted": False, "issue": {"code": "DOCUMENT_PATH_NOT_ALLOWED", "message": relative}}
    from .scientific_integrity import guard_batteries
    refused = guard_batteries(root, request)
    if refused is not None:
        return refused
    path = fs_path(root, relative)
    current = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
    patch = request.get("merge") or {}
    if not isinstance(patch, dict):
        return {"accepted": False, "issue": {"code": "INVALID_DOCUMENT_MERGE"}}
    frozen_issue = None
    if relative.startswith("roadmaps/"):
        charter = current.get("charter") or {}
        charter = charter if isinstance(charter, dict) else {}
        signed = charter.get("status") in {"CHARTERED", "CLOSED"} or bool(charter.get("charter_hash"))
        charter_patch = patch["charter"] if "charter" in patch else {}
        operational = {"status", "closed_at", "close_reason", "final_report"}
        if signed and (not isinstance(charter_patch, dict) or any(value != charter.get(key)
                              for key, value in charter_patch.items() if key not in operational)):
            frozen_issue = "SIGNED_CHARTER_IMMUTABLE"
        identity_fields = {"question_id", "roadmap_id", "mandate_id", "public_data_only", "public_data_refs"}
        if any(current.get(key) is not None and key in patch and patch[key] != current[key] for key in identity_fields):
            frozen_issue = "CAMPAIGN_IDENTITY_AND_SCOPE_IMMUTABLE"
        from .autonomy import WRITER_AUTHORITY
        changes_closure = ("closure" in patch or patch.get("status") == "CLOSED"
                           or isinstance(charter_patch, dict) and any(
                               key in charter_patch for key in ("closed_at", "close_reason"))
                           or isinstance(charter_patch, dict) and charter_patch.get("status") == "CLOSED")
        if changes_closure and request.get("_autonomy_authority") is not WRITER_AUTHORITY:
            frozen_issue = "CAMPAIGN_CLOSURE_WRITER_ONLY"
    if relative.startswith("contracts/") and current:
        # Existing contracts carry scientific/authority promises. A changed
        # contract needs a new versioned identity, never an in-place raw merge.
        if any(key not in current or value != current[key] for key, value in patch.items()):
            frozen_issue = "EXISTING_CONTRACT_IMMUTABLE_USE_NEW_VERSION"
    if frozen_issue:
        return {"request_id": request.get("request_id"), "accepted": False, "issue": {"code": frozen_issue}}

    if relative == "evolution/board.json":
        existing = {str(post.get("id")): post for post in current.get("posts") or []
                    if isinstance(post, dict) and str(post.get("id") or "")}
        proposed = (request.get("merge") or {}).get("posts") or []
        def signature(post):
            return (post.get("from"), post.get("to"), post.get("text"), tuple(post.get("refs") or []),
                    post.get("reply_to"), bool(post.get("private")))
        for post in proposed:
            if not isinstance(post, dict) or not str(post.get("id") or ""):
                continue
            prior = existing.get(str(post["id"]))
            prior_content = prior is not None and all(prior.get(key) is not None for key in ("from", "to", "text"))
            post_content = all(post.get(key) is not None for key in ("from", "to", "text"))
            if prior_content and post_content and signature(prior) != signature(post):
                return {"request_id": request.get("request_id"), "accepted": False,
                        "issue": {"code": "BOARD_ID_COLLISION", "message": str(post["id"])}}

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
    if relative == "evolution/board.json" and isinstance(merged.get("posts"), list):
        merged["posts"] = merged["posts"][-300:]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(merged, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return {"request_id": request.get("request_id"), "accepted": True, "document": relative, "readback": "PASS"}




def apply_requests(root: Path, requests: list[dict]) -> list[dict]:
    """Apply entity mutations and document merges to a materialized Tower root, in order."""
    from .mutations import apply_mutation_request

    from .scientific_integrity import guard_transition
    receipts = []
    for request in requests:
        refused = guard_transition(root, request)
        if refused is not None:
            receipts.append(refused)
        else:
            receipts.append(apply_document(root, request) if "document" in request else apply_mutation_request(root, request))
    if any("document" in r for r in requests):
        from .live_tower import publish_live_tower

        publish_live_tower(root)
    return receipts
