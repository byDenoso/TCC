#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

PINNED_REPOSITORY = "https://github.com/kabeleh/iDM.git"
PINNED_REVISION = "dc55e59dec8f5c647df6e9d764f5c6960796e1df"
LCDM_INI = "ini/base_2018_plikHM_TTTEEE_lowl_lowE_lensing.ini"
IDM_INI = "ini/iDM.ini"
COBAYA_YAML = "Cobaya/MCMC/hyperbolic_Planck_PP_DESI_InitCond_Swamp_MCMC.yml"
EXPECTED_BLOBS = {
    IDM_INI: "43d8c23105cda3b854a9775d6048b847b2970398",
    COBAYA_YAML: "429a59adab6d1e7c2d7247733266d09ef463aba7",
    LCDM_INI: "3b6808a0d18b32cfbf21af798aad5a1255e6cf81",
}
EXPECTED_LIKELIHOODS = [
    "planck_2018_lowl.TT",
    "planck_2018_lowl.EE",
    "planck_2018_highl_plik.TTTEEE_lite_native",
    "planck_2018_lensing.native",
    "bao.desi_dr2",
    "sn.pantheonplus",
]
OUTPUT = Path("idm_preflight_result.json")


def run(cmd: list[str], *, cwd: Path | None = None, timeout: int = 300) -> dict[str, Any]:
    completed = subprocess.run(
        cmd,
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=timeout,
        check=False,
    )
    return {"argv": cmd, "exit_code": completed.returncode, "output_tail": completed.stdout[-12000:]}


def require_ok(stage: str, result: dict[str, Any], receipt: dict[str, Any]) -> None:
    receipt["stages"][stage] = result
    if result["exit_code"] != 0:
        raise RuntimeError(f"{stage} failed with exit {result['exit_code']}")


def prepare_runtime_dirs(repo: Path) -> None:
    (repo / "output").mkdir(parents=True, exist_ok=True)


def prepare_ini_output_dirs(repo: Path, ini_paths: list[str]) -> None:
    """Prepare parents for explicit CLASS roots and CLASS's default output/<ini-path> root."""
    for relative in ini_paths:
        ini_path = repo / relative
        explicit_root: Path | None = None
        for raw_line in ini_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.split("#", 1)[0].strip()
            if not line or "=" not in line:
                continue
            key, value = (part.strip() for part in line.split("=", 1))
            if key != "root":
                continue
            root_value = value.strip().strip('"').strip("'")
            root_path = Path(root_value)
            if root_path.is_absolute() or ".." in root_path.parts:
                raise RuntimeError(f"unsafe CLASS output root in {relative}: {root_value}")
            explicit_root = root_path
            break

        if explicit_root is None:
            default_root = Path("output") / Path(relative).with_suffix("")
            parent = default_root.parent
        else:
            parent = explicit_root.parent

        if str(parent) not in {"", "."}:
            (repo / parent).mkdir(parents=True, exist_ok=True)


def probe_distribution_version(distribution: str) -> str:
    """Read newly installed package metadata in a fresh interpreter process."""
    probe = run(
        [
            sys.executable,
            "-c",
            "import importlib.metadata,sys; print(importlib.metadata.version(sys.argv[1]))",
            distribution,
        ],
        timeout=30,
    )
    if probe["exit_code"] != 0:
        raise RuntimeError(f"package version probe failed for {distribution}: {probe['output_tail']}")
    return probe["output_tail"].strip().splitlines()[-1]


