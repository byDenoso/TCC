#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Iterable

import arviz as az
import numpy as np
import pandas as pd
import yaml

DEFAULT_PARAMS = [
    "H0", "ombh2", "omch2", "cosmomc_theta", "tau", "logA", "ns",
    "peer_fede", "Alens", "rdrag", "omegam", "sigma8", "S8", "A_act", "P_act",
]


def expand_trace(values: np.ndarray, weights: np.ndarray, max_draws: int = 200_000) -> np.ndarray:
    """Reconstruct a Metropolis trace from Cobaya's run-length encoded weights."""
    values = np.asarray(values, dtype=float)
    weights = np.asarray(weights, dtype=float)
    mask = np.isfinite(values) & np.isfinite(weights) & (weights > 0)
    values, weights = values[mask], weights[mask]
    if values.size == 0:
        return np.empty(0, dtype=float)
    counts = np.maximum(1, np.rint(weights).astype(np.int64))
    expanded = np.repeat(values, counts)
    if expanded.size <= max_draws:
        return expanded.astype(float, copy=False)
    indices = np.linspace(0, expanded.size - 1, max_draws, dtype=np.int64)
    return expanded[indices].astype(float, copy=False)


def _read_chain(path: Path) -> pd.DataFrame:
    header = None
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            if line.startswith("#"):
                header = line.lstrip("#").split()
                break
    if not header:
        raise ValueError(f"Missing header in {path}")
    return pd.read_csv(path, sep=r"\s+", comment="#", names=header, engine="python")


def _checkpoint(root: Path) -> dict:
    path = root / "mcmc" / "chain.checkpoint"
    if not path.exists():
        return {"exists": False, "converged": False, "Rminus1_last": None}
    raw = yaml.safe_load(path.read_text(encoding="utf-8", errors="replace")) or {}
    mcmc = (raw.get("sampler") or {}).get("mcmc") or {}
    value = mcmc.get("Rminus1_last")
    try:
        value = float(value)
    except (TypeError, ValueError):
        value = None
    return {"exists": True, "converged": bool(mcmc.get("converged", False)), "Rminus1_last": value}


def _finite_max(values: Iterable[float]) -> float | None:
    arr = np.asarray(list(values), dtype=float)
    arr = arr[np.isfinite(arr)]
    return float(arr.max()) if arr.size else None


def _finite_min(values: Iterable[float]) -> float | None:
    arr = np.asarray(list(values), dtype=float)
    arr = arr[np.isfinite(arr)]
    return float(arr.min()) if arr.size else None


def diagnose(root: str | Path, burn_fraction: float = 0.30, params: list[str] | None = None,
             max_draws_per_chain: int = 200_000, rhat_minus1_limit: float = 0.01) -> dict:
    root = Path(root).resolve()
    chain_paths = sorted((root / "mcmc").glob("chain.*.txt"))
    checkpoint = _checkpoint(root)
    requested = params or DEFAULT_PARAMS
    errors: list[dict[str, str]] = []
    frames: list[tuple[Path, pd.DataFrame]] = []
    for path in chain_paths:
        try:
            frames.append((path, _read_chain(path)))
        except Exception as exc:
            errors.append({"path": str(path), "error": f"{type(exc).__name__}: {exc}"})

    common_params = [p for p in requested if frames and all(p in frame.columns for _, frame in frames)]
    traces: dict[str, list[np.ndarray]] = {p: [] for p in common_params}
    per_chain: list[dict] = []
    for path, frame in frames:
        if "weight" not in frame:
            errors.append({"path": str(path), "error": "Missing weight column"})
            continue
        row = {"path": str(path), "compressed_rows": int(len(frame)), "expanded_draws": {}}
        for p in common_params:
            trace = expand_trace(frame[p].to_numpy(float), frame["weight"].to_numpy(float),
                                 max_draws=max_draws_per_chain)
            trace = trace[int(trace.size * burn_fraction):]
            traces[p].append(trace)
            row["expanded_draws"][p] = int(trace.size)
        per_chain.append(row)

    usable_params: dict[str, np.ndarray] = {}
    for p, chains in traces.items():
        if len(chains) < 2 or any(chain.size < 20 for chain in chains):
            continue
        equal_draws = min(chain.size for chain in chains)
        usable_params[p] = np.stack([chain[-equal_draws:] for chain in chains], axis=0)

    rhat: dict[str, float] = {}
    ess_bulk: dict[str, float] = {}
    ess_tail: dict[str, float] = {}
    if usable_params:
        rh = az.rhat(usable_params, method="rank")
        eb = az.ess(usable_params, method="bulk")
        et = az.ess(usable_params, method="tail")
        for p in usable_params:
            rhat[p] = float(np.asarray(rh[p]).squeeze())
            ess_bulk[p] = float(np.asarray(eb[p]).squeeze())
            ess_tail[p] = float(np.asarray(et[p]).squeeze())

    rhat_minus1 = {p: value - 1.0 for p, value in rhat.items()}
    rhat_minus1_max = _finite_max(rhat_minus1.values())
    ess_bulk_min = _finite_min(ess_bulk.values())
    ess_tail_min = _finite_min(ess_tail.values())
    n_chains = len(frames)
    diagnostics_finite = rhat_minus1_max is not None and math.isfinite(rhat_minus1_max)
    converged = bool(n_chains >= 4 and checkpoint["converged"] and diagnostics_finite
                     and rhat_minus1_max < rhat_minus1_limit)
    return {
        "root": str(root), "burn_fraction": burn_fraction,
        "n_chain_files": len(chain_paths), "n_chains_read": n_chains,
        "params_requested": requested, "params_diagnosed": list(usable_params),
        "chains": per_chain, "errors": errors, "cobaya": checkpoint,
        "rank_rhat": rhat, "rank_rhat_minus1": rhat_minus1,
        "rhat_minus1_max": rhat_minus1_max,
        "ess_bulk": ess_bulk, "ess_tail": ess_tail,
        "ess_bulk_min": ess_bulk_min, "ess_tail_min": ess_tail_min,
        "gate": {"minimum_chains": 4, "rhat_minus1_limit": rhat_minus1_limit,
                 "requires_cobaya_converged": True},
        "converged": converged,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Independent rank-Rhat/ESS gate for Cobaya chains")
    parser.add_argument("--root", required=True)
    parser.add_argument("--burn", type=float, default=0.30)
    parser.add_argument("--output", default=None)
    parser.add_argument("--max-draws-per-chain", type=int, default=200_000)
    parser.add_argument("--rhat-minus1-limit", type=float, default=0.01)
    parser.add_argument("--params", nargs="*", default=None)
    args = parser.parse_args()
    result = diagnose(args.root, burn_fraction=args.burn, params=args.params,
                      max_draws_per_chain=args.max_draws_per_chain,
                      rhat_minus1_limit=args.rhat_minus1_limit)
    output = Path(args.output) if args.output else Path(args.root) / "convergence_gate.json"
    output.write_text(json.dumps(result, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps({"converged": result["converged"], "n_chains": result["n_chains_read"],
                      "rhat_minus1_max": result["rhat_minus1_max"],
                      "ess_bulk_min": result["ess_bulk_min"],
                      "ess_tail_min": result["ess_tail_min"], "output": str(output)}, indent=2))
    return 0 if result["converged"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
