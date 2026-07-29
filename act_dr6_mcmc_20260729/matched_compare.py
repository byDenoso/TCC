#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

MODELS = ("M0", "M1", "M2", "M3")
EXTRA_K = {"M0": 0, "M1": 1, "M2": 1, "M3": 2}
CONTRASTS = (("M2", "M0"), ("M1", "M0"), ("M3", "M1"), ("M3", "M2"))


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _best_path(root: Path) -> Path:
    direct = root / "best_minimum.json"
    if direct.exists():
        return direct
    summary = root / "campaign_summary.json"
    if summary.exists():
        best = _read_json(summary).get("best_minimum")
        if isinstance(best, dict):
            direct.write_text(json.dumps(best, indent=2), encoding="utf-8")
            return direct
    raise FileNotFoundError(f"No best minimum under {root}")


def _model_record(root: Path, model: str) -> dict[str, Any]:
    best = _read_json(_best_path(root))
    chi_blocks = {
        key.removeprefix("chi2__"): float(value)
        for key, value in best.items()
        if key.startswith("chi2__") and isinstance(value, (int, float)) and math.isfinite(float(value))
    }
    total_chi2 = float(sum(chi_blocks.values())) if chi_blocks else float(2.0 * best["minuslogpost"])
    gate_path = root / "convergence_gate.json"
    gate = _read_json(gate_path) if gate_path.exists() else {"converged": False, "missing": True}
    derived = {
        name: float(best[name])
        for name in ("H0", "peer_fede", "Alens", "rdrag", "ns", "S8", "A_act", "A_planck")
        if name in best and isinstance(best[name], (int, float))
    }
    return {
        "model": model, "root": str(root), "chi2_total": total_chi2,
        "chi2_blocks": chi_blocks, "extra_parameters_vs_M0": EXTRA_K[model],
        "aic_relative_constant_free": total_chi2 + 2 * EXTRA_K[model],
        "converged": bool(gate.get("converged", False)),
        "convergence_gate": gate, "derived": derived,
    }


def build_comparison(base: str | Path) -> dict[str, Any]:
    base = Path(base).resolve()
    models = {model: _model_record(base / model, model) for model in MODELS}
    contrasts: dict[str, Any] = {}
    for numerator, denominator in CONTRASTS:
        a, b = models[numerator], models[denominator]
        delta_chi2 = a["chi2_total"] - b["chi2_total"]
        delta_k = EXTRA_K[numerator] - EXTRA_K[denominator]
        contrasts[f"{numerator}_vs_{denominator}"] = {
            "numerator": numerator, "denominator": denominator,
            "delta_chi2": delta_chi2, "delta_k": delta_k,
            "delta_aic": delta_chi2 + 2 * delta_k,
            "block_deltas": {
                block: a["chi2_blocks"].get(block, 0.0) - b["chi2_blocks"].get(block, 0.0)
                for block in sorted(set(a["chi2_blocks"]) | set(b["chi2_blocks"]))
            },
        }
    all_converged = all(record["converged"] for record in models.values())
    complete = all(math.isfinite(record["chi2_total"]) for record in models.values())
    return {
        "base": str(base), "models": models, "contrasts": contrasts,
        "all_converged": all_converged, "complete": complete,
        "publishable_matched_comparison": bool(all_converged and complete),
        "bic": {"computed": False,
                "reason": "N_eff must be defined explicitly for heterogeneous correlated likelihood blocks"},
        "bayesian_evidence": {"computed": False,
                              "reason": "Requires a separate evidence calculation; profile/MCMC output is insufficient"},
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", required=True)
    parser.add_argument("--output", default=None)
    args = parser.parse_args()
    result = build_comparison(args.base)
    output = Path(args.output) if args.output else Path(args.base) / "matched_comparison.json"
    output.write_text(json.dumps(result, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps({"publishable": result["publishable_matched_comparison"],
                      "all_converged": result["all_converged"],
                      "contrasts": result["contrasts"], "output": str(output)}, indent=2))
    return 0 if result["publishable_matched_comparison"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
