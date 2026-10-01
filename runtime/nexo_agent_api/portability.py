"""Offline, byte-verified Tower exports. Never activates a writer or executor."""
from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import stat
import shutil
import tempfile
from pathlib import Path, PurePosixPath

from .live_tower import LIVE_TOWER_FILE_ID, _canonical, read_live_tower_bytes, verify_live_tower
from .tower_paths import fs_path

CONTRACT = "NEXO_PORTABLE_EXPORT_V1"
COVERAGE = {
    "embedded_entries": "ALL_EXACT_BYTES",
    "known_external_artifacts": "manifests/artifacts.json + pinned CAMB v2",
    "external_discovery": "PARTIAL_CONTRACT_CATALOG",
    "execution_readiness": "NOT_ATTESTED",
    "limit": "References, execution contracts, data_binding inputs and attachments require dependency audit; a citation is not a downloaded corpus.",
}
POLICY = {"writes": False, "schedules": False, "integrations": False,
          "proposal_replay": False, "mode": "ISOLATED_READ_ONLY"}

_WINDOWS_RESERVED = {
    "CON", "PRN", "AUX", "NUL", "CONIN$", "CONOUT$",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}
_WINDOWS_FORBIDDEN = set('<>"|?*')


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def safe_path(name):
    if not isinstance(name, str) or not name or "\\" in name:
        raise ValueError("invalid portable path")
    path = PurePosixPath(name)
    if path.is_absolute() or any(p in ("", ".", "..") for p in name.split("/")):
        raise ValueError("unsafe portable path")
    if name == "NEXO_TOWER_LIVE.json" or name.startswith(".nexo-"):
        raise ValueError("reserved portable path")
    return name


def _windows_path_key(name):
    """Return the path written by ``tower_paths.fs_path`` on Windows.

    Colons are deliberately escaped by the existing Tower path contract. Other
    Win32-invalid names fail before any restore starts. Case-folding catches two
    logical bundle entries that would address the same case-insensitive file.
    """
    parts = []
    for part in name.split("/"):
        if part[-1:] in {" ", "."}:
            raise ValueError("unsafe Windows portable path")
        if any(ord(char) < 32 or char in _WINDOWS_FORBIDDEN for char in part):
            raise ValueError("unsafe Windows portable path")
        if part.split(".", 1)[0].upper() in _WINDOWS_RESERVED:
            raise ValueError("reserved Windows portable path")
        parts.append(part.replace("%", "%25").replace(":", "%3A").casefold())
    return "/".join(parts)


def validate_portable_paths(files):
    if not isinstance(files, dict):
        raise ValueError("portable files must be an object")
    seen = {}
    for name in files:
        safe_path(name)
        key = _windows_path_key(name)
        if key in seen:
            raise ValueError(f"portable path collision: {seen[key]!r} and {name!r}")
        seen[key] = name
    for key, name in seen.items():
        parts = key.split("/")
        for index in range(1, len(parts)):
            prefix = "/".join(parts[:index])
            if prefix in seen:
                raise ValueError(f"portable file/directory collision: {seen[prefix]!r} and {name!r}")


