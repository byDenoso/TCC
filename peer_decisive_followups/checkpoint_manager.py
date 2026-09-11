from __future__ import annotations

import hashlib
import json
import os
import shutil
from pathlib import Path
from typing import Any

from peer_decisive_followups.production_contract import sha256_json


class CheckpointError(RuntimeError):
    pass


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def inspect_raw_checkpoint(raw: Path) -> dict[str, Any]:
    raw = Path(raw)
    resumes = sorted(p for p in raw.glob("*.resume") if p.is_file()) if raw.exists() else []
    valid_resumes = [p for p in resumes if p.stat().st_size > 0]
    live = sorted(p for p in raw.glob("*_phys_live.txt") if p.is_file()) if raw.exists() else []
    dead = sorted(p for p in raw.glob("*_dead.txt") if p.is_file()) if raw.exists() else []
    if valid_resumes:
        phase = "sampling"
    elif live:
        phase = "initializing_live_points"
    else:
        phase = "not_started"
    return {
        "resumable": bool(valid_resumes),
        "phase": phase,
        "resume_files": [p.name for p in resumes],
        "valid_resume_files": [p.name for p in valid_resumes],
        "live_files": [p.name for p in live],
        "dead_files": [p.name for p in dead],
    }


def _copy_regular_files(source: Path, destination: Path) -> list[str]:
    copied: list[str] = []
    for src in sorted(source.iterdir()):
        if src.is_symlink():
            raise CheckpointError(f"symlink not allowed in checkpoint source: {src.name}")
        if src.is_file():
            shutil.copy2(src, destination / src.name)
            copied.append(src.name)
    return copied


def _file_record(path: Path, relative: str) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise CheckpointError(f"invalid checkpoint file: {relative}")
    size = path.stat().st_size
    return {"path": relative, "size": size, "sha256": _sha256(path)}


