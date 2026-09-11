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


def _all_payload_files(bundle: Path) -> list[Path]:
    files: list[Path] = []
    for path in sorted(bundle.rglob("*")):
        if path.is_symlink():
            raise CheckpointError(f"symlink not allowed in bundle: {path.relative_to(bundle)}")
        if path.is_file() and path.name != "checkpoint_manifest.json":
            files.append(path)
    return files


def promote_checkpoint(raw: Path, bundle: Path, *, model: str, segment: int,
                       parent_digest: str | None, science_manifest: dict[str, Any],
                       runtime_manifest: dict[str, Any], output_prefix: Path | None = None,
                       status: dict[str, Any] | None = None) -> dict[str, Any]:
    raw, bundle = Path(raw), Path(bundle)
    state = inspect_raw_checkpoint(raw)
    if not state["resumable"]:
        raise CheckpointError("no non-empty data resume file available for promotion")
    tmp = bundle.with_name(bundle.name + ".tmp")
    if tmp.exists():
        shutil.rmtree(tmp)
    (tmp / "raw").mkdir(parents=True)
    _copy_regular_files(raw, tmp / "raw")

    if output_prefix is not None:
        prefix = Path(output_prefix)
        cobaya = tmp / "cobaya"
        cobaya.mkdir()
        for suffix in (".input.yaml", ".updated.yaml"):
            src = Path(str(prefix) + suffix)
            if not src.is_file() or src.stat().st_size == 0:
                raise CheckpointError(f"missing Cobaya resume metadata: {src}")
            shutil.copy2(src, cobaya / src.name)

    (tmp / "science_manifest.json").write_text(
        json.dumps(science_manifest, indent=2, sort_keys=True), encoding="utf-8")
    (tmp / "runtime_manifest.json").write_text(
        json.dumps(runtime_manifest, indent=2, sort_keys=True), encoding="utf-8")
    if status is not None:
        (tmp / "segment_status.json").write_text(
            json.dumps(status, indent=2, sort_keys=True), encoding="utf-8")

    records = [
        _file_record(path, path.relative_to(tmp).as_posix())
        for path in _all_payload_files(tmp)
    ]
    core = {
        "schema": "peer-checkpoint-v2",
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
    allowed = {
        "raw", "cobaya", "science_manifest.json", "runtime_manifest.json",
        "checkpoint_manifest.json", "segment_status.json",
    }
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

    manifest = _load_json(bundle / "checkpoint_manifest.json")
    identity_fields = (
        ("model", "model"),
        ("science_sha", "science_sha"),
        ("runtime_sha", "runtime_sha"),
        ("parent_digest", "parent_checkpoint_digest"),
        ("checkpoint_digest", "checkpoint_digest"),
    )
    for key, manifest_key in identity_fields:
        if key in expected and manifest.get(manifest_key) != expected[key]:
            raise CheckpointError(f"{manifest_key} mismatch")
    core = {k: v for k, v in manifest.items() if k != "checkpoint_digest"}
    if manifest.get("checkpoint_digest") != sha256_json(core):
        raise CheckpointError("checkpoint manifest digest mismatch")

    records = manifest.get("files", [])
    if not isinstance(records, list) or not records:
        raise CheckpointError("checkpoint file manifest is empty")
    recorded_paths: set[str] = set()
    for record in records:
        rel = record.get("path")
        if not isinstance(rel, str) or rel.startswith("/") or ".." in Path(rel).parts:
            raise CheckpointError("unsafe checkpoint path")
        if rel in recorded_paths:
            raise CheckpointError(f"duplicate checkpoint path: {rel}")
        recorded_paths.add(rel)
        path = bundle / rel
        if path.is_symlink() or not path.is_file():
            raise CheckpointError(f"missing checkpoint file: {rel}")
        if path.stat().st_size != record.get("size"):
            raise CheckpointError(f"hash/size integrity mismatch for {rel}")
        if _sha256(path) != record.get("sha256"):
            raise CheckpointError(f"hash mismatch for {rel}")

    actual_paths = {path.relative_to(bundle).as_posix() for path in _all_payload_files(bundle)}
    if actual_paths != recorded_paths:
        extra = sorted(actual_paths - recorded_paths)
        missing = sorted(recorded_paths - actual_paths)
        raise CheckpointError(f"checkpoint payload manifest mismatch: extra={extra}, missing={missing}")

    science = _load_json(bundle / "science_manifest.json")
    runtime = _load_json(bundle / "runtime_manifest.json")
    if sha256_json(science) != manifest.get("science_sha"):
        raise CheckpointError("science manifest hash mismatch")
    if sha256_json(runtime) != manifest.get("runtime_sha"):
        raise CheckpointError("runtime manifest hash mismatch")
    if not inspect_raw_checkpoint(raw)["resumable"]:
        raise CheckpointError("checkpoint contains no valid resume state")
    return manifest


def _restore_cobaya_metadata(bundle: Path, output_dir: Path) -> None:
    source = bundle / "cobaya"
    if not source.exists():
        return
    if source.is_symlink() or not source.is_dir():
        raise CheckpointError("Cobaya metadata directory is invalid")
    output_dir.mkdir(parents=True, exist_ok=True)
    backups: list[tuple[Path, Path]] = []
    staged: list[tuple[Path, Path]] = []
    try:
        for src in sorted(source.iterdir()):
            if src.is_symlink() or not src.is_file():
                raise CheckpointError(f"invalid Cobaya metadata file: {src.name}")
            dst = output_dir / src.name
            stage = output_dir / f".{src.name}.restore-tmp"
            backup = output_dir / f".{src.name}.restore-backup"
            for old in (stage, backup):
                if old.exists():
                    old.unlink()
            shutil.copy2(src, stage)
            if dst.exists():
                os.replace(dst, backup)
                backups.append((backup, dst))
            staged.append((stage, dst))
        for stage, dst in staged:
            os.replace(stage, dst)
        for backup, _ in backups:
            if backup.exists():
                backup.unlink()
    except Exception:
        for stage, _ in staged:
            if stage.exists():
                stage.unlink()
        for backup, dst in reversed(backups):
            if backup.exists():
                if dst.exists():
                    dst.unlink()
                os.replace(backup, dst)
        raise


def restore_bundle(bundle: Path, destination: Path, expected: dict[str, Any],
                   output_dir: Path | None = None) -> dict[str, Any]:
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
        _restore_cobaya_metadata(bundle, Path(output_dir) if output_dir else destination.parent)
    except Exception:
        if destination.exists():
            shutil.rmtree(destination)
        if backup.exists():
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
