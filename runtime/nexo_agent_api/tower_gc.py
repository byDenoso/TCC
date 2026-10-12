"""Private, lossless Tower maintenance inside the existing Writer.

The production entry point is read-only. Archive/restore functions rehearse on
isolated candidates; none uploads, deletes canonical files, grants authority,
or enables a collector. Unknown references and consumers retain their objects.
Only the existing Writer may promote a reviewed candidate via CAS/readback.
"""
from __future__ import annotations

import copy
import gzip
import hashlib
import io
import json
import re
import zipfile
import zlib
from collections import Counter, defaultdict, deque
from pathlib import PurePosixPath
from typing import Any

from .live_tower import read_live_tower_bytes, verify_live_tower

CONTRACT = "TOWER_GC_DRY_RUN_V1"
ARCHIVE_CONTRACT = "TOWER_GC_ARCHIVE_V1"
_SAFE_DERIVED_ROOTS = ("cache/", "retrieval/cache/")
_SCIENCE_ROOTS = ("entities/", "roadmaps/", "manifests/", "recipes/", "data/", "artifacts/", "evolution/")
_AUTHORITY_ROOTS = ("contracts/", "governance/", "runtime/", "authorizations/", "privacy/")
_IDEMPOTENCY_ROOTS = ("operations/", "mutations/receipts/")
_HASH = re.compile(r"^sha256:[0-9a-f]{64}$")
_ID = re.compile(r"^(?:[A-Z][A-Z0-9_-]*::|OR-[0-9a-f]{32}$)")


class TowerGCError(ValueError):
    """Fail closed on an incomplete inventory, corrupt archive or conflict."""


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def _hash(raw: bytes) -> str:
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _safe_path(path: str) -> str:
    if (not isinstance(path, str) or not path or "\\" in path or "\x00" in path
            or PurePosixPath(path).is_absolute() or any(x in {".", "..", ""} for x in path.split("/"))):
        raise TowerGCError("GC_UNSAFE_PATH")
    return path


def _bundle(raw: bytes) -> tuple[dict, str]:
    bundle = read_live_tower_bytes(raw)
    if not isinstance(bundle, dict) or not isinstance(bundle.get('files'), dict):
        raise TowerGCError('GC_TOWER_NOT_OBJECT')
    revision = verify_live_tower(bundle)
    for path, entry in bundle["files"].items():
        _safe_path(path)
        if not isinstance(entry, dict):
            raise TowerGCError("GC_ENTRY_INVALID")
    return bundle, revision


def _strings(value, field=""):
    if isinstance(value, dict):
        for key, child in value.items():
            # Map keys can contain historical IDs or logical paths as well.
            yield "map_key", str(key)
            yield from _strings(child, str(key))
    elif isinstance(value, list):
        for child in value:
            yield from _strings(child, field)
    elif isinstance(value, str):
        yield field, value


def _classify(path, entry):
    value = entry.get("value")
    if path == "CONTROL.json" or path.startswith(_AUTHORITY_ROOTS):
        return "KEEP_AUTHORITY"
    if path.startswith(_IDEMPOTENCY_ROOTS):
        return "KEEP_IDEMPOTENCY"
    if path.startswith(_SCIENCE_ROOTS):
        return "KEEP_SCIENCE"
    if path.startswith(("events/", "snapshot/", "bootstrap/", "queues/")):
        return "KEEP_ACTIVE_OR_AUDIT"
    if (path.startswith(_SAFE_DERIVED_ROOTS) and entry.get("encoding") == "json"
            and isinstance(value, dict) and value.get("derived") is True):
        return "REBUILDABLE_DERIVED"
    return "UNRESOLVED_REF"


