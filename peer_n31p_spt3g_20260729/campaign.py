#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
from pathlib import Path
from typing import Any

import yaml

from act_dr6_mcmc_20260729.campaign import base_info, jittered_ref, apply_ref

MODELS = {
    "N31P": "M2",
    "N31P_ALENS": "M3",
}

SPT_D1_DATASET = "spt_candl_data.SPT3G_D1_TnE"
SPT_D1_CLASS = "candl.interface.CandlCobayaLikelihood"

# Parameters owned by the PEER/base cosmology contract. The official SPT
# template is authoritative for SPT nuisance parameters and their priors, but
# it must not silently widen or replace the cosmological priors used by PEER.
SPT_TEMPLATE_COSMOLOGY_PARAMS = {
    "A",
    "As",
    "DHBBN",
    "YHe",
    "Y_p",
    "age",
    "clamp",
    "cosmomc_theta",
    "logA",
    "H0",
    "ns",
    "ombh2",
    "omch2",
    "omega_de",
    "omegam",
    "omegamh2",
    "rdrag",
    "s8h5",
    "s8omegamp25",
    "s8omegamp5",
    "sigma8",
    "tau",
    "theta_MC_100",
    "zrei",
}


def _load_official_spt_template(path: Path) -> tuple[dict[str, Any], str]:
    path = Path(path)
    raw = path.read_text(encoding="utf-8")
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()

    # The upstream Cobaya template uses PyYAML python/name tags for executable
    # objects. We only need its declarative nuisance/prior contract here, so
    # normalize those tags to strings and keep safe_load fail-closed.
    safe_text = re.sub(r"!!python/name:([^\s]+)\s+''", r"'\1'", raw)
    template = yaml.safe_load(safe_text)
    if not isinstance(template, dict):
        raise ValueError(f"Invalid SPT D1 template: {path}")

    try:
        spt_like = template["likelihood"]["candl_like"]
        dataset = spt_like["data_set_file"]
    except (KeyError, TypeError) as exc:
        raise ValueError("SPT D1 template is missing likelihood.candl_like.data_set_file") from exc
    if dataset != SPT_D1_DATASET:
        raise ValueError(f"Unexpected SPT D1 dataset {dataset!r}; expected {SPT_D1_DATASET!r}")
    if not isinstance(template.get("params"), dict) or not isinstance(template.get("prior", {}), dict):
        raise ValueError("SPT D1 template is missing params/prior mappings")
    return template, digest


def build_spt_info(
    model: str,
    packages_path: str,
    output: str,
    *,
    spt_template: Path,
    ref_scale: float = 1.0,
) -> dict[str, Any]:
    if model not in MODELS:
        raise ValueError(f"Unknown model: {model}")
    source_model = MODELS[model]
    info = copy.deepcopy(base_info(source_model, packages_path, output, ref_scale=ref_scale))
    template, _ = _load_official_spt_template(spt_template)

    # Remove ACT-specific calibration and likelihoods. This lane deliberately
    # combines Planck low-l only with SPT-3G D1 high-l to avoid an unmodelled
    # Planck/SPT high-l overlap covariance.
    for par in ("A_act", "P_act", "A_planck"):
        info["params"].pop(par, None)
    info.get("prior", {}).pop("act_calibration_prior", None)

    for like_name in ("act_dr6_cmbonly", "act_dr6_cmbonly.PlanckActCut"):
        info["likelihood"].pop(like_name, None)
        info["params"].pop(f"chi2__{like_name}", None)

    # Merge the official D1 nuisance model without allowing its broad reference
    # cosmology priors to overwrite the frozen PEER cosmological contract.
    for name, spec in template["params"].items():
        if name in SPT_TEMPLATE_COSMOLOGY_PARAMS:
            continue
        if name not in info["params"]:
            info["params"][name] = copy.deepcopy(spec)
    for name, spec in template.get("prior", {}).items():
        info["prior"][name] = copy.deepcopy(spec)

    info["likelihood"]["candl_like"] = {
        "class": SPT_D1_CLASS,
        "data_set_file": SPT_D1_DATASET,
        "clear_internal_priors": True,
        "feedback": True,
        "stop_at_error": True,
    }
    info["params"]["chi2__candl_like"] = {"derived": True}
    info["force"] = True
    return info


def write_configs(
    model: str,
    packages_path: str,
    root: Path,
    *,
    spt_template: Path,
    spt_data_ref: str,
) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "configs").mkdir(exist_ok=True)
    (root / "logs").mkdir(exist_ok=True)

    spt_template = Path(spt_template)
    _, spt_template_sha256 = _load_official_spt_template(spt_template)
    source_model = MODELS[model]
    evaluate = build_spt_info(
        model,
        packages_path,
        str((root / "evaluate" / "chain").resolve()),
        spt_template=spt_template,
    )
    apply_ref(evaluate, jittered_ref(source_model, 2026072950 + (0 if model == "N31P" else 100)))
    evaluate["sampler"] = {"evaluate": {"N": 1, "override": {}}}
    (root / "configs" / "evaluate.yaml").write_text(
        yaml.safe_dump(evaluate, sort_keys=False), encoding="utf-8"
    )

    mcmc = build_spt_info(
        model,
        packages_path,
        str((root / "mcmc" / "chain").resolve()),
        spt_template=spt_template,
    )
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
        "campaign": "PEER-N3-1P SPT-3G D1 matched posterior",
        "model": model,
        "source_model": source_model,
        "stack": (
            "Planck low-l TT + Sroll2 EE + SPT-3G D1 TT/TE/EE + "
            "Planck lensing + DESI DR2 BAO + SH0ES"
        ),
        "lane": "SPT3G_D1_NO_PLANCK_HIGH_L_OVERLAP",
        "spt_dataset": "SPT3G_D1_TnE",
        "spt_data_ref": spt_data_ref,
        "spt_template_sha256": spt_template_sha256,
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
            "candl": "2.0.3",
            "spt_candl_data_ref": spt_data_ref,
            "python": "3.11",
        },
    }
    (root / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True, choices=tuple(MODELS))
    parser.add_argument("--packages", required=True)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--spt-template", required=True, type=Path)
    parser.add_argument("--spt-data-ref", required=True)
    args = parser.parse_args()
    write_configs(
        args.model,
        args.packages,
        args.root.resolve(),
        spt_template=args.spt_template.resolve(),
        spt_data_ref=args.spt_data_ref,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
