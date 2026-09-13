from __future__ import annotations

import hashlib
import json
import os
import shutil
from pathlib import Path
from typing import Any

from peer_decisive_followups.production_contract import sha256_json


class BootstrapStateError(RuntimeError):
    pass


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def inspect_bootstrap_state(path: Path) -> dict[str, Any]:
    path = Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size == 0:
        return {"valid": False, "path": str(path), "reason": "missing_or_empty"}
    try:
        with path.open("r", encoding="utf-8") as handle:
            magic = handle.readline().strip()
            compatibility = handle.readline().split()
    except Exception as exc:
        return {"valid": False, "path": str(path), "reason": f"read_error:{type(exc).__name__}"}
    if magic != "POLYCHORD_BOOTSTRAP_V1" or len(compatibility) != 4:
        return {"valid": False, "path": str(path), "reason": "invalid_header"}
    try:
        n_dims, n_derived, nlive, nprior = map(int, compatibility)
    except ValueError:
        return {"valid": False, "path": str(path), "reason": "invalid_compatibility"}
    return {
        "valid": True,
        "path": str(path),
        "size": path.stat().st_size,
        "sha256": _sha256(path),
        "nDims": n_dims,
        "nDerived": n_derived,
        "nlive": nlive,
        "nprior": nprior,
    }


def _json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception as exc:
        raise BootstrapStateError(f"invalid json: {Path(path).name}") from exc
    if not isinstance(value, dict):
        raise BootstrapStateError(f"json object required: {Path(path).name}")
    return value


def _record(path: Path, rel: str) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise BootstrapStateError(f"invalid bootstrap payload: {rel}")
    return {"path": rel, "size": path.stat().st_size, "sha256": _sha256(path)}


def _payload_files(bundle: Path) -> list[Path]:
    files: list[Path] = []
    for path in sorted(Path(bundle).rglob("*")):
        if path.is_symlink():
            raise BootstrapStateError(f"symlink not allowed: {path.relative_to(bundle)}")
        if path.is_file() and path.name != "bootstrap_manifest.json":
            files.append(path)
    return files


def promote_bootstrap_bundle(state_file: Path, bundle: Path, *, model: str, segment: int,
                             parent_digest: str | None, science_manifest: dict[str, Any],
                             runtime_manifest: dict[str, Any], output_prefix: Path | None = None,
                             status: dict[str, Any] | None = None) -> dict[str, Any]:
    state_file, bundle = Path(state_file), Path(bundle)
    state = inspect_bootstrap_state(state_file)
    if not state["valid"]:
        raise BootstrapStateError(f"invalid bootstrap state: {state.get('reason')}")
    tmp = bundle.with_name(bundle.name + ".tmp")
    if tmp.exists():
        shutil.rmtree(tmp)
    (tmp / "raw").mkdir(parents=True)
    shutil.copy2(state_file, tmp / "raw" / state_file.name)

    if output_prefix is not None:
        prefix = Path(output_prefix)
        cobaya = tmp / "cobaya"
        cobaya.mkdir()
        for suffix in (".input.yaml", ".updated.yaml"):
            src = Path(str(prefix) + suffix)
            if src.is_symlink() or not src.is_file() or src.stat().st_size == 0:
                raise BootstrapStateError(f"missing Cobaya metadata: {src}")
            shutil.copy2(src, cobaya / src.name)

    (tmp / "science_manifest.json").write_text(
        json.dumps(science_manifest, indent=2, sort_keys=True), encoding="utf-8"
    )
    (tmp / "runtime_manifest.json").write_text(
        json.dumps(runtime_manifest, indent=2, sort_keys=True), encoding="utf-8"
    )
    if status is not None:
        (tmp / "segment_status.json").write_text(
            json.dumps(status, indent=2, sort_keys=True), encoding="utf-8"
        )

    records = [_record(path, path.relative_to(tmp).as_posix()) for path in _payload_files(tmp)]
    core = {
        "schema": "peer-bootstrap-checkpoint-v1",
        "model": model,
        "segment": int(segment),
        "parent_checkpoint_digest": parent_digest,
        "science_sha": sha256_json(science_manifest),
        "runtime_sha": sha256_json(runtime_manifest),
        "phase": "generating_live_points",
        "resumable_native": False,
        "files": records,
    }
    manifest = {**core, "checkpoint_digest": sha256_json(core)}
    (tmp / "bootstrap_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8"
    )
    if bundle.exists():
        shutil.rmtree(bundle)
    os.replace(tmp, bundle)
    return manifest


