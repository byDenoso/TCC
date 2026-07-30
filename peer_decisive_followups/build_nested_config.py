#!/usr/bin/env python3
from __future__ import annotations
import argparse, copy, json, sys
from pathlib import Path
import yaml

PC = {
    "nlive": "25d", "num_repeats": "5d", "nprior": "20nlive",
    "do_clustering": True, "precision_criterion": 0.001,
    "max_ndead": 50000, "boost_posterior": 2,
    "synchronous": False, "write_resume": True, "read_resume": True,
    "write_stats": True,
}

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--science", type=Path, required=True)
    ap.add_argument("--model", choices=["M0", "M1", "M2", "M3"], required=True)
    ap.add_argument("--packages", required=True)
    ap.add_argument("--root", type=Path, required=True)
    ap.add_argument("--seed", type=int, required=True)
    args = ap.parse_args()
    sys.path.insert(0, str(args.science / "act_dr6_mcmc_20260729"))
    from campaign import base_info
    args.root.mkdir(parents=True, exist_ok=True)
    info = base_info(args.model, args.packages, str((args.root / "data" / "chain").resolve()))
    info["resume"] = False; info["force"] = True
    info["sampler"] = {"polychord": {**PC, "seed": args.seed}}
    (args.root / "data.yaml").write_text(yaml.safe_dump(info, sort_keys=False), encoding="utf-8")

    prior = copy.deepcopy(info)
    prior["output"] = str((args.root / "prior_volume" / "chain").resolve())
    prior.pop("theory", None)
    prior["likelihood"] = {"one": None}
    prior["params"] = {
        name: spec for name, spec in prior["params"].items()
        if isinstance(spec, dict) and "prior" in spec
    }
    prior["sampler"] = {"polychord": {**PC, "nlive": "15d", "num_repeats": "2d", "precision_criterion": 0.0005, "seed": args.seed + 90000}}
    (args.root / "prior_volume.yaml").write_text(yaml.safe_dump(prior, sort_keys=False), encoding="utf-8")
    manifest = {
        "model": args.model, "seed": args.seed, "sampler": "PolyChord",
        "normalized_evidence": "logZ_data - logZ_prior_volume",
        "completion_gate": "Both runs must exit 0 and expose logZ/logZstd; otherwise evidence is INCOMPLETE.",
        "settings": PC,
    }
    (args.root / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return 0
if __name__ == "__main__": raise SystemExit(main())
