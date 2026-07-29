#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import yaml

MODELS = ("M0", "M1", "M2", "M3")
LANES = ("A", "B")

REFS = {
    "M0": dict(ombh2=0.02260, omch2=0.11860, H0=68.21, logA=3.0580,
               ns=0.9720, tau=0.0590, A_act=1.0000, P_act=1.0000,
               A_planck=1.0000, peer_fede=0.0, Alens=1.0),
    "M1": dict(ombh2=0.02262, omch2=0.11820, H0=68.40, logA=3.0350,
               ns=0.9747, tau=0.0538, A_act=1.0000, P_act=1.0000,
               A_planck=1.0000, peer_fede=0.0, Alens=1.1106),
    "M2": dict(ombh2=0.0229068, omch2=0.123505, H0=70.89, logA=3.05812,
               ns=0.99126, tau=0.06187, A_act=0.99950, P_act=1.00259,
               A_planck=0.99950, peer_fede=0.07517, Alens=1.0),
    "M3": dict(ombh2=0.0229068, omch2=0.123505, H0=70.889, logA=3.05812,
               ns=0.99126, tau=0.06187, A_act=0.99950, P_act=1.00259,
               A_planck=0.99950, peer_fede=0.07517, Alens=1.05245),
}

BOUNDS = {
    "ombh2": (0.017, 0.027), "omch2": (0.09, 0.15), "H0": (60.0, 80.0),
    "logA": (2.6, 3.5), "ns": (0.90, 1.10), "tau": (0.0, 0.10),
    "A_act": (0.5, 1.5), "P_act": (0.9, 1.1), "A_planck": (0.5, 1.5),
    "peer_fede": (0.0, 0.18), "Alens": (0.5, 1.5),
}

PROPOSALS = {
    "ombh2": 1.2e-4, "omch2": 1.2e-3, "H0": 0.50, "logA": 0.012,
    "ns": 0.0040, "tau": 0.0050, "A_act": 0.0020, "P_act": 0.0080,
    "A_planck": 0.0020, "peer_fede": 0.010, "Alens": 0.030,
}


def sampled(name: str, ref: float) -> dict[str, Any]:
    lo, hi = BOUNDS[name]
    return {
        "prior": {"min": lo, "max": hi},
        "ref": {"dist": "norm", "loc": float(ref), "scale": float(PROPOSALS[name] * 0.5)},
        "proposal": float(PROPOSALS[name]),
    }


def build(model: str, lane: str, packages_path: str, output: str, max_samples: int) -> dict[str, Any]:
    if model not in MODELS or lane not in LANES:
        raise ValueError((model, lane))
    r = REFS[model]
    here = Path(__file__).resolve().parent

    params: dict[str, Any] = {
        "ombh2": sampled("ombh2", r["ombh2"]), "omch2": sampled("omch2", r["omch2"]),
        "H0": sampled("H0", r["H0"]), "logA": sampled("logA", r["logA"]),
        "As": {"value": "lambda logA: 1e-10*np.exp(logA)", "derived": True, "latex": "A_s"},
        "ns": sampled("ns", r["ns"]), "tau": sampled("tau", r["tau"]),
        "A_act": sampled("A_act", r["A_act"]), "P_act": sampled("P_act", r["P_act"]),
        "peer_zc": {"value": 3.81, "latex": "\\log_{10}(z_c)"},
        "peer_thetai": {"value": 2.89155, "latex": "\\theta_i"},
        "omegam": {"derived": "lambda omch2, ombh2, H0: (omch2+ombh2)/(H0/100.)**2"},
        "sigma8": {"derived": True}, "S8": {"derived": "lambda sigma8, omegam: sigma8*(omegam/0.3)**0.5"},
        "rdrag": {"derived": True}, "thetastar": {"derived": True},
    }
    params["peer_fede"] = sampled("peer_fede", r["peer_fede"]) if model in ("M2", "M3") else {"value": 0.0}
    params["Alens"] = sampled("Alens", r["Alens"]) if model in ("M1", "M3") else {"value": 1.0}
    if lane == "A":
        params["A_planck"] = {"value": "lambda A_act: A_act", "derived": False}
    else:
        params["A_planck"] = sampled("A_planck", r["A_planck"])

    likelihood: dict[str, Any] = {
        "act_dr6_cmbonly": {"stop_at_error": True},
        "planck_2018_lowl.TT": {"stop_at_error": True},
        "planck_2018_lowl.EE_sroll2": {"stop_at_error": True},
        "planck_2018_lensing.native": {"stop_at_error": True},
        "bao.desi_dr2.desi_bao_all": {"stop_at_error": True},
        "shoes_h0.SH0ESGaussian": {"python_path": str(here), "mean": 73.04, "sigma": 1.04, "stop_at_error": True},
    }
    if lane == "A":
        likelihood["act_dr6_cmbonly.PlanckActCut"] = {"stop_at_error": True}
    else:
        likelihood["planck_full_lite.PlanckFullLite"] = {"python_path": str(here), "stop_at_error": True}

    for like in likelihood:
        params[f"chi2__{like}"] = {"derived": True}

    return {
        "packages_path": packages_path, "output": output, "force": True, "debug": False,
        "theory": {"peer_scalar_n3.PEERScalarN3": {
            "python_path": str(here), "path": "global", "stop_at_error": True,
            "extra_args": {"mnu": 0.06, "omk": 0.0, "nnu": 3.046, "num_massive_neutrinos": 1,
                           "lens_potential_accuracy": 0, "lmax": 9000,
                           "DoLateRadTruncation": False, "halofit_version": "mead2020"}}},
        "likelihood": likelihood,
        "prior": {"act_calibration_prior": "lambda A_act: stats.norm.logpdf(A_act,loc=1.,scale=.003)"},
        "params": params,
        "sampler": {"mcmc": {
            "Rminus1_stop": 0.01, "Rminus1_cl_stop": 0.05, "burn_in": 200,
            "learn_proposal": True, "learn_proposal_Rminus1_max": 50.0, "proposal_scale": 1.2,
            "max_samples": int(max_samples), "seed": 2026072990 + MODELS.index(model) * 10 + LANES.index(lane),
            "output_every": 60, "measure_speeds": False, "oversample_power": 0.0,
            "oversample_thin": False, "drag": False, "max_tries": "100d"}},
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--model", choices=MODELS, required=True); p.add_argument("--lane", choices=LANES, required=True)
    p.add_argument("--packages-path", required=True); p.add_argument("--root", required=True)
    p.add_argument("--max-samples", type=int, default=4000)
    args = p.parse_args(); root = Path(args.root).resolve()
    (root / "configs").mkdir(parents=True, exist_ok=True); (root / "mcmc").mkdir(parents=True, exist_ok=True)
    (root / "logs").mkdir(parents=True, exist_ok=True)
    info = build(args.model, args.lane, args.packages_path, str(root / "mcmc" / "chain"), args.max_samples)
    (root / "configs" / "mcmc.yaml").write_text(yaml.safe_dump(info, sort_keys=False), encoding="utf-8")
    (root / "manifest.json").write_text(json.dumps({
        "model": args.model, "lane": args.lane,
        "stack": "ACT DR6 + Planck + Sroll2 + Planck lensing + DESI DR2 + SH0ES",
        "sampling_coordinate": "H0 direct", "camb_precision": "ACT validated production precision",
        "cosmorec_policy": "posterior landmarks re-evaluated separately", "max_samples": args.max_samples}, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
