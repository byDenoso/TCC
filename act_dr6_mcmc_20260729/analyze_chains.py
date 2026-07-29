#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

PARAMS = ["H0", "ombh2", "omch2", "cosmomc_theta", "tau", "logA", "As", "ns", "peer_fede", "Alens", "rdrag", "omegam", "sigma8", "S8", "A_act", "P_act"]


def weighted_quantile(x: np.ndarray, w: np.ndarray, q: float) -> float:
    order = np.argsort(x)
    x = x[order]
    w = w[order]
    c = np.cumsum(w)
    if c[-1] <= 0:
        return float("nan")
    return float(np.interp(q * c[-1], c, x))


def read_chain(path: Path, burn_fraction: float) -> pd.DataFrame:
    with path.open("r", encoding="utf-8", errors="replace") as f:
        header = None
        for line in f:
            if line.startswith("#"):
                header = line.lstrip("#").split()
                break
    if not header:
        raise ValueError(f"No header in {path}")
    df = pd.read_csv(path, sep=r"\s+", comment="#", names=header, engine="python")
    return df.iloc[int(len(df) * burn_fraction):].copy()


def corr(df: pd.DataFrame, a: str, b: str) -> float | None:
    if a not in df or b not in df or "weight" not in df:
        return None
    x = df[a].to_numpy(float)
    y = df[b].to_numpy(float)
    w = df["weight"].to_numpy(float)
    w = w / w.sum()
    mx, my = np.sum(w * x), np.sum(w * y)
    vx, vy = np.sum(w * (x - mx) ** 2), np.sum(w * (y - my) ** 2)
    if vx <= 0 or vy <= 0:
        return None
    return float(np.sum(w * (x - mx) * (y - my)) / np.sqrt(vx * vy))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--burn", type=float, default=0.30)
    args = ap.parse_args()
    root = Path(args.root).resolve()
    frames = []
    per_chain = []
    for path in sorted(root.glob("mcmc/chain.*.txt")):
        try:
            df = read_chain(path, args.burn)
            frames.append(df)
            per_chain.append({"path": str(path), "rows_after_burn": len(df), "weight_sum": float(df["weight"].sum())})
        except Exception as exc:
            per_chain.append({"path": str(path), "error": str(exc)})
    checkpoint = {}
    cp = root / "mcmc/chain.checkpoint"
    if cp.exists():
        checkpoint = yaml.safe_load(cp.read_text(encoding="utf-8")) or {}
    progress_tail = []
    pp = root / "mcmc/chain.progress"
    if pp.exists():
        progress_tail = pp.read_text(encoding="utf-8", errors="replace").splitlines()[-20:]
    out = {"model": args.model, "burn_fraction": args.burn, "chains": per_chain,
           "checkpoint": checkpoint, "progress_tail": progress_tail,
           "posterior": {}, "correlations": {}}
    if frames:
        all_df = pd.concat(frames, ignore_index=True, sort=False)
        w = all_df["weight"].to_numpy(float)
        for p in PARAMS:
            if p not in all_df:
                continue
            x = all_df[p].to_numpy(float)
            mask = np.isfinite(x) & np.isfinite(w) & (w > 0)
            if not mask.any():
                continue
            xx, ww = x[mask], w[mask]
            out["posterior"][p] = {
                "mean": float(np.average(xx, weights=ww)),
                "q16": weighted_quantile(xx, ww, 0.16),
                "median": weighted_quantile(xx, ww, 0.50),
                "q84": weighted_quantile(xx, ww, 0.84),
            }
        for a, b in [("ns", "peer_fede"), ("ns", "H0"), ("peer_fede", "H0"), ("Alens", "peer_fede"), ("Alens", "ns")]:
            value = corr(all_df, a, b)
            if value is not None:
                out["correlations"][f"{a}__{b}"] = value
        chi_cols = [c for c in all_df.columns if c.startswith("chi2__")]
        if chi_cols:
            score = all_df[chi_cols].sum(axis=1)
            i = int(score.idxmin())
            out["best_sample_chi2"] = {"total": float(score.loc[i]), **{c: float(all_df.loc[i, c]) for c in chi_cols}}
    (root / "posterior_summary.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
