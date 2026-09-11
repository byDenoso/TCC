from __future__ import annotations

import argparse
import copy
import importlib.util
import json
from pathlib import Path
from typing import Any, Callable

import yaml

from peer_decisive_followups.production_contract import build_science_manifest

EXPECTED_LIKELIHOODS = {
    "act_dr6_cmbonly",
    "act_dr6_cmbonly.PlanckActCut",
    "planck_2018_lowl.TT",
    "planck_2018_lowl.EE_sroll2",
    "planck_2018_lensing.native",
    "bao.desi_dr2.desi_bao_all",
    "shoes_h0.SH0ESGaussian",
}

PRODUCTION_POLYCHORD = {
    "nlive": 400,
    "num_repeats": "5d",
    "nprior": "20nlive",
    "do_clustering": True,
    "precision_criterion": 0.001,
    "max_ndead": 50000,
    "boost_posterior": 2,
    "synchronous": False,
    "write_resume": True,
    "read_resume": True,
    "write_stats": True,
}

PRIOR_POLYCHORD_OVERRIDES = {
    "nlive": "15d",
    "num_repeats": "2d",
    "precision_criterion": 0.0005,
}


def _load_base_info(science_dir: Path) -> Callable[..., dict[str, Any]]:
    campaign = Path(science_dir) / "act_dr6_mcmc_20260729" / "campaign.py"
    if not campaign.is_file():
        raise FileNotFoundError(f"canonical campaign.py not found: {campaign}")
    module_name = f"peer_campaign_{abs(hash(str(campaign.resolve())))}"
    spec = importlib.util.spec_from_file_location(module_name, campaign)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load campaign module: {campaign}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    base_info = getattr(module, "base_info", None)
    if not callable(base_info):
        raise RuntimeError("canonical campaign has no callable base_info")
    return base_info


def _assert_prior(info: dict[str, Any], name: str, lo: float, hi: float) -> None:
    spec = info.get("params", {}).get(name)
    if not isinstance(spec, dict) or not isinstance(spec.get("prior"), dict):
        raise ValueError(f"{name} must be sampled with the frozen prior")
    prior = spec["prior"]
    if float(prior.get("min")) != lo or float(prior.get("max")) != hi:
        raise ValueError(f"{name} prior drift: expected [{lo}, {hi}], got {prior}")


def validate_frozen_config(path: Path, model: str) -> dict[str, Any]:
    if model not in {"M1", "M3"}:
        raise ValueError("production model must be M1 or M3")
    info = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(info, dict):
        raise ValueError("production config must be a mapping")
    likes = set((info.get("likelihood") or {}).keys())
    if likes != EXPECTED_LIKELIHOODS:
        raise ValueError(f"likelihood stack drift: expected {sorted(EXPECTED_LIKELIHOODS)}, got {sorted(likes)}")

    params = info.get("params", {})
    _assert_prior(info, "tau", 0.0, 0.10)
    _assert_prior(info, "Alens", 0.5, 1.5)
    if model == "M3":
        _assert_prior(info, "peer_fede", 0.0, 0.18)
    else:
        peer = params.get("peer_fede")
        if not isinstance(peer, dict) or float(peer.get("value", float("nan"))) != 0.0:
            raise ValueError("M1 peer_fede must remain fixed at 0.0")
    for name, expected in (("peer_zc", 3.81), ("peer_thetai", 2.89155)):
        spec = params.get(name)
        if not isinstance(spec, dict) or float(spec.get("value", float("nan"))) != expected:
            raise ValueError(f"{name} drift: expected {expected}")

    pc = ((info.get("sampler") or {}).get("polychord") or {})
    for key, expected in PRODUCTION_POLYCHORD.items():
        if pc.get(key) != expected:
            raise ValueError(f"PolyChord setting drift for {key}: expected {expected!r}, got {pc.get(key)!r}")
    if not isinstance(pc.get("seed"), int):
        raise ValueError("PolyChord seed must be explicit and deterministic")
    return info


def build_production_configs(science_dir: Path, model: str, packages: str,
                             root: Path, seed: int, continuation: bool = False) -> dict[str, Any]:
    if model not in {"M1", "M3"}:
        raise ValueError("production model must be M1 or M3")
    root = Path(root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    base_info = _load_base_info(Path(science_dir))

    data = base_info(model, packages, str((root / "data" / "chain").resolve()))
    data["resume"] = bool(continuation)
    data["force"] = not continuation
    data["sampler"] = {"polychord": {**PRODUCTION_POLYCHORD, "seed": int(seed)}}
    data_path = root / "data.yaml"
    data_path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    validate_frozen_config(data_path, model)

    prior = copy.deepcopy(data)
    prior["output"] = str((root / "prior_volume" / "chain").resolve())
    prior.pop("theory", None)
    prior["likelihood"] = {"one": None}
    prior["params"] = {
        name: spec
        for name, spec in prior["params"].items()
        if isinstance(spec, dict) and "prior" in spec
    }
    prior["sampler"] = {
        "polychord": {
            **PRODUCTION_POLYCHORD,
            **PRIOR_POLYCHORD_OVERRIDES,
            "seed": int(seed) + 90000,
        }
    }
    prior_path = root / "prior_volume.yaml"
    prior_path.write_text(yaml.safe_dump(prior, sort_keys=False), encoding="utf-8")

    science_manifest = build_science_manifest(model, data)
    (root / "science_manifest.json").write_text(
        json.dumps(science_manifest, indent=2, sort_keys=True), encoding="utf-8"
    )
    execution_manifest = {
        "schema": "peer-nested-production-config-v1",
        "model": model,
        "seed": int(seed),
        "continuation": bool(continuation),
        "data_config": "data.yaml",
        "prior_config": "prior_volume.yaml",
        "normalized_evidence": "logZ_data - logZ_prior_volume",
        "production_polychord": PRODUCTION_POLYCHORD,
        "prior_overrides": PRIOR_POLYCHORD_OVERRIDES,
    }
    (root / "production_manifest.json").write_text(
        json.dumps(execution_manifest, indent=2, sort_keys=True), encoding="utf-8"
    )
    return {
        "data": data,
        "prior": prior,
        "science_manifest": science_manifest,
        "execution_manifest": execution_manifest,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--science", type=Path, required=True)
    parser.add_argument("--model", choices=["M1", "M3"], required=True)
    parser.add_argument("--packages", required=True)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--continuation", action="store_true")
    args = parser.parse_args()
    build_production_configs(
        args.science, args.model, args.packages, args.root, args.seed,
        continuation=args.continuation,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