def plan_gc(raw: bytes) -> dict:
    """Inventory by exact identity and conservative reachability; never mutate."""
    bundle, revision = _bundle(raw)
    files = bundle["files"]
    aliases = defaultdict(set)
    by_hash = defaultdict(list)
    sizes = {}
    classes = {}
    for path, entry in sorted(files.items()):
        data = _canonical(entry)
        sizes[path] = len(data)
        by_hash[_hash(data)].append(path)
        aliases[path].add(path)
        aliases["TOWER_V06/" + path].add(path)
        if isinstance(entry.get("value"), dict):
            for field in ("id", "receipt_id", "stable_id"):
                identity = entry["value"].get(field)
                if isinstance(identity, str) and identity:
                    aliases[identity].add(path)
        classes[path] = _classify(path, entry)

    edges = {path: set() for path in files}
    unresolved = defaultdict(set)
    for path, entry in sorted(files.items()):
        for field, text in _strings(entry):
            reference = text.split("#", 1)[0]
            targets = aliases.get(reference)
            if targets:
                edges[path].update(targets)
                if len(targets) > 1:
                    unresolved[path].add("AMBIGUOUS_IDENTITY")
            elif (_ID.match(reference) or reference.startswith("TOWER_V06/")
                  or ("/" in reference and reference.endswith((".json", ".md", ".py")))
                  or (_HASH.fullmatch(reference) and field not in {
                      "payload_sha256", "source_revision", "result_revision", "revision",
                      "state_fingerprint", "source_bytes_sha256", "plan_sha256"})):
                # Hashes/external/dynamic references cannot establish absence.
                unresolved[path].add("UNRESOLVED_OR_EXTERNAL_REFERENCE")

    roots = {p for p, c in classes.items() if c != "REBUILDABLE_DERIVED"}
    roots.update(unresolved)
    reachable = set(roots)
    queue = deque(sorted(roots))
    while queue:
        for target in sorted(edges[queue.popleft()]):
            if target not in reachable:
                reachable.add(target)
                queue.append(target)

    items = []
    for path in sorted(files):
        classification = classes[path]
        reasons = []
        if path in reachable and classification == "REBUILDABLE_DERIVED":
            classification = "KEEP_ACTIVE_OR_AUDIT"
            reasons.append("REACHABLE_FROM_RETAINED_ROOT")
        if unresolved[path]:
            reasons.extend(sorted(unresolved[path]))
        if classification == "REBUILDABLE_DERIVED":
            reasons.append("CONSUMER_COVERAGE_AND_REBUILD_PROOF_REQUIRED")
        items.append({"path": path, "class": classification, "bytes": sizes[path],
                      "sha256": _hash(_canonical(files[path])), "refs": sorted(edges[path]),
                      "reasons": reasons, "eligible_for_removal": False})
    duplicates = []
    for digest, paths in sorted(by_hash.items()):
        if len(paths) > 1:
            original = _canonical(files[paths[0]])
            if not all(_canonical(files[path]) == original for path in paths):
                raise TowerGCError("GC_HASH_COLLISION")
            duplicates.append({"sha256": digest, "paths": paths,
                               "shared_bytes_estimate": len(original) * (len(paths) - 1)})
    summary = {"tower_bytes": len(raw), "logical_files": len(files),
               "classes": dict(sorted(Counter(row["class"] for row in items).items())),
               "reference_edges": sum(len(refs) for refs in edges.values()),
               "unresolved_objects": sum(bool(v) for v in unresolved.values()),
               "duplicate_groups": len(duplicates),
               "dedup_bytes_estimate": sum(row["shared_bytes_estimate"] for row in duplicates),
               "physical_removals": 0, "consumer_coverage": "UNVERIFIED"}
    plan = {"contract": CONTRACT, "mode": "DRY_RUN", "visibility": "PRIVATE",
            "tower_file_id": bundle["stable_file_id"], "base_revision": revision,
            "source_bytes_sha256": _hash(raw), "summary": summary,
            "items": items, "duplicate_groups": duplicates}
    plan["plan_sha256"] = _hash(_canonical(plan))
    return plan