def entry_bytes(entry):
    encoding = entry.get("encoding")
    if encoding == "json":
        return (json.dumps(entry["value"], ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode()
    if encoding == "text":
        value = entry.get("data", entry.get("value"))
        if not isinstance(value, str):
            raise ValueError("text entry is not a string")
        return value.encode()
    if encoding == "base64":
        return base64.b64decode(entry["data"], validate=True)
    raise ValueError(f"unsupported portable encoding: {encoding}")


def inventory(bundle):
    validate_portable_paths(bundle["files"])
    files, references, identities = [], [], []
    def walk(value, path, pointer=""):
        if isinstance(value, dict):
            for key, item in sorted(value.items()):
                where = pointer + "/" + key.replace("~", "~0").replace("/", "~1")
                if isinstance(item, str):
                    if key == "id" or key.endswith("_id"):
                        identities.append({"path": path, "pointer": where, "value": item})
                    if key.endswith(("_ref", "_refs", "_url", "_uri")) or key in {"ref", "url", "uri", "drive_file_id"}:
                        references.append({"path": path, "pointer": where, "value": item})
                if isinstance(item, list) and (key.endswith(("_refs", "_ids")) or key in {"relations", "depends_on"}):
                    for i, ref in enumerate(item):
                        if isinstance(ref, str):
                            references.append({"path": path, "pointer": where + "/" + str(i), "value": ref})
                walk(item, path, where)
        elif isinstance(value, list):
            for i, item in enumerate(value):
                walk(item, path, pointer + "/" + str(i))
    for path, entry in sorted(bundle["files"].items()):
        safe_path(path)
        raw = entry_bytes(entry)
        files.append({"path": path, "encoding": entry["encoding"], "bytes": len(raw), "sha256": digest(raw),
                      "receipt": path.startswith("mutations/receipts/")})
        if entry["encoding"] == "json":
            walk(entry["value"], path)
    return {"files": files, "identities": identities, "references": references}


def _strict_bundle(raw):
    bundle = read_live_tower_bytes(raw)
    fingerprint = verify_live_tower(bundle)
    if bundle.get("revision") != fingerprint or bundle.get("state_fingerprint") != fingerprint:
        raise ValueError("SOURCE_DECLARED_HASH_MISMATCH: export acceptance requires exact hashes")
    if bundle.get("stable_file_id") != LIVE_TOWER_FILE_ID:
        raise ValueError("SOURCE_CANONICAL_FILE_ID_MISMATCH")
    return bundle


def _dependencies(bundle):
    # Artifact registry is data-driven; references to papers remain references,
    # in accordance with EVIDENCE_REFERENCE_V06's store-reference-not-corpus rule.
    registry = bundle["files"].get("manifests/artifacts.json", {}).get("value", {}).get("artifacts", {})
    result = []
    for identity, artifact in sorted(registry.items()):
        if not isinstance(artifact, dict) or artifact.get("storage") not in {"drive", "github_actions", "external"}:
            continue
        result.append({"id": identity, "ref": artifact.get("ref"), "sha256": artifact.get("artifact_digest"),
                       "status": "MISSING_BYTES", "reason": "external artifact not embedded in live Tower"})
    camb = json.loads((Path(__file__).parents[1] / "portable_camb/PORT_MANIFEST.v2.json").read_text())
    result.append({"id": "peer.camb.exact_v2", "ref": camb["drive_file_id"], "sha256": camb["archive_sha256"],
                   "status": "MISSING_BYTES", "reason": "private runtime archive required for CAMB execution"})
    return result


def export_tower(raw: bytes, destination, *, attachments=None, source_revision=None):
    """Create a new private export; attachments maps dependency IDs to local bytes."""
    bundle = _strict_bundle(raw)
    contents = inventory(bundle)
    destination = Path(destination).absolute()
    if destination.exists():
        raise FileExistsError(destination)
    dependencies = _dependencies(bundle)
    supplied = attachments or {}
    unknown = set(supplied) - {d["id"] for d in dependencies}
    if unknown:
        raise ValueError("attachment IDs absent from dependency inventory")
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".nexo-export-", dir=destination.parent))
    try:
        (staging / "source.bin").write_bytes(raw)
        for dep in dependencies:
            if dep["id"] not in supplied:
                continue
            data = Path(supplied[dep["id"]]).read_bytes()
            expected = (dep.get("sha256") or "").removeprefix("sha256:")
            if not re.fullmatch(r"[0-9a-f]{64}", expected) or digest(data) != expected:
                raise ValueError("DEPENDENCY_HASH_MISMATCH_OR_UNPINNED: " + dep["id"])
            name = "objects/" + expected
            (staging / "objects").mkdir(exist_ok=True)
            (staging / name).write_bytes(data)
            dep.update(status="INCLUDED", path=name, bytes=len(data))
            dep.pop("reason", None)
        manifest = {"contract": CONTRACT, "source_sha256": digest(raw), "source_bytes": len(raw),
                    "source_revision": source_revision, "state_fingerprint": bundle["state_fingerprint"],
                    "source_authentication": ("AUTHORIZED_DRIVE_HEAD" if source_revision else "LOCAL_BYTES_UNAUTHENTICATED"),
                    "policy": POLICY, "coverage": COVERAGE, "inventory": contents, "dependencies": dependencies,
                    "completeness": "COMPLETE_KNOWN_DEPENDENCIES" if all(d["status"] == "INCLUDED" for d in dependencies) else "INCOMPLETE_EXTERNAL_BYTES"}
        encoded = _canonical(manifest) + b"\n"
        (staging / "manifest.json").write_bytes(encoded)
        (staging / "manifest.sha256").write_text(digest(encoded) + "\n")
        verify_export(staging)
        _seal(staging)
        _publish_directory_noclobber(staging, destination)
        return {"path": str(destination), "manifest_sha256": digest(encoded), "completeness": manifest["completeness"],
                "file_count": len(contents["files"]), "missing_dependencies": sum(d["status"] != "INCLUDED" for d in dependencies)}
    except BaseException:
        # Failed staging only; never remove an existing user destination.
        if staging.exists():
            for p in staging.rglob("*"):
                p.chmod(0o700 if p.is_dir() else 0o600)
            staging.chmod(0o700)
            shutil.rmtree(staging)
        raise


