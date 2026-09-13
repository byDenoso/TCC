from __future__ import annotations

import copy
import os
import subprocess
from pathlib import Path

import pytest
import yaml

from peer_decisive_followups.bootstrap_state import (
    promote_bootstrap_bundle,
    restore_bootstrap_bundle,
)
from peer_decisive_followups.production_contract import sha256_json


pytestmark = pytest.mark.integration


def _run(cmd: list[str], cwd: Path, *, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=cwd, env=env, text=True, capture_output=True)


def _accepted(state: Path) -> int:
    lines = state.read_text(encoding="utf-8").splitlines()
    assert lines[0].strip() == "POLYCHORD_BOOTSTRAP_V1"
    return int(lines[2].split()[0])


def _logz(stats: Path) -> float:
    for line in stats.read_text(encoding="utf-8-sig").splitlines():
        if line.startswith("log(Z") and "Still active" not in line:
            return float(line.split("=")[-1].split("+/-")[0])
    raise AssertionError(f"no final logZ in {stats}")


def _base(packages: Path, prefix: Path) -> dict:
    return {
        "packages_path": str(packages),
        "likelihood": {"gaussian": {"external": "lambda x, y: -0.5 * (x**2 + y**2)"}},
        "params": {
            "x": {"prior": {"min": -5.0, "max": 5.0}},
            "y": {"prior": {"min": -5.0, "max": 5.0}},
        },
        "sampler": {"polychord": {
            "nlive": 5,
            "num_repeats": 2,
            "nprior": 12,
            "precision_criterion": 0.5,
            "max_ndead": 12,
            "write_resume": True,
            "read_resume": True,
            "write_stats": True,
            "synchronous": True,
            "seed": 13579,
        }},
        "output": str(prefix),
        "resume": False,
        "force": True,
    }


def _write_run(folder: Path, info: dict, name: str) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / name
    path.write_text(yaml.safe_dump(info, sort_keys=False), encoding="utf-8")
    return path


def _partial_env(sidecar: Path) -> dict[str, str]:
    sidecar.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env["POLYCHORD_BOOTSTRAP_SEGMENT_VALID"] = "4"
    env["POLYCHORD_BOOTSTRAP_STATE_DIR"] = str(sidecar.resolve())
    return env


def _diagnostic(result: subprocess.CompletedProcess[str], state: Path) -> str:
    state_text = state.read_text(encoding="utf-8") if state.is_file() else "<missing state>"
    return "\n--- stdout ---\n" + result.stdout + "\n--- stderr ---\n" + result.stderr + "\n--- state ---\n" + state_text


def _bootstrap_continuation(info: dict, output_prefix: Path) -> dict:
    continued = copy.deepcopy(info)
    continued["output"] = str(output_prefix)
    continued["resume"] = False
    continued["force"] = False
    return continued


def test_real_polychord_pre_resume_segments_match_uninterrupted_reference(tmp_path: Path):
    packages = Path(os.environ["COBAYA_PACKAGES_PATH"]).resolve()
    science = {"schema": "toy-pre-resume-v1", "seed": 13579, "nprior": 12}
    runtime = {"schema": "toy-patched-polychord-v1", "version": "1.20.1"}

    first = tmp_path / "seg0"
    first_prefix = first / "data" / "chain"
    sidecar0 = first / "bootstrap-sidecar"
    state0 = sidecar0 / "chain.bootstrap"
    info0 = _base(packages, first_prefix)
    run0 = _write_run(first, info0, "run.yaml")
    r0 = _run(["mpirun", "--oversubscribe", "-np", "2", "cobaya-run", str(run0)], first, env=_partial_env(sidecar0))
    assert r0.returncode == 86, (r0.stdout + "\n" + r0.stderr)[-5000:]
    assert state0.is_file() and _accepted(state0) == 4
    first_raw = first / "data" / "chain_polychord_raw"
    assert not list(first_raw.glob("*.bootstrap*")), "pre-resume state must live outside Cobaya-managed raw output"
    assert not list(first_raw.glob("*.resume"))

    bundle0 = tmp_path / "bundle0"
    m0 = promote_bootstrap_bundle(
        state0, bundle0, model="M1", segment=0, parent_digest=None,
        science_manifest=science, runtime_manifest=runtime, output_prefix=first_prefix,
    )

    second = tmp_path / "seg1"
    second_prefix = second / "data" / "chain"
    sidecar1 = second / "bootstrap-sidecar"
    state1 = sidecar1 / "chain.bootstrap"
    info1 = _bootstrap_continuation(info0, second_prefix)
    restore_bootstrap_bundle(
        bundle0, state1,
        {"model": "M1", "science_sha": sha256_json(science), "runtime_sha": sha256_json(runtime),
         "checkpoint_digest": m0["checkpoint_digest"]},
    )
    run1 = _write_run(second, info1, "run.yaml")
    r1 = _run(["mpirun", "--oversubscribe", "-np", "2", "cobaya-run", str(run1)], second, env=_partial_env(sidecar1))
    assert r1.returncode == 86, _diagnostic(r1, state1)
    assert state1.is_file() and _accepted(state1) == 8, _diagnostic(r1, state1)

    bundle1 = tmp_path / "bundle1"
    m1 = promote_bootstrap_bundle(
        state1, bundle1, model="M1", segment=1, parent_digest=m0["checkpoint_digest"],
        science_manifest=science, runtime_manifest=runtime, output_prefix=second_prefix,
    )

    third = tmp_path / "seg2"
    third_prefix = third / "data" / "chain"
    sidecar2 = third / "bootstrap-sidecar"
    state2 = sidecar2 / "chain.bootstrap"
    info2 = _bootstrap_continuation(info0, third_prefix)
    restore_bootstrap_bundle(
        bundle1, state2,
        {"model": "M1", "science_sha": sha256_json(science), "runtime_sha": sha256_json(runtime),
         "checkpoint_digest": m1["checkpoint_digest"]},
    )
    run2 = _write_run(third, info2, "run.yaml")
    r2 = _run(["mpirun", "--oversubscribe", "-np", "2", "cobaya-run", str(run2)], third, env=_partial_env(sidecar2))
    assert r2.returncode == 0, (r2.stdout + "\n" + r2.stderr)[-5000:]
    third_raw = third / "data" / "chain_polychord_raw"
    assert not state2.exists()
    assert any(p.stat().st_size > 0 for p in third_raw.glob("*.resume"))
    stats_segmented = next(third_raw.glob("*.stats"))

    reference = tmp_path / "reference"
    ref_prefix = reference / "data" / "chain"
    ref_info = _base(packages, ref_prefix)
    ref_run = _write_run(reference, ref_info, "run.yaml")
    reference_env = dict(os.environ)
    reference_env.pop("POLYCHORD_BOOTSTRAP_SEGMENT_VALID", None)
    reference_env.pop("POLYCHORD_BOOTSTRAP_STATE_DIR", None)
    rr = _run(["mpirun", "--oversubscribe", "-np", "2", "cobaya-run", str(ref_run)], reference, env=reference_env)
    assert rr.returncode == 0, (rr.stdout + "\n" + rr.stderr)[-5000:]
    stats_reference = next((reference / "data" / "chain_polychord_raw").glob("*.stats"))

    assert _logz(stats_segmented) == pytest.approx(_logz(stats_reference), abs=1e-10, rel=0.0)
