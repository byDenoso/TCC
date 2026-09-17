from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tarfile
import tempfile
import urllib.request
import zipfile
from pathlib import Path
from typing import Mapping


class PortableCambError(RuntimeError):
    pass


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_extract_tar(archive: Path, destination: Path) -> None:
    destination_resolved = destination.resolve()
    with tarfile.open(archive, "r:*") as handle:
        for member in handle.getmembers():
            target = (destination / member.name).resolve()
            if destination_resolved not in target.parents and target != destination_resolved:
                raise PortableCambError(f"unsafe archive member: {member.name}")
        handle.extractall(destination)


def _safe_extract_zip(archive: Path, destination: Path) -> None:
    destination_resolved = destination.resolve()
    with zipfile.ZipFile(archive) as handle:
        for member in handle.infolist():
            target = (destination / member.filename).resolve()
            if destination_resolved not in target.parents and target != destination_resolved:
                raise PortableCambError(f"unsafe archive member: {member.filename}")
        handle.extractall(destination)


def _safe_extract_zstd_tar(archive: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    try:
        subprocess.run(
            ["tar", "--zstd", "-xf", str(archive), "-C", str(destination)],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise PortableCambError(f"zstd tar extraction failed: {exc}") from exc


def _find_payload(root: Path, *, recursive: bool) -> Path | None:
    candidates = [root / "payload", root]
    if recursive:
        candidates.extend(path.parent for path in root.rglob("peer-camb-python"))
    seen: set[Path] = set()
    for candidate in candidates:
        candidate = candidate.resolve()
        if candidate in seen:
            continue
        seen.add(candidate)
        if (candidate / "peer-camb-python").is_file() and (candidate / "lib" / "camblib.so").is_file():
            return candidate
    return None


def _verify_payload(payload: Path, manifest: dict[str, object]) -> dict[str, str]:
    launcher = payload / "peer-camb-python"
    camblib = payload / "lib" / "camblib.so"
    expected_camblib = str(manifest.get("camblib_sha256") or "")
    if not expected_camblib:
        raise PortableCambError("manifest missing camblib_sha256")
    actual_camblib = _sha256(camblib)
    if actual_camblib != expected_camblib:
        raise PortableCambError(f"camblib SHA256 mismatch: {actual_camblib}")
    if not os.access(launcher, os.X_OK):
        launcher.chmod(launcher.stat().st_mode | 0o111)
    return {
        "NEXO_CAPABILITY_PEER_CAMB_EXACT_V2": "READY",
        "NEXO_CAPABILITY_PEER_CAMB_EXACT_V2_LAUNCHER": str(launcher),
        "NEXO_PEER_CAMB_RUNTIME_ROOT": str(payload),
        "NEXO_PEER_CAMB_VERSION": str(manifest.get("camb_version") or ""),
        "NEXO_PEER_COSMOREC_VERSION": str(manifest.get("cosmorec_version") or ""),
        "NEXO_PEER_CAMB_CAMBLIB_SHA256": actual_camblib,
        "NEXO_PEER_CAMB_ARCHIVE_SHA256": str(manifest.get("archive_sha256") or ""),
    }


def _materialize_archive(archive: Path, manifest: dict[str, object], destination: Path) -> Path:
    expected_archive = str(manifest.get("archive_sha256") or "")
    if not expected_archive:
        raise PortableCambError("manifest missing archive_sha256")
    actual_archive = _sha256(archive)
    if actual_archive != expected_archive:
        raise PortableCambError(f"archive SHA256 mismatch: {actual_archive}")
    destination.mkdir(parents=True, exist_ok=True)
    if tarfile.is_tarfile(archive):
        _safe_extract_tar(archive, destination)
    elif zipfile.is_zipfile(archive):
        _safe_extract_zip(archive, destination)
    elif archive.name.endswith((".tar.zst", ".tzst", ".zst")):
        _safe_extract_zstd_tar(archive, destination)
    else:
        raise PortableCambError("unsupported portable CAMB archive format")
    payload = _find_payload(destination, recursive=True)
    if payload is None:
        raise PortableCambError("portable CAMB payload layout not found after extraction")
    return payload


def _download(url: str, destination: Path) -> Path:
    request = urllib.request.Request(url, headers={"User-Agent": "NEXO/portable-camb-v2"})
    try:
        with urllib.request.urlopen(request, timeout=120) as response, destination.open("wb") as output:
            shutil.copyfileobj(response, output)
    except Exception as exc:
        raise PortableCambError(f"portable CAMB download failed: {type(exc).__name__}: {exc}") from exc
    return destination


def prepare_portable_camb(
    env: Mapping[str, str] | None = None,
    *,
    runtime_root: str | Path | None = None,
) -> dict[str, str]:
    source_env = dict(os.environ if env is None else env)
    root = Path(runtime_root) if runtime_root is not None else Path(__file__).resolve().parent
    manifest_path = root / "PORT_MANIFEST.v2.json"
    if not manifest_path.is_file():
        raise PortableCambError(f"portable CAMB manifest missing: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema") != "peer-camb-platform-port-2":
        raise PortableCambError("unexpected portable CAMB manifest schema")

    expanded = _find_payload(root, recursive=False)
    if expanded is not None:
        return _verify_payload(expanded, manifest)

    archive_value = str(source_env.get("NEXO_PEER_CAMB_ARCHIVE") or "").strip()
    url_value = str(source_env.get("NEXO_PEER_CAMB_ARCHIVE_URL") or "").strip()
    if not archive_value and not url_value:
        raise PortableCambError("no portable CAMB source configured")

    temp_root = Path(tempfile.mkdtemp(prefix="nexo-peer-camb-"))
    archive = Path(archive_value).expanduser() if archive_value else temp_root / "portable-camb.tar.zst"
    if url_value:
        archive = _download(url_value, archive)
    if not archive.is_file():
        raise PortableCambError(f"portable CAMB archive missing: {archive}")

    payload = _materialize_archive(archive, manifest, temp_root / "expanded")
    return _verify_payload(payload, manifest)
