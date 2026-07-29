#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import json
import random
from pathlib import Path
from typing import Any

import yaml

FULL_PLANCK_LIKE = "planck_2018_highl_plik.TTTEEE_lite_native"
PACT_LIKE = "act_dr6_cmbonly.PlanckActCut"


def configure_lane_b(info: dict[str, Any]) -> dict[str, Any]:
    """Transform a matched Lane-A config into the full-range Planck robustness lane."""
    out = copy.deepcopy(info)
    likes = out.setdefault("likelihood", {})
    likes.pop(PACT_LIKE, None)
    likes[FULL_PLANCK_LIKE] = {"stop_at_error": True}
    params = out.setdefault("params", {})
    params["A_planck"] = {
        "prior": {"min": 0.9, "max": 1.1},
        "ref": {"dist": "norm", "loc": 1.0, "scale": 0.002},
        "proposal": 0.001,
        "latex": "A_\\mathrm{Planck}",
    }
    params.pop(f"chi2__{PACT_LIKE}", None)
    params[f"chi2__{FULL_PLANCK_LIKE}"] = {"derived": True}
    priors = out.setdefault("prior", {})
    priors["act_calibration_prior"] = "lambda A_act: stats.norm.logpdf(A_act, loc=1.0, scale=0.003)"
    priors["planck_calibration_prior"] = "lambda A_planck: stats.norm.logpdf(A_planck, loc=1.0, scale=0.0025)"
    return out


def _campaign_module():
    import campaign
    return campaign


def _apply_seed_refs(info: dict[str, Any], seed_values: dict[str, float] | None) -> None:
    if not seed_values:
        return
    for name, value in seed_values.items():
        spec = info.get("params", {}).get(name)
        if isinstance(spec, dict) and "prior" in spec:
            spec["ref"] = float(value)


def _read_seed(path: str | None) -> dict[str, float] | None:
    if not path:
        return None
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if "best_minimum" in raw and isinstance(raw["best_minimum"], dict):
        raw = raw["best_minimum"]
    return {k: float(v) for k, v in raw.items() if isinstance(v, (int, float))}


def write_configs(model: str, packages: str, root: Path, lane_a_best: str | None = None,
                  lane_a_covmat: str | None = None) -> None:
    campaign = _campaign_module()
    root.mkdir(parents=True, exist_ok=True)
    cfg = root / "configs"
    cfg.mkdir(exist_ok=True)
    seed_values = _read_seed(lane_a_best)
    for i in range(8):
        seed = 2026072950 + i + {"M0": 0, "M1": 100, "M2": 200, "M3": 300}[model]
        info = configure_lane_b(campaign.base_info(
            model, packages, str((root / f"minimize/start_{i+1}/chain").resolve())))
        if seed_values:
            _apply_seed_refs(info, seed_values)
            rng = random.Random(seed)
            for name, spec in info["params"].items():
                if not (isinstance(spec, dict) and "prior" in spec and name in seed_values):
                    continue
                proposal = float(spec.get("proposal", 0.0) or 0.0)
                lo, hi = float(spec["prior"]["min"]), float(spec["prior"]["max"])
                value = float(seed_values[name]) + rng.gauss(0.0, max(proposal * 3.0, 1e-8))
                spec["ref"] = min(max(value, lo + 1e-8), hi - 1e-8)
        info["sampler"] = {"minimize": {
            "ignore_prior": False, "best_of": 1, "max_evals": 9000,
            "seed": seed, "method": "scipy",
            "override_scipy": {"method": "Powell",
                               "options": {"maxiter": 1000, "xtol": 1e-4, "ftol": 1e-8}},
        }}
        (cfg / f"minimize_{i+1}.yaml").write_text(yaml.safe_dump(info, sort_keys=False), encoding="utf-8")

    mcmc = configure_lane_b(campaign.base_info(model, packages, str((root / "mcmc/chain").resolve())))
    _apply_seed_refs(mcmc, seed_values)
    mcmc["resume"] = True
    if lane_a_covmat and Path(lane_a_covmat).exists():
        mcmc["covmat"] = str(Path(lane_a_covmat).resolve())
    mcmc["sampler"] = {"mcmc": {
        "Rminus1_stop": 0.01, "Rminus1_cl_stop": 0.05,
        "burn_in": 300, "learn_proposal": True,
        "learn_proposal_Rminus1_max": 30.0, "max_samples": 30000,
        "proposal_scale": 1.2,
        "seed": 2026073049 + {"M0": 0, "M1": 100, "M2": 200, "M3": 300}[model],
        "output_every": 60,
    }}
    (cfg / "mcmc.yaml").write_text(yaml.safe_dump(mcmc, sort_keys=False), encoding="utf-8")
    manifest = {
        "model": model, "lane": "B_FULL_PLANCK_PLIKLITE_NATIVE",
        "role": "robustness_only_overlap_intentional",
        "stack": "Planck low-l TT + Sroll2 EE + Planck high-l TTTEEE PlikLite native + ACT DR6 TTTEEE + Planck lensing + DESI DR2 BAO + SH0ES",
        "separate_calibrations": True,
        "planck_highl_likelihood": FULL_PLANCK_LIKE,
        "seeded_from_lane_a": bool(seed_values), "lane_a_covmat": lane_a_covmat,
        "no_sample_sharing": True,
    }
    (root / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def promote_best(model: str, root: Path) -> None:
    campaign = _campaign_module()
    rows = []
    for path in sorted(root.glob("minimize/start_*/chain.minimum.txt")):
        try:
            row = campaign.parse_minimum(path)
            row["source"] = str(path)
            rows.append(row)
        except Exception:
            pass
    if not rows:
        raise SystemExit("No valid Lane-B minima found")
    best = min(rows, key=lambda row: row["minuslogpost"])
    cfg_path = root / "configs/mcmc.yaml"
    info = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
    _apply_seed_refs(info, best)
    cfg_path.write_text(yaml.safe_dump(info, sort_keys=False), encoding="utf-8")
    (root / "best_minimum.json").write_text(json.dumps(best, indent=2), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    write = sub.add_parser("write-configs")
    write.add_argument("--model", choices=("M0", "M1", "M2", "M3"), required=True)
    write.add_argument("--packages", required=True)
    write.add_argument("--root", required=True)
    write.add_argument("--lane-a-best")
    write.add_argument("--lane-a-covmat")
    promote = sub.add_parser("promote-best")
    promote.add_argument("--model", choices=("M0", "M1", "M2", "M3"), required=True)
    promote.add_argument("--root", required=True)
    args = parser.parse_args()
    if args.cmd == "write-configs":
        write_configs(args.model, args.packages, Path(args.root).resolve(),
                      lane_a_best=args.lane_a_best, lane_a_covmat=args.lane_a_covmat)
        return 0
    promote_best(args.model, Path(args.root).resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
