#!/usr/bin/env python3
from __future__ import annotations
import argparse, json
from pathlib import Path

MODELS = ("M0", "M1", "M2", "M3")
PARAMS = ("H0", "peer_fede", "Alens", "ns", "rdrag", "S8", "A_act", "A_planck")


def _load(root: Path):
    best = json.loads((root / "best_minimum.json").read_text(encoding="utf-8"))
    gate_path = root / "convergence_gate.json"
    gate = json.loads(gate_path.read_text(encoding="utf-8")) if gate_path.exists() else {"converged": False}
    return best, gate


def compare_lanes(lane_a, lane_b):
    lane_a, lane_b = Path(lane_a).resolve(), Path(lane_b).resolve()
    models, flags = {}, []
    for model in MODELS:
        a, ga = _load(lane_a / model)
        b, gb = _load(lane_b / model)
        available = [p for p in PARAMS if p in a and p in b]
        models[model] = {
            "lane_a": {p: float(a[p]) for p in available},
            "lane_b": {p: float(b[p]) for p in available},
            "shift": {p: float(b[p]) - float(a[p]) for p in available},
            "lane_a_converged": bool(ga.get("converged", False)),
            "lane_b_converged": bool(gb.get("converged", False)),
        }
        flags += [models[model]["lane_a_converged"], models[model]["lane_b_converged"]]
    return {
        "lane_a": str(lane_a), "lane_b": str(lane_b), "models": models,
        "all_converged": all(flags),
        "cross_lane_delta_chi2_is_model_selection": False,
        "interpretation": "Lane B is an overlapping-data robustness stress test. Use parameter shifts and within-lane contrasts only."
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--lane-a", required=True)
    parser.add_argument("--lane-b", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    result = compare_lanes(args.lane_a, args.lane_b)
    Path(args.output).write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0 if result["all_converged"] else 2

if __name__ == "__main__":
    raise SystemExit(main())