def prepare_archive(raw: bytes, paths: list[str]) -> tuple[bytes, dict]:
    """Non-destructive, content-addressed archive rehearsal with exact aliases.

    Entry bytes are canonical serializations of the original Tower entries.
    Full raw-snapshot byte preservation is provided by prepare_backup instead.
    Archives retain every distinct path even when their bytes can be shared.
    """
    bundle, revision = _bundle(raw)
    selected = sorted(set(paths))
    blobs = {}
    items = []
    for path in selected:
        _safe_path(path)
        if path not in bundle["files"]:
            raise TowerGCError("GC_ARCHIVE_SOURCE_MISSING")
        data = _canonical(bundle["files"][path])
        digest = _hash(data)
        if digest in blobs and blobs[digest] != data:
            raise TowerGCError("GC_HASH_COLLISION")
        blobs[digest] = data
        items.append({"path": path, "sha256": digest, "bytes": len(data), "member": "blobs/" + digest[7:] + ".json"})
    manifest = {"contract": ARCHIVE_CONTRACT, "visibility": "PRIVATE", "mode": "REHEARSAL_ONLY",
                "tower_file_id": bundle["stable_file_id"], "base_revision": revision,
                "source_bytes_sha256": _hash(raw), "items": items}
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        for name, data in [("manifest.json", _canonical(manifest))] + [
                ("blobs/" + digest[7:] + ".json", data) for digest, data in sorted(blobs.items())]:
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = 0o100600 << 16
            archive.writestr(info, data)
    packed = output.getvalue()
    receipt = {**manifest, "archive_sha256": _hash(packed), "archive_bytes": len(packed),
               "original_entry_bytes": sum(row["bytes"] for row in items),
               "unique_entry_bytes": sum(len(data) for data in blobs.values())}
    verify_archive(packed, receipt)
    return packed, receipt


def verify_archive(raw: bytes, receipt: dict) -> dict[str, dict]:
    """Verify hashes, identities, limits and every member before restoration."""
    if (not isinstance(receipt, dict) or receipt.get("contract") != ARCHIVE_CONTRACT or receipt.get("visibility") != "PRIVATE"
            or receipt.get("mode") != "REHEARSAL_ONLY" or receipt.get("archive_sha256") != _hash(raw)
            or receipt.get("archive_bytes") != len(raw)):
        raise TowerGCError("GC_ARCHIVE_READBACK_MISMATCH")
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            names = archive.namelist()
            if len(set(names)) != len(names):
                raise TowerGCError("GC_ARCHIVE_DUPLICATE_MEMBER")
            expected_manifest = {key: receipt[key] for key in (
                "contract", "visibility", "mode", "tower_file_id", "base_revision", "source_bytes_sha256", "items")}
            expected_bytes = _canonical(expected_manifest)
            info = archive.getinfo("manifest.json")
            if info.file_size != len(expected_bytes) or archive.read(info) != expected_bytes:
                raise TowerGCError("GC_ARCHIVE_MANIFEST_MISMATCH")
            expected_members = {"manifest.json"}
            restored = {}
            cache = {}
            for item in receipt["items"]:
                path = _safe_path(item["path"])
                digest = item["sha256"]
                if not isinstance(digest, str) or not _HASH.fullmatch(digest):
                    raise TowerGCError("GC_ARCHIVE_HASH_INVALID")
                member = "blobs/" + digest[7:] + ".json"
                if item["member"] != member or path in restored:
                    raise TowerGCError("GC_ARCHIVE_IDENTITY_INVALID")
                expected_members.add(member)
                info = archive.getinfo(member)
                if info.file_size != item["bytes"]:
                    raise TowerGCError("GC_ARCHIVE_ITEM_SIZE_MISMATCH")
                if member not in cache:
                    cache[member] = archive.read(info)
                data = cache[member]
                if _hash(data) != digest:
                    raise TowerGCError("GC_ARCHIVE_ITEM_HASH_MISMATCH")
                value = json.loads(data)
                if not isinstance(value, dict) or _canonical(value) != data:
                    raise TowerGCError("GC_ARCHIVE_ITEM_INVALID")
                restored[path] = value
            if expected_members != set(names):
                raise TowerGCError("GC_ARCHIVE_UNEXPECTED_MEMBER")
            return restored
    except (KeyError, TypeError, OSError, ValueError, zipfile.BadZipFile, RuntimeError, zlib.error) as exc:
        if isinstance(exc, TowerGCError):
            raise
        raise TowerGCError("GC_ARCHIVE_UNREADABLE") from exc


