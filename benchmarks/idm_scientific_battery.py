#!/usr/bin/env python3
from __future__ import annotations

import importlib
import importlib.metadata
import json
import math
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

from benchmarks.idm_runtime_preflight import (
    EXPECTED_BLOBS,
    PINNED_REPOSITORY,
    PINNED_REVISION,
)

OUTPUT = Path("idm_scientific_battery_result.json")
SCHEMA = "nexo.idm_scientific_battery.v1"

QUESTION = (
    "Does non-zero interacting-dark-sector coupling produce stable, sign- and "
    "magnitude-dependent departures from matched uncoupled scalar-field and LCDM controls?"
)
H0 = (
    "After matching the scalar-field background, non-zero cdm_c produces no material "
    "departure beyond numerical noise in background, growth, or linear clustering observables."
)
H1 = (
    "Non-zero cdm_c produces reproducible sign- and/or magnitude-dependent departures "
    "in one or more background, growth, or linear-clustering observables."
)
DISCRIMINANT = (
    "Compare H(z=0.5), sigma8, f*sigma8(z=0.5), P(k=0.1,z=0), age, rs_d and Omega_m "
    "against a matched uncoupled scalar-field control at the frozen iDM revision."
)
STOPPING_RULE = (
    "Stop after the exact 15-case bounded battery is attempted once at the pinned revision; "
    "do not auto-repeat numerical failures under identical conditions."
)

COMMON: dict[str, Any] = {
    "h": 0.67810,
    "omega_b": 0.02238280,
    "omega_cdm": 0.1201075,
    "N_ur": 3.044,
    "T_cmb": 2.7255,
    "z_reio": 7.6711,
    "YHe": 0.25,
    "output": "mPk",
    "P_k_max_1/Mpc": 1.0,
    "z_max_pk": 5.0,
}

SCF_BASE: dict[str, Any] = {
    **COMMON,
    "Omega_fld": 0,
    "Omega_scf": -0.7,
    "Omega_Lambda": 0.0,
    "scf_potential": "hyperbolic",
    "scf_parameters": "1e-08, 0.59, 0.0, 0.0, 0, 0, 0., 0., 0., 0., 1, 0",
    "attractor_ic_scf": "no",
    "scf_tuning_index": 0,
    "gauge": "newtonian",
}


def build_cases() -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = [
        {"id": "T01_LCDM", "kind": "lcdm", "label": "LCDM reference", "params": dict(COMMON)},
        {
            "id": "T02_SCF_UNCOUPLED",
            "kind": "scf_uncoupled",
            "label": "matched hyperbolic scalar field, standard CDM",
            "params": dict(SCF_BASE),
        },
        {
            "id": "T03_IDM_C0",
            "kind": "idm_coupling",
            "label": "interacting-CDM code path, zero coupling",
            "cdm_c": 0.0,
            "params": {**SCF_BASE, "model_cdm": "i", "cdm_c": 0.0},
        },
    ]
    for index, value in enumerate([-3.0, -1.0, -0.3, -0.1, -0.03, -0.01, 0.01, 0.03, 0.1, 0.3, 1.0, 3.0], start=4):
        token = f"M{abs(value):g}" if value < 0 else f"P{value:g}"
        cases.append(
            {
                "id": f"T{index:02d}_IDM_C{token}",
                "kind": "idm_coupling",
                "label": f"iDM coupling cdm_c={value:g}",
                "cdm_c": value,
                "params": {**SCF_BASE, "model_cdm": "i", "cdm_c": value},
            }
        )
    return cases


def run(cmd: list[str], *, cwd: Path | None = None, timeout: int = 300) -> dict[str, Any]:
    started = time.time()
    try:
        completed = subprocess.run(
            cmd,
            cwd=cwd,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout,
            check=False,
        )
        return {
            "argv": cmd,
            "exit_code": completed.returncode,
            "seconds": time.time() - started,
            "output_tail": completed.stdout[-12000:],
        }
    except subprocess.TimeoutExpired as exc:
        text = exc.stdout or ""
        if isinstance(text, bytes):
            text = text.decode(errors="replace")
        return {
            "argv": cmd,
            "exit_code": 124,
            "seconds": time.time() - started,
            "output_tail": text[-12000:],
            "error": "timeout",
        }


def require_ok(stage: str, result: dict[str, Any], receipt: dict[str, Any]) -> None:
    receipt["stages"][stage] = result
    if result["exit_code"] != 0:
        raise RuntimeError(f"{stage} failed with exit {result['exit_code']}")


