from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

from peer_decisive_followups.runtime_contract import (
    ACT_COMMIT,
    build_runtime_manifest,
    verify_runtime_manifest,
)

REPO = "byDenoso/TCC"
RUNTIME_ARTIFACT = "validated-act-cosmorec-runtime-gslfix"
LIKELIHOOD_ARTIFACT = "official-likelihood-packages-v3"
EXPECTED_CAMB_WHEEL_SHA256 = "4e38c3771329b2d4f5c185f8d8d7a0f183178d5b07957f18f9008f90e7d4b79d"


class MaterializationError(RuntimeError):
    pass


def _run(cmd: list[str], *, cwd: Path | None = None) -> None:
    print("+", " ".join(map(str, cmd)), flush=True)
    subprocess.run(cmd, cwd=cwd, check=True)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _tree_sha256(root: Path) -> str:
    root = root.resolve()
    h = hashlib.sha256()
    files = sorted(p for p in root.rglob("*") if p.is_file() and not p.is_symlink())
    for path in files:
        rel = path.relative_to(root).as_posix().encode("utf-8")
        h.update(len(rel).to_bytes(8, "big"))
        h.update(rel)
        digest = bytes.fromhex(_sha256(path))
        h.update(digest)
    return h.hexdigest()


def _safe_extract(archive: tarfile.TarFile, destination: Path) -> None:
    destination = destination.resolve()
    for member in archive.getmembers():
        member_path = (destination / member.name).resolve()
        try:
            member_path.relative_to(destination)
        except ValueError as exc:
            raise MaterializationError(f"unsafe tar path: {member.name}") from exc
        if member.issym() or member.islnk():
            raise MaterializationError(f"links are not allowed in likelihood payload tar: {member.name}")
    archive.extractall(destination)


def _replace_directory_link(dst: Path, src: Path) -> None:
    if dst.is_symlink() or dst.is_file():
        dst.unlink()
    elif dst.is_dir():
        shutil.rmtree(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.symlink_to(src.resolve(), target_is_directory=True)


def materialize_runtime(*, source_run: str, work: Path, packages: Path,
                        manifest_path: Path) -> dict:
    work = Path(work).resolve()
    packages = Path(packages).resolve()
    workspace = packages.parent.resolve()
    manifest_path = Path(manifest_path).resolve()
    work.mkdir(parents=True, exist_ok=True)
    workspace.mkdir(parents=True, exist_ok=True)

    validated = work / "validated"
    payload = work / "payload"
    for path in (validated, payload):
        if path.exists():
            shutil.rmtree(path)
        path.mkdir(parents=True)

    _run([
        "gh", "run", "download", str(source_run), "--repo", REPO,
        "--name", RUNTIME_ARTIFACT, "--dir", str(validated),
    ])
    _run([
        "gh", "run", "download", str(source_run), "--repo", REPO,
        "--name", LIKELIHOOD_ARTIFACT, "--dir", str(payload),
    ])

    tar_path = payload / "official-likelihood-packages-v3.tar.gz"
    sums_path = payload / "official-likelihood-packages-v3.tar.gz.sha256"
    if not tar_path.is_file() or not sums_path.is_file():
        raise MaterializationError("official likelihood payload is incomplete")
    declared = sums_path.read_text(encoding="utf-8").split()[0].strip().lower()
    actual_tar_sha = _sha256(tar_path)
    if declared != actual_tar_sha:
        raise MaterializationError(
            f"likelihood payload sha256 mismatch: declared {declared}, actual {actual_tar_sha}"
        )

    if packages.exists():
        shutil.rmtree(packages)
    with tarfile.open(tar_path, "r:gz") as archive:
        _safe_extract(archive, workspace)
    if not packages.is_dir():
        raise MaterializationError(f"packages were not extracted to {packages}")

    wheels = sorted(validated.rglob("camb-*.whl"))
    databases = sorted(p for p in validated.rglob("Rec_database") if p.is_dir())
    developments = sorted(p for p in validated.rglob("Development") if p.is_dir())
    if len(wheels) != 1 or not databases or not developments:
        raise MaterializationError("validated CAMB/CosmoRec artifact is incomplete or ambiguous")
    wheel = wheels[0]
    wheel_sha = _sha256(wheel)
    if wheel_sha != EXPECTED_CAMB_WHEEL_SHA256:
        raise MaterializationError(
            f"CAMB wheel identity mismatch: expected {EXPECTED_CAMB_WHEEL_SHA256}, got {wheel_sha}"
        )

    shutil.rmtree(packages / "code" / "CAMB", ignore_errors=True)
    _run([sys.executable, "-m", "pip", "install", "--force-reinstall", "--no-deps", str(wheel)])

    database = databases[0]
    development = developments[0]
    for base in (work, workspace):
        _replace_directory_link(base / "Rec_database", database)
        _replace_directory_link(base / "Development", development)
        (base / "temp").mkdir(exist_ok=True)

    required = workspace / "Rec_database" / "Effective_Rates.HI" / "Effective_Rate_Tables.nS_3" / "res_state_list.dat"
    helium = workspace / "Development" / "Helium" / "Helium.Data.lite" / "He4_SS.dat"
    if not required.is_file() or not helium.is_file():
        raise MaterializationError("CosmoRec data binding failed")

    act = work / "act-lite"
    if act.exists():
        shutil.rmtree(act)
    _run(["git", "clone", "https://github.com/ACTCollaboration/DR6-ACT-lite.git", str(act)])
    _run(["git", "checkout", ACT_COMMIT], cwd=act)
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=act, text=True).strip()
    if head != ACT_COMMIT:
        raise MaterializationError(f"ACT-lite commit mismatch: {head}")
    _run([sys.executable, "-m", "pip", "install", "-e", str(act)])

    import camb
    from camb import recombination

    if getattr(camb, "__version__", None) != "1.6.6":
        raise MaterializationError(f"unexpected CAMB version: {getattr(camb, '__version__', None)}")
    if type(recombination.CosmoRec()).__name__ != "CosmoRec":
        raise MaterializationError("CosmoRec recombination model is unavailable")

    manifest = build_runtime_manifest(
        payload_hashes={
            "camb_wheel": wheel_sha,
            "cosmorec_rec_database_tree": _tree_sha256(database),
            "cosmorec_development_tree": _tree_sha256(development),
            "official_likelihood_tar": actual_tar_sha,
        },
        source={
            "repo": REPO,
            "run_id": str(source_run),
            "runtime_artifact": RUNTIME_ARTIFACT,
            "likelihood_artifact": LIKELIHOOD_ARTIFACT,
        },
    )
    manifest = verify_runtime_manifest(manifest)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    import json
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Materialize the validated PEER CAMB/CosmoRec + likelihood runtime.")
    parser.add_argument("--source-run", default="34561868964")
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--packages", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()
    manifest = materialize_runtime(
        source_run=args.source_run,
        work=args.work,
        packages=args.packages,
        manifest_path=args.manifest,
    )
    print(manifest["identity_sha256"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
