#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import random
from pathlib import Path
from typing import Any

import yaml

MODELS = ("M0", "M1", "M2", "M3")

REFS = {
    "M0": dict(ombh2=0.02260, omch2=0.1186, cosmomc_theta=0.010414, logA=3.058,
               ns=0.9720, tau=0.0590, A_act=1.000, P_act=1.000,
               peer_fede=0.0, Alens=1.0),
    "M1": dict(ombh2=0.02262, omch2=0.1182, cosmomc_theta=0.010415, logA=3.035,
               ns=0.9747, tau=0.0538, A_act=1.000, P_act=1.000,
               peer_fede=0.0, Alens=1.1106),
    "M2": dict(ombh2=0.02293, omch2=0.1250, cosmomc_theta=0.010401, logA=3.077,
               ns=0.9944, tau=0.0628, A_act=1.000, P_act=1.000,
               peer_fede=0.1075, Alens=1.0),
    "M3": dict(ombh2=0.02303, omch2=0.1253, cosmomc_theta=0.010400, logA=3.049,
               ns=0.9926, tau=0.0551, A_act=1.000, P_act=1.000,
               peer_fede=0.0903, Alens=1.0869),
}

PROPOSALS = {
    "ombh2": 6.5e-5, "omch2": 1.1e-3, "cosmomc_theta": 1.0e-5,
    "logA": 3.6e-3, "ns": 3.3e-3, "tau": 5.0e-3,
    "A_act": 2.0e-3, "P_act": 8.0e-3, "peer_fede": 8.0e-3,
    "Alens": 2.5e-2,
}

BOUNDS = {
    "ombh2": (0.017, 0.027), "omch2": (0.09, 0.15),
    "cosmomc_theta": (0.01030, 0.01050), "logA": (2.6, 3.5),
    "ns": (0.90, 1.10), "tau": (0.0, 0.10), "A_act": (0.5, 1.5),
    "P_act": (0.9, 1.1), "peer_fede": (0.0, 0.18), "Alens": (0.5, 1.5),
}


def sampled(name: str, ref: float, scale: float = 1.0) -> dict[str, Any]:
    lo, hi = BOUNDS[name]
    return {
        "prior": {"min": lo, "max": hi},
        "ref": {"dist": "norm", "loc": float(ref), "scale": float(PROPOSALS[name] * max(scale, 0.5))},
        "proposal": float(PROPOSALS[name]),
    }