def verify_bootstrap_bundle(bundle: Path, expected: dict[str, Any]) -> dict[str, Any]:
    bundle = Path(bundle)
    if bundle.is_symlink() or not bundle.is_dir():
        raise BootstrapStateError("bootstrap bundle directory is invalid")
    allowed = {
        "raw", "cobaya", "science_manifest.json", "runtime_manifest.json",
        "bootstrap_manifest.json", "segment_status.json",
    }
    names = {p.name for p in bundle.iterdir()}
    unexpected = sorted(names - allowed)
    if unexpected:
        raise BootstrapStateError(f"unexpected bootstrap entries: {unexpected}")
    for required in ("raw", "science_manifest.json", "runtime_manifest.json", "bootstrap_manifest.json"):
        if required not in names:
            raise BootstrapStateError(f"missing bootstrap entry: {required}")

    manifest = _json(bundle / "bootstrap_manifest.json")
    identities = (
        ("model", "model"),
        ("science_sha", "science_sha"),
        ("runtime_sha", "runtime_sha"),
        ("parent_digest", "parent_checkpoint_digest"),
        ("checkpoint_digest", "checkpoint_digest"),
    )
    for expected_key, manifest_key in identities:
        if expected_key in expected and manifest.get(manifest_key) != expected[expected_key]:
            raise BootstrapStateError(f"{manifest_key.replace('_checkpoint', '')} mismatch")
    core = {k: v for k, v in manifest.items() if k != "checkpoint_digest"}
    if manifest.get("checkpoint_digest") != sha256_json(core):
        raise BootstrapStateError("bootstrap manifest digest mismatch")

    records = manifest.get("files")
    if not isinstance(records, list) or not records:
        raise BootstrapStateError("bootstrap file manifest is empty")
    recorded: set[str] = set()
    for record in records:
        rel = record.get("path")
        if not isinstance(rel, str) or rel.startswith("/") or ".." in Path(rel).parts:
            raise BootstrapStateError("unsafe bootstrap path")
        if rel in recorded:
            raise BootstrapStateError(f"duplicate bootstrap path: {rel}")
        recorded.add(rel)
        path = bundle / rel
        if path.is_symlink() or not path.is_file():
            raise BootstrapStateError(f"missing bootstrap file: {rel}")
        if path.stat().st_size != record.get("size"):
            raise BootstrapStateError(f"hash/size integrity mismatch for {rel}")
        if _sha256(path) != record.get("sha256"):
            raise BootstrapStateError(f"hash mismatch for {rel}")
    actual = {p.relative_to(bundle).as_posix() for p in _payload_files(bundle)}
    if actual != recorded:
        raise BootstrapStateError("bootstrap payload manifest mismatch")

    science = _json(bundle / "science_manifest.json")
    runtime = _json(bundle / "runtime_manifest.json")
    if sha256_json(science) != manifest.get("science_sha"):
        raise BootstrapStateError("science manifest hash mismatch")
    if sha256_json(runtime) != manifest.get("runtime_sha"):
        raise BootstrapStateError("runtime manifest hash mismatch")
    raw_files = list((bundle / "raw").glob("*.bootstrap"))
    if len(raw_files) != 1 or not inspect_bootstrap_state(raw_files[0])["valid"]:
        raise BootstrapStateError("bundle contains no valid pre-resume state")
    return manifest


def _restore_metadata(bundle: Path, output_dir: Path) -> None:
    source = bundle / "cobaya"
    if not source.exists():
        return
    if source.is_symlink() or not source.is_dir():
        raise BootstrapStateError("Cobaya metadata directory is invalid")
    output_dir.mkdir(parents=True, exist_ok=True)
    for src in sorted(source.iterdir()):
        if src.is_symlink() or not src.is_file():
            raise BootstrapStateError(f"invalid Cobaya metadata file: {src.name}")
        stage = output_dir / f".{src.name}.bootstrap-restore-tmp"
        shutil.copy2(src, stage)
        os.replace(stage, output_dir / src.name)


def restore_bootstrap_bundle(bundle: Path, destination_state: Path, expected: dict[str, Any],
                             output_dir: Path | None = None) -> dict[str, Any]:
    manifest = verify_bootstrap_bundle(bundle, expected)
    destination_state = Path(destination_state)
    raw_files = list((Path(bundle) / "raw").glob("*.bootstrap"))
    src = raw_files[0]
    destination_state.parent.mkdir(parents=True, exist_ok=True)
    stage = destination_state.with_name("." + destination_state.name + ".restore-tmp")
    if stage.exists():
        stage.unlink()
    shutil.copy2(src, stage)
    os.replace(stage, destination_state)
    if output_dir is not None:
        _restore_metadata(Path(bundle), Path(output_dir))
    return manifest