def verify_export(directory, *, expected_manifest_sha256=None):
    root = Path(directory)
    if root.is_symlink() or any(not (stat.S_ISREG(p.lstat().st_mode) or stat.S_ISDIR(p.lstat().st_mode)) for p in root.rglob("*")):
        raise ValueError("symlinks and special files forbidden in portable export")
    encoded = (root / "manifest.json").read_bytes()
    actual = digest(encoded)
    sidecar = (root / "manifest.sha256").read_text().strip()
    if not re.fullmatch(r"[0-9a-f]{64}", sidecar) or sidecar != actual:
        raise ValueError("MANIFEST_HASH_MISMATCH")
    if expected_manifest_sha256 is not None and actual != expected_manifest_sha256:
        raise ValueError("MANIFEST_HASH_MISMATCH")
    manifest = json.loads(encoded)
    if manifest.get("contract") != CONTRACT or manifest.get("policy") != POLICY or manifest.get("coverage") != COVERAGE:
        raise ValueError("unsupported portable contract or unsafe policy")
    raw = (root / "source.bin").read_bytes()
    if digest(raw) != manifest["source_sha256"] or len(raw) != manifest["source_bytes"]:
        raise ValueError("SOURCE_BYTES_MISMATCH")
    bundle = _strict_bundle(raw)
    if inventory(bundle) != manifest["inventory"] or bundle["state_fingerprint"] != manifest["state_fingerprint"]:
        raise ValueError("INVENTORY_MISMATCH")
    expected_deps = _dependencies(bundle)
    if len(expected_deps) != len(manifest["dependencies"]):
        raise ValueError("DEPENDENCY_INVENTORY_MISMATCH")
    expected_files = {"source.bin", "manifest.json", "manifest.sha256"}
    for original, dep in zip(expected_deps, manifest["dependencies"]):
        if any(dep.get(k) != original[k] for k in ("id", "ref", "sha256")):
            raise ValueError("DEPENDENCY_INVENTORY_MISMATCH")
        if dep["status"] == "INCLUDED":
            sha = dep["sha256"].removeprefix("sha256:")
            name = "objects/" + sha
            if not re.fullmatch(r"[0-9a-f]{64}", sha) or dep.get("path") != name:
                raise ValueError("DEPENDENCY_PATH_MISMATCH")
            data = (root / name).read_bytes()
            if digest(data) != sha or len(data) != dep["bytes"]:
                raise ValueError("DEPENDENCY_BYTES_MISMATCH")
            expected_files.add(name)
        elif dep != original:
            raise ValueError("DEPENDENCY_STATUS_MISMATCH")
    completeness = "COMPLETE_KNOWN_DEPENDENCIES" if all(d["status"] == "INCLUDED" for d in manifest["dependencies"]) else "INCOMPLETE_EXTERNAL_BYTES"
    if manifest["completeness"] != completeness:
        raise ValueError("COMPLETENESS_MISMATCH")
    if {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()} != expected_files:
        raise ValueError("UNEXPECTED_EXPORT_FILES")
    return manifest


def _seal(root):
    for path in root.rglob("*"):
        path.chmod(0o500 if path.is_dir() else 0o400)
    root.chmod(0o500)


def _publish_directory_noclobber(staging, destination):
    """Publish a verified directory without ever replacing an existing path.

    ``rename(2)`` replaces an empty directory on POSIX. Reserving the final name
    with mkdir is the portable no-clobber primitive; children are already sealed
    and verified before they are moved into that private reservation.
    """
    staging, destination = Path(staging), Path(destination)
    destination.mkdir(mode=0o700)
    for path in staging.rglob("*"):
        if path.is_dir():
            path.chmod(0o700)
    staging.chmod(0o700)
    moved = []
    try:
        for child in sorted(staging.iterdir(), key=lambda path: path.name):
            target = destination / child.name
            os.rename(child, target)
            moved.append((target, child))
        staging.rmdir()
        _seal(destination)
    except BaseException:
        for target, original in reversed(moved):
            try:
                os.rename(target, original)
            except OSError:
                pass
        try:
            destination.rmdir()
        except OSError:
            pass
        raise


def restore_export(directory, destination, *, allow_incomplete=False, expected_manifest_sha256=None):
    manifest = verify_export(directory, expected_manifest_sha256=expected_manifest_sha256)
    if manifest["completeness"] != "COMPLETE_KNOWN_DEPENDENCIES" and not allow_incomplete:
        raise ValueError("INCOMPLETE_EXPORT: use --allow-incomplete for explicit data-only inspection")
    target = Path(destination).absolute()
    if target.exists():
        raise FileExistsError(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".nexo-restore-", dir=target.parent))
    try:
        raw = (Path(directory) / "source.bin").read_bytes()
        bundle = _strict_bundle(raw)
        for row in manifest["inventory"]["files"]:
            path = fs_path(staging, row["path"])
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(entry_bytes(bundle["files"][row["path"]]))
            if digest(path.read_bytes()) != row["sha256"]:
                raise ValueError("RESTORE_READBACK_MISMATCH")
        (staging / "NEXO_TOWER_LIVE.json").write_bytes(raw)
        shutil.copytree(directory, staging / ".nexo-export")
        (staging / ".nexo-isolated.json").write_bytes(_canonical({"contract": CONTRACT, **POLICY,
            "completeness": manifest["completeness"], "manifest_sha256": digest((Path(directory) / "manifest.json").read_bytes())}))
        _seal(staging)
        _publish_directory_noclobber(staging, target)
        return {"path": str(target), "status": "RESTORED_READ_ONLY", "file_count": len(manifest["inventory"]["files"]),
                "completeness": manifest["completeness"], "policy": POLICY}
    except BaseException:
        for p in staging.rglob("*"):
            p.chmod(0o700 if p.is_dir() else 0o600)
        staging.chmod(0o700)
        shutil.rmtree(staging)
        raise