def base_info(model: str, packages_path: str, output: str, ref_scale: float = 1.0) -> dict[str, Any]:
    if model not in MODELS:
        raise ValueError(model)
    r = REFS[model]
    params: dict[str, Any] = {
        "ombh2": sampled("ombh2", r["ombh2"], ref_scale),
        "omch2": sampled("omch2", r["omch2"], ref_scale),
        "cosmomc_theta": sampled("cosmomc_theta", r["cosmomc_theta"], ref_scale),
        "logA": sampled("logA", r["logA"], ref_scale),
        "As": {"value": "lambda logA: 1e-10*np.exp(logA)", "derived": True, "latex": "A_s"},
        "ns": sampled("ns", r["ns"], ref_scale),
        "tau": sampled("tau", r["tau"], ref_scale),
        "A_act": sampled("A_act", r["A_act"], ref_scale),
        "P_act": sampled("P_act", r["P_act"], ref_scale),
        "A_planck": {"value": "lambda A_act: A_act", "latex": "y_\\mathrm{cal}"},
        "peer_zc": {"value": 3.81, "latex": "\\log_{10}(z_c)"},
        "peer_thetai": {"value": 2.89155, "latex": "\\theta_i"},
        "H0": {"derived": True, "latex": "H_0"},
        "omegam": {"derived": "lambda omch2, ombh2, H0: (omch2 + ombh2) / (H0/100.0)**2", "latex": "\\Omega_m"},
        "sigma8": {"derived": True, "latex": "\\sigma_8"},
        "S8": {"derived": "lambda sigma8, omegam: sigma8 * (omegam / 0.3)**0.5", "latex": "S_8"},
        "rdrag": {"derived": True, "latex": "r_d"},
        "thetastar": {"derived": True, "latex": "\\theta_*"},
    }
    params["peer_fede"] = sampled("peer_fede", r["peer_fede"], ref_scale) if model in ("M2", "M3") else {"value": 0.0, "latex": "f_\\mathrm{PEER}"}
    params["Alens"] = sampled("Alens", r["Alens"], ref_scale) if model in ("M1", "M3") else {"value": 1.0, "latex": "A_\\mathrm{lens}"}

    for like in [
        "act_dr6_cmbonly", "act_dr6_cmbonly.PlanckActCut",
        "planck_2018_lowl.TT", "planck_2018_lowl.EE_sroll2",
        "planck_2018_lensing.native", "bao.desi_dr2.desi_bao_all",
        "shoes_h0.SH0ESGaussian",
    ]:
        params[f"chi2__{like}"] = {"derived": True}

    return {
        "packages_path": packages_path,
        "output": output,
        "force": True,
        "debug": False,
        "theory": {
            "peer_scalar_n3.PEERScalarN3": {
                "python_path": str(Path(__file__).resolve().parent),
                "stop_at_error": True,
                "extra_args": {
                    "mnu": 0.06, "omk": 0.0, "nnu": 3.046,
                    "num_massive_neutrinos": 1, "kmax": 10,
                    "k_per_logint": 130, "nonlinear": True,
                    "lens_potential_accuracy": 8, "lens_margin": 2050,
                    "lAccuracyBoost": 1.2, "min_l_logl_sampling": 6000,
                    "DoLateRadTruncation": False,
                    "recombination_model": "CosmoRec",
                    "halofit_version": "mead2020",
                },
            }
        },
        "likelihood": {
            "act_dr6_cmbonly": {"stop_at_error": True},
            "act_dr6_cmbonly.PlanckActCut": {"stop_at_error": True},
            "planck_2018_lowl.TT": {"stop_at_error": True},
            "planck_2018_lowl.EE_sroll2": {"stop_at_error": True},
            "planck_2018_lensing.native": {"stop_at_error": True},
            "bao.desi_dr2.desi_bao_all": {"stop_at_error": True},
            "shoes_h0.SH0ESGaussian": {
                "python_path": str(Path(__file__).resolve().parent),
                "mean": 73.04, "sigma": 1.04, "stop_at_error": True,
            },
        },
        "prior": {"act_calibration_prior": "lambda A_act: stats.norm.logpdf(A_act, loc=1.0, scale=0.003)"},
        "params": params,
    }


def jittered_ref(model: str, seed: int) -> dict[str, float]:
    rng = random.Random(seed)
    out = dict(REFS[model])
    for name in ["ombh2", "omch2", "cosmomc_theta", "logA", "ns", "tau", "A_act", "P_act"]:
        out[name] += rng.gauss(0.0, PROPOSALS[name] * 3.0)
        lo, hi = BOUNDS[name]
        out[name] = min(max(out[name], lo + 1e-8), hi - 1e-8)
    if model in ("M2", "M3"):
        out["peer_fede"] = min(max(out["peer_fede"] + rng.gauss(0.0, 0.02), 1e-5), 0.179)
    if model in ("M1", "M3"):
        out["Alens"] = min(max(out["Alens"] + rng.gauss(0.0, 0.05), 0.51), 1.49)
    return out


def apply_ref(info: dict[str, Any], refs: dict[str, float]) -> None:
    for name, value in refs.items():
        if name in info["params"] and isinstance(info["params"][name], dict) and "prior" in info["params"][name]:
            info["params"][name]["ref"] = float(value)