def restore_entries(current_raw: bytes, archive_raw: bytes, receipt: dict, *, expected_revision: str) -> tuple[bytes, dict]:
    """Offline inverse on the latest revision: preserve deltas, refuse collisions.

    This is a prepared candidate, NOT a commit or an upload. A subsequent head
    check and readback through the sole Writer remain mandatory.
    """
    if not isinstance(receipt, dict):
        raise TowerGCError("GC_MANIFEST_INVALID")
    current, revision = _bundle(current_raw)
    if revision != expected_revision:
        raise TowerGCError("GC_CAS_CONFLICT")
    if current["stable_file_id"] != receipt.get("tower_file_id"):
        raise TowerGCError("GC_TOWER_IDENTITY_MISMATCH")
    restored = verify_archive(archive_raw, receipt)
    candidate = copy.deepcopy(current)
    added = 0
    for path, value in restored.items():
        if path in candidate["files"] and candidate["files"][path] != value:
            raise TowerGCError("GC_RESTORE_PATH_CONFLICT")
        if path not in candidate["files"]:
            candidate["files"][path] = value
            added += 1
    if not added:
        return current_raw, {"status": "NO_OP", "restored": 0, "before": revision, "after": revision}
    fingerprint = _hash(_canonical(candidate["files"]))
    candidate.update(file_count=len(candidate["files"]), revision=fingerprint, state_fingerprint=fingerprint)
    result = _canonical(candidate) + b"\n"
    verify_live_tower(read_live_tower_bytes(result))
    return result, {"status": "PREPARED_NOT_COMMITTED", "restored": added,
                    "before": revision, "after": fingerprint, "readback": "REQUIRED"}


def prepare_backup(raw: bytes) -> tuple[bytes, dict]:
    """Exact raw snapshot bytes, independent of later serializer formatting."""
    bundle, revision = _bundle(raw)
    packed = gzip.compress(raw, mtime=0)
    receipt = {"contract": "TOWER_GC_BACKUP_V1", "visibility": "PRIVATE", "base_revision": revision,
               "tower_file_id": bundle["stable_file_id"], "raw_bytes": len(raw),
               "raw_sha256": _hash(raw), "backup_bytes": len(packed), "backup_sha256": _hash(packed)}
    restore_backup(packed, receipt)
    return packed, receipt


def restore_backup(packed: bytes, receipt: dict) -> bytes:
    if (not isinstance(receipt, dict) or receipt.get("contract") != "TOWER_GC_BACKUP_V1" or receipt.get("visibility") != "PRIVATE"
            or _hash(packed) != receipt.get("backup_sha256") or len(packed) != receipt.get("backup_bytes")):
        raise TowerGCError("GC_BACKUP_READBACK_MISMATCH")
    try:
        with gzip.GzipFile(fileobj=io.BytesIO(packed)) as handle:
            raw = handle.read(receipt["raw_bytes"] + 1)
        if len(raw) != receipt["raw_bytes"] or _hash(raw) != receipt["raw_sha256"]:
            raise TowerGCError("GC_BACKUP_CONTENT_MISMATCH")
        bundle, revision = _bundle(raw)
        if revision != receipt["base_revision"] or bundle["stable_file_id"] != receipt["tower_file_id"]:
            raise TowerGCError("GC_BACKUP_IDENTITY_MISMATCH")
        return raw
    except (OSError, EOFError, TypeError, KeyError, zlib.error) as exc:
        raise TowerGCError("GC_BACKUP_UNREADABLE") from exc


def opportunistic_dry_run(raw: bytes, report_path, *, max_bytes: int) -> dict:
    """Opt-in bounded maintenance in the existing cycle; one private cache.

    max_bytes is an explicit runtime budget, not an invented default. This
    function cannot compact or archive production state. Identical bytes reuse
    the previous report; errors affect collection only.
    """
    import os
    import tempfile
    from pathlib import Path

    if type(max_bytes) is not int or max_bytes < len(raw):
        return {"status": "SKIPPED_BUDGET"}
    destination = Path(report_path)
    source_hash = _hash(raw)
    if destination.is_file():
        try:
            cached = json.loads(destination.read_bytes())
            check = dict(cached)
            digest = check.pop("plan_sha256", None)
            if (digest == _hash(_canonical(check)) and cached.get("contract") == CONTRACT
                    and cached.get("source_bytes_sha256") == source_hash):
                return {"status": "CACHED_DRY_RUN", "physical_removals": 0}
        except (OSError, ValueError, TypeError):
            pass
    plan = plan_gc(raw)
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix="tower-gc-", dir=destination.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(_canonical(plan) + b"\n")
        os.replace(temporary, destination)
    finally:
        Path(temporary).unlink(missing_ok=True)
    return {"status": "DRY_RUN", "physical_removals": 0,
            "logical_files": plan["summary"]["logical_files"]}