def git_blob(repo: Path, relative: str) -> str:
    result = run(["git", "hash-object", relative], cwd=repo, timeout=30)
    if result["exit_code"] != 0:
        raise RuntimeError(f"git hash-object failed for {relative}: {result['output_tail']}")
    return result["output_tail"].strip().splitlines()[-1]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    requested_revision = os.getenv("NEXO_PARAM_SOURCE_REVISION", PINNED_REVISION).strip()
    receipt: dict[str, Any] = {
        "schema": "nexo.idm_runtime_preflight.v1",
        "work_id": os.getenv("NEXO_WORK_ID"),
        "execution_id": os.getenv("NEXO_EXECUTION_ID"),
        "pinned_repository": PINNED_REPOSITORY,
        "pinned_revision": PINNED_REVISION,
        "requested_revision": requested_revision,
        "stages": {},
        "files": {},
        "cobaya": {},
        "status": "FAIL",
    }
    try:
        if requested_revision != PINNED_REVISION:
            raise RuntimeError("source revision is not the frozen iDM revision")
        with tempfile.TemporaryDirectory(prefix="nexo-idm-") as raw:
            root = Path(raw)
            repo = root / "idm"
            repo.mkdir()
            require_ok("git_init", run(["git", "init", "-q"], cwd=repo, timeout=30), receipt)
            require_ok("git_remote", run(["git", "remote", "add", "origin", PINNED_REPOSITORY], cwd=repo, timeout=30), receipt)
            require_ok("git_fetch", run(["git", "fetch", "--depth", "1", "origin", PINNED_REVISION], cwd=repo, timeout=180), receipt)
            require_ok("git_checkout", run(["git", "checkout", "--detach", "FETCH_HEAD"], cwd=repo, timeout=30), receipt)
            head = run(["git", "rev-parse", "HEAD"], cwd=repo, timeout=30)
            require_ok("git_revision", head, receipt)
            actual_revision = head["output_tail"].strip().splitlines()[-1]
            if actual_revision != PINNED_REVISION:
                raise RuntimeError(f"revision mismatch: {actual_revision}")
            receipt["actual_revision"] = actual_revision

            for relative, expected_blob in EXPECTED_BLOBS.items():
                path = repo / relative
                if not path.is_file():
                    raise RuntimeError(f"required frozen input missing: {relative}")
                actual_blob = git_blob(repo, relative)
                if actual_blob != expected_blob:
                    raise RuntimeError(f"blob mismatch for {relative}: {actual_blob}")
                receipt["files"][relative] = {"git_blob": actual_blob, "sha256": sha256(path), "bytes": path.stat().st_size}

            prepare_runtime_dirs(repo)
            prepare_ini_output_dirs(repo, [LCDM_INI, IDM_INI])
            require_ok("make_clean", run(["make", "clean"], cwd=repo, timeout=120), receipt)
            require_ok("compile_class", run(["make", "class", "-j2"], cwd=repo, timeout=600), receipt)
            if not (repo / "class").is_file():
                raise RuntimeError("CLASS binary missing after successful build")
            receipt["class_binary_sha256"] = sha256(repo / "class")
            require_ok("lcdm_smoke", run(["./class", LCDM_INI], cwd=repo, timeout=180), receipt)
            require_ok("idm_smoke", run(["./class", IDM_INI], cwd=repo, timeout=180), receipt)

            require_ok("install_cobaya_3_6_1", run([sys.executable, "-m", "pip", "install", "--disable-pip-version-check", "cobaya==3.6.1"], timeout=300), receipt)
            cobaya_version = probe_distribution_version("cobaya")
            if cobaya_version != "3.6.1":
                raise RuntimeError(f"Cobaya version mismatch: {cobaya_version}")
            receipt["cobaya"]["version"] = cobaya_version
            check_yaml = run([
                sys.executable, "-c",
                "import json,sys; from cobaya.yaml import yaml_load_file; d=yaml_load_file(sys.argv[1]); print(json.dumps(list((d.get('likelihood') or {}).keys())))",
                str(repo / COBAYA_YAML),
            ], timeout=60)
            require_ok("cobaya_parse", check_yaml, receipt)
            likelihoods = json.loads(check_yaml["output_tail"].strip().splitlines()[-1])
            if likelihoods != EXPECTED_LIKELIHOODS:
                raise RuntimeError(f"likelihood stack mismatch: {likelihoods}")
            receipt["cobaya"]["likelihoods"] = likelihoods

            packages = root / "cobaya-packages"
            install_check = run([
                sys.executable, "-m", "cobaya", "install", str(repo / COBAYA_YAML),
                "--packages-path", str(packages), "--skip", "classy", "--no-set-global", "--no-progress-bars",
            ], timeout=600)
            require_ok("cobaya_likelihood_resolution", install_check, receipt)
            receipt["cobaya"]["packages_path"] = str(packages)
            receipt["status"] = "PASS"
            return_code = 0
    except subprocess.TimeoutExpired as exc:
        receipt["error"] = f"timeout:{exc.cmd}"
        return_code = 124
    except Exception as exc:
        receipt["error"] = f"{type(exc).__name__}:{exc}"
        return_code = 1
    finally:
        OUTPUT.write_text(json.dumps(receipt, indent=2, sort_keys=True), encoding="utf-8")
        print(json.dumps(receipt, indent=2, sort_keys=True))
    return return_code


if __name__ == "__main__":
    raise SystemExit(main())