def materialize_exact_source(root: Path, receipt: dict[str, Any]) -> Path:
    repo = root / "idm"
    repo.mkdir()
    require_ok("git_init", run(["git", "init", "-q"], cwd=repo, timeout=30), receipt)
    require_ok(
        "git_remote",
        run(["git", "remote", "add", "origin", PINNED_REPOSITORY], cwd=repo, timeout=30),
        receipt,
    )
    require_ok(
        "git_fetch",
        run(["git", "fetch", "--depth", "1", "origin", PINNED_REVISION], cwd=repo, timeout=180),
        receipt,
    )
    require_ok("git_checkout", run(["git", "checkout", "--detach", "FETCH_HEAD"], cwd=repo, timeout=30), receipt)
    head = run(["git", "rev-parse", "HEAD"], cwd=repo, timeout=30)
    require_ok("git_revision", head, receipt)
    actual = head["output_tail"].strip().splitlines()[-1]
    if actual != PINNED_REVISION:
        raise RuntimeError(f"revision mismatch: {actual}")
    receipt["source_revision"] = actual

    receipt["source_blobs"] = {}
    for relative, expected in EXPECTED_BLOBS.items():
        check = run(["git", "hash-object", relative], cwd=repo, timeout=30)
        require_ok(f"blob:{relative}", check, receipt)
        actual_blob = check["output_tail"].strip().splitlines()[-1]
        if actual_blob != expected:
            raise RuntimeError(f"blob mismatch for {relative}: {actual_blob}")
        receipt["source_blobs"][relative] = actual_blob
    return repo


def install_classy(repo: Path, receipt: dict[str, Any]) -> None:
    install = run(
        [sys.executable, "-m", "pip", "install", "--disable-pip-version-check", "--no-input", "--no-cache-dir", "."],
        cwd=repo,
        timeout=600,
    )
    require_ok("install_classy", install, receipt)
    probe = run(
        [sys.executable, "-c", "import classy,importlib.metadata; print(classy.__file__); print(importlib.metadata.version('classy'))"],
        timeout=30,
    )
    require_ok("probe_classy", probe, receipt)
    lines = [line.strip() for line in probe["output_tail"].splitlines() if line.strip()]
    receipt["classy"] = {
        "module": lines[-2] if len(lines) >= 2 else None,
        "version": lines[-1] if lines else None,
    }


def safe_float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def collect_metrics(cosmo: Any) -> dict[str, float | None]:
    metrics: dict[str, float | None] = {}
    for key, out_key in [
        ("H0", "H0"),
        ("age", "age_Gyr"),
        ("sigma8", "sigma8"),
        ("Omega_m", "Omega_m"),
        ("rs_d", "rs_d_Mpc"),
        ("100*theta_s", "theta_s_100"),
    ]:
        try:
            value = cosmo.get_current_derived_parameters([key])[key]
            metrics[out_key] = safe_float(value)
        except Exception:
            metrics[out_key] = None

    probes = [
        ("H_z0p5", lambda: cosmo.Hubble(0.5)),
        ("Da_z1", lambda: cosmo.angular_distance(1.0)),
        ("growth_D_z0p5", lambda: cosmo.scale_independent_growth_factor(0.5)),
        ("fsigma8_z0p5", lambda: cosmo.scale_independent_f_sigma8(0.5)),
        ("Pk_k0p1_z0", lambda: cosmo.pk(0.1, 0.0)),
        ("Pk_k0p01_z0", lambda: cosmo.pk(0.01, 0.0)),
    ]
    for name, fn in probes:
        try:
            metrics[name] = safe_float(fn())
        except Exception:
            metrics[name] = None
    return metrics


def execute_cases(receipt: dict[str, Any]) -> list[dict[str, Any]]:
    importlib.invalidate_caches()
    from classy import Class

    results: list[dict[str, Any]] = []
    for case in build_cases():
        started = time.time()
        record: dict[str, Any] = {
            "id": case["id"],
            "kind": case["kind"],
            "label": case["label"],
            "cdm_c": case.get("cdm_c"),
            "status": "FAIL",
        }
        cosmo = Class()
        try:
            cosmo.set(case["params"])
            cosmo.compute()
            record["metrics"] = collect_metrics(cosmo)
            finite_count = sum(value is not None for value in record["metrics"].values())
            record["finite_metric_count"] = finite_count
            record["status"] = "PASS" if finite_count >= 8 else "PARTIAL_METRICS"
        except Exception as exc:
            record["error"] = f"{type(exc).__name__}:{exc}"[-6000:]
        finally:
            try:
                cosmo.struct_cleanup()
                cosmo.empty()
            except Exception:
                pass
        record["seconds"] = time.time() - started
        results.append(record)
    receipt["attempted_cases"] = len(results)
    return results


def relative_delta_pct(value: float | None, baseline: float | None) -> float | None:
    if value is None or baseline is None or baseline == 0:
        return None
    return 100.0 * (value / baseline - 1.0)