def promote_checkpoint(raw: Path, bundle: Path, *, model: str, segment: int,
                       parent_digest: str | None, science_manifest: dict[str, Any],
                       runtime_manifest: dict[str, Any]) -> dict[str, Any]:
    raw, bundle = Path(raw), Path(bundle)
    state = inspect_raw_checkpoint(raw)
    if not state["resumable"]:
        raise CheckpointError("no non-empty data resume file available for promotion")
    tmp = bundle.with_name(bundle.name + ".tmp")
    if tmp.exists():
        shutil.rmtree(tmp)
    (tmp / "raw").mkdir(parents=True)
    _copy_regular_files(raw, tmp / "raw")
    (tmp / "science_manifest.json").write_text(
        json.dumps(science_manifest, indent=2, sort_keys=True), encoding="utf-8")
    (tmp / "runtime_manifest.json").write_text(
        json.dumps(runtime_manifest, indent=2, sort_keys=True), encoding="utf-8")

    records: list[dict[str, Any]] = []
    for path in sorted((tmp / "raw").iterdir()):
        records.append(_file_record(path, f"raw/{path.name}"))
    for name in ("science_manifest.json", "runtime_manifest.json"):
        records.append(_file_record(tmp / name, name))

    core = {
        "schema": "peer-checkpoint-v1",
        "model": model,
        "segment": int(segment),
        "parent_checkpoint_digest": parent_digest,
        "science_sha": sha256_json(science_manifest),
        "runtime_sha": sha256_json(runtime_manifest),
        "phase": state["phase"],
        "resumable": True,
        "files": records,
    }
    manifest = {**core, "checkpoint_digest": sha256_json(core)}
    (tmp / "checkpoint_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    if bundle.exists():
        shutil.rmtree(bundle)
    os.replace(tmp, bundle)
    return manifest


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise CheckpointError(f"invalid json: {path.name}") from exc
    if not isinstance(value, dict):
        raise CheckpointError(f"json object required: {path.name}")
    return value


def verify_bundle(bundle: Path, expected: dict[str, Any]) -> dict[str, Any]:
    bundle = Path(bundle)
    if not bundle.is_dir() or bundle.is_symlink():
        raise CheckpointError("checkpoint bundle directory is invalid")
    allowed = {"raw", "science_manifest.json", "runtime_manifest.json", "checkpoint_manifest.json",
               "chain.input.yaml", "chain.updated.yaml", "chain.stats", "segment_status.json"}
    names = {p.name for p in bundle.iterdir()}
    unexpected = sorted(names - allowed)
    if unexpected:
        raise CheckpointError(f"unexpected bundle entries: {unexpected}")
    for required in ("raw", "science_manifest.json", "runtime_manifest.json", "checkpoint_manifest.json"):
        if required not in names:
            raise CheckpointError(f"missing bundle entry: {required}")
    raw = bundle / "raw"
    if raw.is_symlink() or not raw.is_dir():
        raise CheckpointError("raw checkpoint directory is invalid")
    if any(p.is_symlink() for p in raw.iterdir()):
        raise CheckpointError("symlink not allowed in raw checkpoint")

    manifest = _load_json(bundle / "checkpoint_manifest.json")
    for key, manifest_key in (("model", "model"), ("science_sha", "science_sha"),
                              ("runtime_sha", "runtime_sha"), ("parent_digest", "parent_checkpoint_digest")):
        if key in expected and manifest.get(manifest_key) != expected[key]:
            raise CheckpointError(f"{manifest_key} mismatch")
    core = {k: v for k, v in manifest.items() if k != "checkpoint_digest"}
    if manifest.get("checkpoint_digest") != sha256_json(core):
        raise CheckpointError("checkpoint manifest digest mismatch")

    for record in manifest.get("files", []):
        rel = record.get("path")
        if not isinstance(rel, str) or rel.startswith("/") or ".." in Path(rel).parts:
            raise CheckpointError("unsafe checkpoint path")
        path = bundle / rel
        if path.is_symlink() or not path.is_file():
            raise CheckpointError(f"missing checkpoint file: {rel}")
        if path.stat().st_size != record.get("size"):
            raise CheckpointError(f"size mismatch for {rel}")
        if _sha256(path) != record.get("sha256"):
            raise CheckpointError(f"hash mismatch for {rel}")

    science = _load_json(bundle / "science_manifest.json")
    runtime = _load_json(bundle / "runtime_manifest.json")
    if sha256_json(science) != manifest.get("science_sha"):
        raise CheckpointError("science manifest hash mismatch")
    if sha256_json(runtime) != manifest.get("runtime_sha"):
        raise CheckpointError("runtime manifest hash mismatch")
    if not inspect_raw_checkpoint(raw)["resumable"]:
        raise CheckpointError("checkpoint contains no valid resume state")
    return manifest


def restore_bundle(bundle: Path, destination: Path, expected: dict[str, Any]) -> dict[str, Any]:
    manifest = verify_bundle(bundle, expected)
    bundle, destination = Path(bundle), Path(destination)
    tmp = destination.with_name(destination.name + ".restore-tmp")
    backup = destination.with_name(destination.name + ".restore-backup")
    for path in (tmp, backup):
        if path.exists():
            shutil.rmtree(path)
    tmp.mkdir(parents=True)
    _copy_regular_files(bundle / "raw", tmp)
    if destination.exists():
        os.replace(destination, backup)
    try:
        os.replace(tmp, destination)
    except Exception:
        if backup.exists() and not destination.exists():
            os.replace(backup, destination)
        raise
    if backup.exists():
        shutil.rmtree(backup)
    return manifest


# Compatibility aliases for non-production callers while migration is in progress.
def inspect_checkpoint(raw: Path) -> dict[str, Any]:
    return inspect_raw_checkpoint(raw)


def snapshot_checkpoint(raw: Path, out: Path) -> dict[str, Any]:
    state = inspect_raw_checkpoint(raw)
    if not state["resumable"]:
        return state
    science = {"schema": "legacy-snapshot"}
    runtime = {"schema": "legacy-snapshot"}
    return promote_checkpoint(raw, out, model="M1", segment=0, parent_digest=None,
                              science_manifest=science, runtime_manifest=runtime)
