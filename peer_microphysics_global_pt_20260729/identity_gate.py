from __future__ import annotations

import argparse
import copy
import json
import math
from pathlib import Path

from campaign import REFS, build_info


def build_identity_infos(packages_path: str):
    free = build_info(packages_path)
    free["params"]["peer_n"] = {"value": 3.0}
    fixed = copy.deepcopy(free)
    fixed["params"].pop("peer_n")
    config = next(iter(fixed["theory"].values()))
    fixed["theory"] = {
        "peer_scalar_n3_reference.PEERScalarN3Reference": config
    }
    return free, fixed


def _sum_mapping(values) -> float:
    sequence = values.values() if hasattr(values, "values") else values
    return float(sum(float(value) for value in sequence))


def _finite_mapping(values) -> dict[str, float]:
    if not hasattr(values, "items"):
        return {}
    return {
        str(key): float(value)
        for key, value in values.items()
        if value is not None and math.isfinite(float(value))
    }


def run_identity_gate(packages_path: str, output: str | Path) -> dict:
    from cobaya.model import get_model

    free_info, fixed_info = build_identity_infos(packages_path)
    free_model = get_model(free_info, stop_at_error=True)
    fixed_model = get_model(fixed_info, stop_at_error=True)
    free_names = list(free_model.parameterization.sampled_params())
    fixed_names = list(fixed_model.parameterization.sampled_params())
    if set(free_names) != set(fixed_names):
        raise RuntimeError(
            f"Identity models expose different sampled parameters: {free_names} vs {fixed_names}"
        )
    point = {name: float(REFS[name]) for name in free_names}
    free_result = free_model.logposterior(point, as_dict=True, make_finite=False)
    fixed_result = fixed_model.logposterior(point, as_dict=True, make_finite=False)
    free_likes = _finite_mapping(free_result["loglikes"])
    fixed_likes = _finite_mapping(fixed_result["loglikes"])
    if set(free_likes) != set(fixed_likes):
        raise RuntimeError("Identity models returned different likelihood components")
    like_deltas = {
        name: free_likes[name] - fixed_likes[name] for name in free_likes
    }
    free_derived = _finite_mapping(free_result.get("derived", {}))
    fixed_derived = _finite_mapping(fixed_result.get("derived", {}))
    common_derived = set(free_derived) & set(fixed_derived)
    derived_deltas = {
        name: free_derived[name] - fixed_derived[name] for name in common_derived
    }
    max_like = max((abs(value) for value in like_deltas.values()), default=math.inf)
    max_derived = max((abs(value) for value in derived_deltas.values()), default=math.inf)
    logpost_delta = float(free_result["logpost"] - fixed_result["logpost"])
    passed = (
        math.isfinite(_sum_mapping(free_result["loglikes"]))
        and math.isfinite(_sum_mapping(fixed_result["loglikes"]))
        and abs(logpost_delta) < 1e-8
        and max_like < 1e-8
        and max_derived < 1e-8
    )
    report = {
        "passed": bool(passed),
        "point": point,
        "logpost_delta": logpost_delta,
        "max_abs_loglike_delta": max_like,
        "max_abs_derived_delta": max_derived,
        "loglike_deltas": like_deltas,
        "derived_deltas": derived_deltas,
        "threshold": 1e-8,
    }
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="n=3 PEER wrapper identity gate")
    parser.add_argument("--packages", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    report = run_identity_gate(args.packages, args.output)
    print(json.dumps(report, indent=2))
    return 0 if report["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