def write_configs(model: str, packages: str, root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    cfg = root / "configs"
    cfg.mkdir(exist_ok=True)
    for i in range(8):
        seed = 2026072900 + i + {"M0": 0, "M1": 100, "M2": 200, "M3": 300}[model]
        info = base_info(model, packages, str((root / f"minimize/start_{i+1}/chain").resolve()))
        apply_ref(info, jittered_ref(model, seed))
        info["sampler"] = {
            "minimize": {
                "ignore_prior": False, "best_of": 1, "max_evals": 8000,
                "seed": seed, "method": "scipy",
                "override_scipy": {
                    "method": "Powell",
                    "options": {"maxiter": 900, "xtol": 1e-4, "ftol": 1e-8},
                },
            }
        }
        (cfg / f"minimize_{i+1}.yaml").write_text(yaml.safe_dump(info, sort_keys=False), encoding="utf-8")

    mcmc = base_info(model, packages, str((root / "mcmc/chain").resolve()))
    mcmc["resume"] = False
    mcmc["sampler"] = {
        "mcmc": {
            "Rminus1_stop": 0.01, "Rminus1_cl_stop": 0.05,
            "burn_in": 300, "learn_proposal": True,
            "learn_proposal_Rminus1_max": 30.0, "max_samples": 30000,
            "proposal_scale": 1.2,
            "seed": 2026072999 + {"M0": 0, "M1": 100, "M2": 200, "M3": 300}[model],
            "output_every": 60, "checkpoint_every": 120,
        }
    }
    (cfg / "mcmc.yaml").write_text(yaml.safe_dump(mcmc, sort_keys=False), encoding="utf-8")
    manifest = {
        "model": model,
        "stack": "Planck low-l TT + Sroll2 EE + PlanckActCut + ACT DR6 TTTEEE + Planck lensing + DESI DR2 BAO + SH0ES",
        "lane": "A_PACT", "act_commit": "627aeafb88ae5ad1aa66b406bea2d65cfa66a27d",
        "camb": "1.6.6+CosmoRec", "cobaya": "3.6.2",
        "peer_log10_zc": 3.81, "peer_theta_i": 2.89155,
        "peer_prior": [0.0, 0.18], "alens_prior": [0.5, 1.5],
        "shoes": [73.04, 1.04],
    }
    (root / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def parse_minimum(path: Path) -> dict[str, float]:
    lines = [x.strip() for x in path.read_text(encoding="utf-8", errors="replace").splitlines() if x.strip()]
    if len(lines) < 2:
        raise ValueError(f"Invalid minimum file {path}")
    return {k: float(v) for k, v in zip(lines[0].lstrip("#").split(), lines[1].split())}


def summarize(root: Path, model: str) -> int:
    minima = []
    for p in sorted(root.glob("minimize/start_*/chain.minimum.txt")):
        try:
            row = parse_minimum(p)
            row["source"] = str(p)
            minima.append(row)
        except Exception as exc:
            minima.append({"source": str(p), "error": str(exc)})
    good = sorted((x for x in minima if "minuslogpost" in x), key=lambda x: x["minuslogpost"])
    summary = {
        "model": model, "n_minima_found": len(good),
        "best_minimum": good[0] if good else None,
        "mcmc_checkpoint_exists": (root / "mcmc/chain.checkpoint").exists(),
        "mcmc_progress_exists": (root / "mcmc/chain.progress").exists(),
        "chain_files": [str(p) for p in sorted(root.glob("mcmc/chain.*.txt"))],
        "minimum_rows": minima,
    }
    (root / "campaign_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return 0 if good else 2


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("write-configs")
    p.add_argument("--model", choices=MODELS, required=True)
    p.add_argument("--packages", required=True)
    p.add_argument("--root", required=True)
    q = sub.add_parser("promote-best")
    q.add_argument("--model", choices=MODELS, required=True)
    q.add_argument("--root", required=True)
    s = sub.add_parser("summarize")
    s.add_argument("--model", choices=MODELS, required=True)
    s.add_argument("--root", required=True)
    args = ap.parse_args()
    if args.cmd == "write-configs":
        write_configs(args.model, args.packages, Path(args.root).resolve())
        return 0
    if args.cmd == "promote-best":
        root = Path(args.root).resolve()
        rows = []
        for p in sorted(root.glob("minimize/start_*/chain.minimum.txt")):
            try:
                row = parse_minimum(p)
                row["source"] = str(p)
                rows.append(row)
            except Exception:
                pass
        if not rows:
            raise SystemExit("No valid minima found")
        best = min(rows, key=lambda x: x["minuslogpost"])
        cfg_path = root / "configs/mcmc.yaml"
        info = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
        for name, spec in info["params"].items():
            if isinstance(spec, dict) and "prior" in spec and name in best:
                spec["ref"] = float(best[name])
        cfg_path.write_text(yaml.safe_dump(info, sort_keys=False), encoding="utf-8")
        (root / "best_minimum.json").write_text(json.dumps(best, indent=2), encoding="utf-8")
        return 0
    return summarize(Path(args.root).resolve(), args.model)


if __name__ == "__main__":
    raise SystemExit(main())
