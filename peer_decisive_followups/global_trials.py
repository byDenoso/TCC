#!/usr/bin/env python3
"""Local-vs-global calibration for the registered PEER amplitude scan.

The global statistic is the maximum improvement over the registered
f_PEER = 0.00..0.12 grid. It does not claim trials over z_c, theta_i,
model families, datasets, or analyst choices that were not included in
this null ensemble.
"""
from __future__ import annotations
import argparse, csv, json, math
from collections import defaultdict
from pathlib import Path

FGRID = tuple(round(i / 100, 2) for i in range(13))
SEEDS = (2026072301, 2026072302, 2026072303, 2026072304)


def read_rows(paths: list[Path]) -> list[dict]:
    latest = {}
    for path in paths:
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            key = (str(row.get("mock_id")), round(float(row.get("f_peer", -1)), 2), int(row.get("seed", -1)))
            latest[key] = row
    return list(latest.values())


def plus_one(k: int, n: int) -> float:
    return (k + 1.0) / (n + 1.0)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("inputs", nargs="+", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--observed-f", type=float, default=0.07)
    ap.add_argument("--t-obs", type=float, default=3.9453)
    args = ap.parse_args()
    rows = read_rows(args.inputs)
    by = defaultdict(lambda: defaultdict(dict))
    for row in rows:
        if row.get("status") != "COMPLETE":
            continue
        mid = str(row["mock_id"])
        f = round(float(row["f_peer"]), 2)
        seed = int(row["seed"])
        chi2 = float(row["chi2_total"])
        if f in FGRID and seed in SEEDS and math.isfinite(chi2):
            by[mid][f][seed] = chi2

    trials = []
    for mid in sorted(by):
        if any(set(by[mid].get(f, {})) != set(SEEDS) for f in FGRID):
            continue
        env = {f: min(by[mid][f].values()) for f in FGRID}
        t_by_f = {f: max(0.0, env[0.0] - env[f]) for f in FGRID}
        local = t_by_f[round(args.observed_f, 2)]
        global_t = max(t_by_f.values())
        best_f = max(t_by_f, key=t_by_f.get)
        trials.append({"mock_id": mid, "T_local": local, "T_global": global_t, "f_global_best": best_f})

    n = len(trials)
    k_local = sum(r["T_local"] >= args.t_obs for r in trials)
    k_global = sum(r["T_global"] >= args.t_obs for r in trials)
    p_local = plus_one(k_local, n) if n else None
    p_global = plus_one(k_global, n) if n else None
    summary = {
        "status": "COMPLETE" if n == 32 else "INCOMPLETE",
        "registered_scan": {"parameter": "f_PEER", "grid": list(FGRID), "observed_best": args.observed_f},
        "t_obs": args.t_obs,
        "n_valid_mocks": n,
        "local": {"k": k_local, "p_emp": p_local},
        "global": {"k": k_global, "p_emp": p_global},
        "trial_factor_empirical": (p_global / p_local if p_local and p_global else None),
        "scope": "Global only over the preregistered 13-point f_PEER amplitude grid.",
        "not_calibrated": ["peer_zc", "peer_thetai", "peer_n", "dataset selection", "model-family selection", "analysis-choice trials"],
    }
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "global_trials_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    with (args.out / "global_trials_mocks.csv").open("w", newline="", encoding="utf-8") as handle:
        w = csv.DictWriter(handle, fieldnames=["mock_id", "T_local", "T_global", "f_global_best"])
        w.writeheader(); w.writerows(trials)
    print(json.dumps(summary, indent=2))
    return 0 if n == 32 else 2

if __name__ == "__main__":
    raise SystemExit(main())