def summarize(results: list[dict[str, Any]]) -> dict[str, Any]:
    by_id = {case["id"]: case for case in results}
    scf = by_id.get("T02_SCF_UNCOUPLED", {}).get("metrics", {})
    lcdm = by_id.get("T01_LCDM", {}).get("metrics", {})
    comparison_metrics = [
        "H0",
        "age_Gyr",
        "sigma8",
        "Omega_m",
        "rs_d_Mpc",
        "theta_s_100",
        "H_z0p5",
        "Da_z1",
        "growth_D_z0p5",
        "fsigma8_z0p5",
        "Pk_k0p1_z0",
        "Pk_k0p01_z0",
    ]

    for case in results:
        metrics = case.get("metrics") or {}
        if case["id"] != "T02_SCF_UNCOUPLED":
            case["delta_vs_scf_pct"] = {
                name: relative_delta_pct(metrics.get(name), scf.get(name))
                for name in comparison_metrics
            }
        if case["id"] != "T01_LCDM":
            case["delta_vs_lcdm_pct"] = {
                name: relative_delta_pct(metrics.get(name), lcdm.get(name))
                for name in comparison_metrics
            }

    successful = [case for case in results if case["status"] in {"PASS", "PARTIAL_METRICS"}]
    failed = [case for case in results if case["status"] == "FAIL"]
    controls = [by_id.get(name) for name in ["T01_LCDM", "T02_SCF_UNCOUPLED", "T03_IDM_C0"]]
    controls_ok = all(case and case["status"] in {"PASS", "PARTIAL_METRICS"} for case in controls)

    zero = by_id.get("T03_IDM_C0", {})
    zero_deltas = zero.get("delta_vs_scf_pct", {})
    finite_zero = [abs(value) for value in zero_deltas.values() if value is not None]

    maxima: dict[str, dict[str, Any]] = {}
    for metric in comparison_metrics:
        candidates = []
        for case in results:
            if case.get("kind") != "idm_coupling" or case.get("cdm_c") == 0:
                continue
            delta = (case.get("delta_vs_scf_pct") or {}).get(metric)
            if delta is not None:
                candidates.append((abs(delta), delta, case["id"], case.get("cdm_c")))
        if candidates:
            _, delta, case_id, coupling = max(candidates)
            maxima[metric] = {"case_id": case_id, "cdm_c": coupling, "delta_pct": delta}

    return {
        "successful_cases": len(successful),
        "failed_cases": len(failed),
        "failed_case_ids": [case["id"] for case in failed],
        "controls_ok": controls_ok,
        "zero_coupling_max_abs_delta_vs_scf_pct": max(finite_zero) if finite_zero else None,
        "max_abs_response_vs_scf": maxima,
        "scientific_status": "COMPLETE" if not failed else "PARTIAL_NUMERICAL_BOUNDARY",
    }


def main() -> int:
    requested = os.getenv("NEXO_PARAM_SOURCE_REVISION", PINNED_REVISION).strip()
    receipt: dict[str, Any] = {
        "schema": SCHEMA,
        "execution_id": os.getenv("NEXO_EXECUTION_ID"),
        "work_id": os.getenv("NEXO_WORK_ID"),
        "test_id": os.getenv("NEXO_TEST_ID"),
        "question": QUESTION,
        "h0": H0,
        "h1": H1,
        "discriminant": DISCRIMINANT,
        "stopping_rule": STOPPING_RULE,
        "source_repository": PINNED_REPOSITORY,
        "pinned_revision": PINNED_REVISION,
        "requested_revision": requested,
        "stages": {},
        "status": "FAIL",
        "cases": [],
    }
    exit_code = 1
    try:
        if requested != PINNED_REVISION:
            raise RuntimeError("source revision differs from frozen iDM binding")
        with tempfile.TemporaryDirectory(prefix="nexo-idm-battery-") as raw:
            repo = materialize_exact_source(Path(raw), receipt)
            install_classy(repo, receipt)
            receipt["cases"] = execute_cases(receipt)
            receipt["summary"] = summarize(receipt["cases"])
            if receipt["attempted_cases"] != 15:
                raise RuntimeError(f"battery attempted {receipt['attempted_cases']} cases instead of 15")
            if not receipt["summary"]["controls_ok"]:
                raise RuntimeError("one or more control cases failed")
            receipt["status"] = "PASS"
            exit_code = 0
    except Exception as exc:
        receipt["error"] = f"{type(exc).__name__}:{exc}"[-12000:]
        exit_code = 1
    finally:
        receipt["finished_at_unix"] = time.time()
        OUTPUT.write_text(json.dumps(receipt, indent=2, sort_keys=True), encoding="utf-8")
        print(json.dumps(receipt, indent=2, sort_keys=True))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
