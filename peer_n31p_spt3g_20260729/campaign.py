#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Any

import yaml

from act_dr6_mcmc_20260729.campaign import base_info, jittered_ref, apply_ref

MODELS = {
    "N31P": "M2",
    "N31P_ALENS": "M3",
}


def build_spt_info(model: str, packages_path: str, output: str, ref_scale: float = 1.0) -> dict[str, Any]:
    if model not in MODELS:
        raise ValueError(f"Unknown model: {model}")
    source_model = MODELS[model]
    info = copy.deepcopy(base_info(source_model, packages_path, output, ref_scale=ref_scale))

    # Remove ACT-specific calibration and likelihoods. The SPT lane deliberately
    # combines Planck low-l only with SPT-3G high-l to avoid an unmodelled
    # Planck/SPT high-l overlap covariance.
    for par in ("A_act", "P_act", "A_planck"):
        info["params"].pop(par, None)
    info.get("prior", {}).pop("act_calibration_prior", None)

    for like_name in ("act_dr6_cmbonly", "act_dr6_cmbonly.PlanckActCut"):
        info["likelihood"].pop(like_name, None)
        info["params"].pop(f"chi2__{like_name}", None)

    info["likelihood"]["spt3g_2022.TTTEEE"] = {"stop_at_error": True}
    info["params"]["chi2__spt3g_2022.TTTEEE"] = {"derived": True}
    info["force"] = True
    return info


def write_configs(model: str, packages_path: str, root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "configs").mkdir(exist_ok=True)
    (root / "logs").mkdir(exist_ok=True)

    source_model = MODELS[model]
    evaluate = build_spt_info(model, packages_path, str((root / "evaluate" / "chain").resolve()))
    apply_ref(evaluate, jittered_ref(source_model, 2026072950 + (0 if model == "N31P" else 100)))
    evaluate["sampler"] = {"evaluate": {"N": 1, "override": {}}}
    (root / "configs" / "evaluate.yaml").write_text(
        yaml.safe_dump(evaluate, sort_keys=False), encoding="utf-8"
    )

    mcmc = build_spt_info(model, packages_path, str((root / "mcmc" / "chain").resolve()))
    apply_ref(mcmc, jittered_ref(source_model, 2026072990 + (0 if model == "N31P" else 100)))
    mcmc["resume"] = False
    mcmc["sampler"] = {
        "mcmc": {
            "Rminus1_stop": 0.01,
            "Rminus1_cl_stop": 0.05,
            "burn_in": 300,
            "learn_proposal": True,
            "learn_proposal_Rminus1_max": 30.0,
            "max_samples": 50000,
            "proposal_scale": 1.2,
            "seed": 2026072991 + (0 if model == "N31P" else 100),
            "output_every": 60,
        }
    }
    (root / "configs" / "mcmc.yaml").write_text(
        yaml.safe_dump(mcmc, sort_keys=False), encoding="utf-8"
    )

    manifest = {
        "campaign": "PEER-N3-1P SPT-3G matched posterior",
        "model": model,
        "source_model": source_model,
        "stack": (
            "Planck low-l TT + Sroll2 EE + SPT-3G 2018 TTTEEE + "
            "Planck lensing + DESI DR2 BAO + SH0ES"
        ),
        "lane": "SPT3G_NO_PLANCK_HIGH_L_OVERLAP",
        "peer_n": 3,
        "peer_log10_zc": 3.81,
        "peer_theta_i": 2.89155,
        "peer_prior": [0.0, 0.18],
        "alens": "fixed_1" if model == "N31P" else "uniform_0.5_1.5",
        "shoes": [73.04, 1.04],
        "convergence_gate": {
            "rank_rhat_minus_1_max": 0.01,
            "cobaya_converged": True,
            "chains_min": 4,
            "burn_fraction": 0.30,
        },
        "software": {
            "camb": "1.6.6+CosmoRec PEER scalar n=3",
            "cobaya": "3.6.2",
            "spt_likelihoods_commit": "633c5a3da99bb6e78c60a7514f311fc3577965bc",
            "python": "3.11",
        },
    }
    (root / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True, choices=tuple(MODELS))
    parser.add_argument("--packages", required=True)
    parser.add_argument("--root", required=True, type=Path)
    args = parser.parse_args()
    write_configs(args.model, args.packages, args.root.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
