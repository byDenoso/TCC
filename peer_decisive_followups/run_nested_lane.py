#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import os
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

REPO = "byDenoso/TCC"
SOURCE_RUN = "30455821484"
ACT_COMMIT = "627aeafb88ae5ad1aa66b406bea2d65cfa66a27d"


def run(cmd, *, cwd=None, timeout=None, check=True, stdout=None, stderr=None):
    print("+", " ".join(map(str, cmd)), flush=True)
    return subprocess.run(
        cmd,
        cwd=cwd,
        timeout=timeout,
        check=check,
        text=True,
        stdout=stdout,
        stderr=stderr,
    )


def _replace_directory_link(dst: Path, src: Path) -> None:
    if dst.is_symlink() or dst.is_file():
        dst.unlink()
    elif dst.is_dir():
        shutil.rmtree(dst)
    dst.symlink_to(src.resolve(), target_is_directory=True)


def install_runtime(work: Path, packages: Path) -> None:
    """Install the validated runtime into the paths used by the configs.

    The official package tar contains a top-level ``packages`` directory, so it
    must be extracted into ``packages.parent``. CosmoRec databases are linked
    into ``work``, which is also the working directory used by PolyChord.
    """
    workspace = packages.parent.resolve()
    work.mkdir(parents=True, exist_ok=True)
    workspace.mkdir(parents=True, exist_ok=True)

    run([
        "gh", "run", "download", SOURCE_RUN, "--repo", REPO,
        "--name", "validated-act-cosmorec-runtime-gslfix",
        "--dir", str(work / "validated"),
    ])
    run([
        "gh", "run", "download", SOURCE_RUN, "--repo", REPO,
        "--name", "official-likelihood-packages-v3",
        "--dir", str(work / "payload"),
    ])
    sums = work / "payload" / "official-likelihood-packages-v3.tar.gz.sha256"
    run(["sha256sum", "-c", sums.name], cwd=sums.parent)
    with tarfile.open(work / "payload" / "official-likelihood-packages-v3.tar.gz", "r:gz") as tf:
        tf.extractall(workspace)
    if not packages.is_dir():
        raise RuntimeError(f"Official packages were not extracted to {packages}")

    wheels = list((work / "validated").rglob("camb-*.whl"))
    dbs = list((work / "validated").rglob("Rec_database"))
    devs = list((work / "validated").rglob("Development"))
    if not wheels or not dbs or not devs:
        raise RuntimeError("validated CAMB payload incomplete")

    shutil.rmtree(packages / "code" / "CAMB", ignore_errors=True)
    run([sys.executable, "-m", "pip", "install", "--force-reinstall", "--no-deps", str(wheels[0])])
    _replace_directory_link(work / "Rec_database", dbs[0])
    _replace_directory_link(work / "Development", devs[0])
    (work / "temp").mkdir(exist_ok=True)

    act = work / "act-lite"
    if act.exists():
        shutil.rmtree(act)
    run(["git", "clone", "https://github.com/ACTCollaboration/DR6-ACT-lite.git", str(act)])
    run(["git", "checkout", ACT_COMMIT], cwd=act)
    run([sys.executable, "-m", "pip", "install", "-e", str(act)])


def parse_status(root: Path, code: int) -> dict:
    import re

    stats = list(root.rglob("*.stats")) + list(root.rglob("*stats*.txt"))
    text = "\n".join(path.read_text(errors="replace") for path in stats)
    values = []
    patterns = [
        r"log\(Z\)\s*=\s*([-+0-9.eE]+)\s*\+/-\s*([-+0-9.eE]+)",
        r"logZ\s*[:=]\s*([-+0-9.eE]+).*?([-+0-9.eE]+)",
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, text, re.S):
            try:
                values.append({"logZ": float(match.group(1)), "logZstd": float(match.group(2))})
            except ValueError:
                pass
    return {
        "status": "COMPLETE" if code == 0 and values else "INCOMPLETE",
        "exit_code": code,
        "stats_files": [str(path) for path in stats],
        "evidence": values[-1] if values else None,
    }


def timed_run(config: Path, logroot: Path, seconds: int, cwd: Path) -> tuple[int, dict]:
    logroot.mkdir(parents=True, exist_ok=True)
    with (logroot / "stdout.log").open("w") as out, (logroot / "stderr.log").open("w") as err:
        try:
            process = run(
                ["mpirun", "--oversubscribe", "-np", "4", "cobaya-run", str(config)],
                cwd=cwd,
                timeout=seconds,
                check=False,
                stdout=out,
                stderr=err,
            )
            code = process.returncode
        except subprocess.TimeoutExpired:
            code = 124
    (logroot / "exit_code.txt").write_text(str(code) + "\n", encoding="utf-8")
    status = parse_status(logroot, code)
    (logroot / "nested_status.json").write_text(json.dumps(status, indent=2), encoding="utf-8")
    return code, status


def normalized_evidence(data: dict, prior: dict) -> dict | None:
    if data.get("status") != "COMPLETE" or prior.get("status") != "COMPLETE":
        return None
    return {
        "logZ": data["evidence"]["logZ"] - prior["evidence"]["logZ"],
        # Cobaya's documented external-prior normalization uses a conservative
        # sum of the two quoted evidence uncertainties.
        "logZstd": data["evidence"]["logZstd"] + prior["evidence"]["logZstd"],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", choices=["M0", "M1", "M2", "M3"], required=True)
    parser.add_argument("--science", type=Path, required=True)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--packages", type=Path, required=True)
    args = parser.parse_args()

    args.work = args.work.resolve()
    args.packages = args.packages.resolve()
    args.work.mkdir(parents=True, exist_ok=True)
    install_runtime(args.work, args.packages)

    index = ["M0", "M1", "M2", "M3"].index(args.model)
    run([
        sys.executable,
        "peer_decisive_followups/build_nested_config.py",
        "--science", str(args.science.resolve()),
        "--model", args.model,
        "--packages", str(args.packages),
        "--root", str(args.work / f"nested_{args.model}"),
        "--seed", str(2026076100 + index),
    ])
    root = args.work / f"nested_{args.model}"
    _, data = timed_run(root / "data.yaml", root / "data", 15000, cwd=args.work)
    _, prior = timed_run(root / "prior_volume.yaml", root / "prior_volume", 4200, cwd=args.work)
    normalized = normalized_evidence(data, prior)
    complete = normalized is not None
    result = {
        "model": args.model,
        "status": "COMPLETE" if complete else "INCOMPLETE",
        "data": data,
        "prior_volume": prior,
        "normalized": normalized,
        "normalization_convention": "Cobaya external-prior unit-likelihood correction",
    }
    (root / "normalized_evidence.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0 if complete else 2


if __name__ == "__main__":
    raise SystemExit(main())
