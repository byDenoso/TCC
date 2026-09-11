from __future__ import annotations

import copy
import json
import os
import subprocess
from pathlib import Path

import pytest
import yaml

from peer_decisive_followups.checkpoint_manager import (
    promote_checkpoint,
    relocate_cobaya_metadata,
    restore_bundle,
)
from peer_decisive_followups.production_contract import sha256_json


pytestmark = pytest.mark.integration


def _run(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(cmd, cwd=cwd, text=True, capture_output=True)
    if result.returncode != 0:
        raise AssertionError(
            f"command failed ({result.returncode}): {' '.join(cmd)}\n"
            f"--- stdout ---\n{result.stdout}\n--- stderr ---\n{result.stderr}"
        )
    return result


def test_real_polychord_checkpoint_restore_and_resume(tmp_path: Path):
    packages = Path(os.environ["COBAYA_PACKAGES_PATH"]).resolve()
    first = tmp_path / "first"
    first_data = first / "data"
    first_data.mkdir(parents=True)
    first_prefix = first_data / "chain"

    info = {
        "packages_path": str(packages),
        "likelihood": {
            "gaussian": {
                "external": "lambda x, y: -0.5 * (x**2 + y**2)",
            }
        },
        "params": {
            "x": {"prior": {"min": -5.0, "max": 5.0}},
            "y": {"prior": {"min": -5.0, "max": 5.0}},
        },
        "sampler": {
            "polychord": {
                "nlive": 20,
                "num_repeats": 2,
                "nprior": 20,
                "precision_criterion": 0.5,
                "max_ndead": 40,
                "write_resume": True,
                "read_resume": True,
                "write_stats": True,
                "seed": 24680,
            }
        },
        "output": str(first_prefix),
        "resume": False,
        "force": True,
    }
    first_yaml = first / "run.yaml"
    first_yaml.write_text(yaml.safe_dump(info, sort_keys=False), encoding="utf-8")
    _run(
        ["mpirun", "--oversubscribe", "-np", "2", "cobaya-run", str(first_yaml)],
        first,
    )

    raw = first_data / "chain_polychord_raw"
    resume_files = [p for p in raw.glob("*.resume") if p.is_file() and p.stat().st_size > 0]
    assert resume_files, f"PolyChord produced no usable resume file under {raw}"
    assert Path(str(first_prefix) + ".input.yaml").is_file()
    assert Path(str(first_prefix) + ".updated.yaml").is_file()

    science = {
        "schema": "toy-polychord-e2e-v1",
        "model": "M1",
        "params": {"x": [-5.0, 5.0], "y": [-5.0, 5.0]},
    }
    runtime = {
        "schema": "toy-polychord-runtime-v1",
        "cobaya": "3.6.2",
        "polychord": "installed-by-cobaya",
    }
    bundle = tmp_path / "checkpoint"
    parent = promote_checkpoint(
        raw,
        bundle,
        model="M1",
        segment=0,
        parent_digest=None,
        science_manifest=science,
        runtime_manifest=runtime,
        output_prefix=first_prefix,
        status={"classification": "RESUMABLE"},
    )

    second = tmp_path / "second"
    second_data = second / "data"
    second_raw = second_data / "chain_polychord_raw"
    expected = {
        "model": "M1",
        "science_sha": sha256_json(science),
        "runtime_sha": sha256_json(runtime),
        "checkpoint_digest": parent["checkpoint_digest"],
    }
    restored = restore_bundle(bundle, second_raw, expected, output_dir=second_data)
    assert restored["checkpoint_digest"] == parent["checkpoint_digest"]

    continuation = copy.deepcopy(info)
    continuation["output"] = str(second_data / "chain")
    continuation["resume"] = True
    continuation["force"] = False
    relocation = relocate_cobaya_metadata(second_data / "chain", continuation)
    assert relocation["files"] == ["chain.input.yaml", "chain.updated.yaml"]

    second.mkdir(parents=True, exist_ok=True)
    second_yaml = second / "resume.yaml"
    second_yaml.write_text(yaml.safe_dump(continuation, sort_keys=False), encoding="utf-8")
    resumed = _run(
        ["mpirun", "--oversubscribe", "-np", "2", "cobaya-run", str(second_yaml)],
        second,
    )
    combined = (resumed.stdout + "\n" + resumed.stderr).lower()
    assert "resum" in combined, combined[-4000:]
    assert any(p.is_file() and p.stat().st_size > 0 for p in second_raw.glob("*.resume"))
    assert any(p.is_file() and p.stat().st_size > 0 for p in second_raw.glob("*.stats"))

    report = {
        "parent_checkpoint_digest": parent["checkpoint_digest"],
        "restored_checkpoint_digest": restored["checkpoint_digest"],
        "resume_files": sorted(p.name for p in second_raw.glob("*.resume")),
        "stats_files": sorted(p.name for p in second_raw.glob("*.stats")),
    }
    (tmp_path / "e2e_report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True), encoding="utf-8"
    )
