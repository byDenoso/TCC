from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import arviz as az
import numpy as np
import pandas as pd

PARAMS = [
    "ombh2",
    "omch2",
    "cosmomc_theta",
    "logA",
    "ns",
    "tau",
    "A_planck",
    "peer_fede",
    "peer_n",
    "peer_identifiable",
    "active_branch",
]


def _finite_max(values) -> float | None:
    array = np.asarray(list(values), dtype=float)
    array = array[np.isfinite(array)]
    return float(array.max()) if array.size else None


def _finite_min(values) -> float | None:
    array = np.asarray(list(values), dtype=float)
    array = array[np.isfinite(array)]
    return float(array.min()) if array.size else None


def _prepare_frame(path: str | Path, burn_fraction: float) -> pd.DataFrame:
    frame = pd.read_csv(path)
    missing = [name for name in PARAMS[:9] if name not in frame.columns]
    if missing:
        raise ValueError(f"{path} is missing columns: {missing}")
    start = int(len(frame) * burn_fraction)
    frame = frame.iloc[start:].reset_index(drop=True).copy()
    frame["peer_identifiable"] = frame["peer_fede"] * (frame["peer_n"] - 3.0)
    frame["active_branch"] = (frame["peer_fede"] >= 0.02).astype(float)
    return frame


def diagnose_cold_chains(
    chain_paths: list[str | Path], burn_fraction: float = 0.30
) -> dict[str, Any]:
    frames = [_prepare_frame(path, burn_fraction) for path in chain_paths]
    if len(frames) != 4:
        raise ValueError(f"Expected four independent cold chains, received {len(frames)}")
    equal_draws = min(len(frame) for frame in frames)
    if equal_draws < 20:
        raise ValueError("Cold chains contain fewer than 20 post-burn draws")
    frames = [frame.iloc[-equal_draws:].reset_index(drop=True) for frame in frames]
    arrays = {
        name: np.stack([frame[name].to_numpy(float) for frame in frames], axis=0)
        for name in PARAMS
    }
    rhat_data = az.rhat(arrays, method="rank")
    ess_bulk_data = az.ess(arrays, method="bulk")
    ess_tail_data = az.ess(arrays, method="tail")
    rhat = {name: float(np.asarray(rhat_data[name]).squeeze()) for name in PARAMS}
    ess_bulk = {
        name: float(np.asarray(ess_bulk_data[name]).squeeze()) for name in PARAMS
    }
    ess_tail = {
        name: float(np.asarray(ess_tail_data[name]).squeeze()) for name in PARAMS
    }
    rhat_minus1 = {name: value - 1.0 for name, value in rhat.items()}

    per_chain_occupancy = [float(frame["active_branch"].mean()) for frame in frames]
    first = np.concatenate(
        [frame["active_branch"].iloc[: equal_draws // 2].to_numpy(float) for frame in frames]
    )
    second = np.concatenate(
        [frame["active_branch"].iloc[equal_draws // 2 :].to_numpy(float) for frame in frames]
    )
    occupancy_first = float(first.mean())
    occupancy_second = float(second.mean())
    occupancy_difference = abs(occupancy_first - occupancy_second)

    combined = pd.concat(frames, ignore_index=True)
    active_n = combined.loc[combined["active_branch"] > 0.5, "peer_n"].to_numpy(float)
    active_summary = {
        "count": int(active_n.size),
        "median": float(np.median(active_n)) if active_n.size else None,
        "q16": float(np.quantile(active_n, 0.16)) if active_n.size else None,
        "q84": float(np.quantile(active_n, 0.84)) if active_n.size else None,
    }
    return {
        "n_chains": len(frames),
        "draws_per_chain": equal_draws,
        "burn_fraction": burn_fraction,
        "rank_rhat": rhat,
        "rank_rhat_minus1": rhat_minus1,
        "rhat_minus1_max": _finite_max(rhat_minus1.values()),
        "ess_bulk": ess_bulk,
        "ess_tail": ess_tail,
        "ess_bulk_min": _finite_min(ess_bulk.values()),
        "ess_tail_min": _finite_min(ess_tail.values()),
        "active_branch_probability": float(combined["active_branch"].mean()),
        "near_null_probability": float(1.0 - combined["active_branch"].mean()),
        "per_chain_active_probability": per_chain_occupancy,
        "occupancy_first_half": occupancy_first,
        "occupancy_second_half": occupancy_second,
        "occupancy_half_difference": occupancy_difference,
        "active_branch_n": active_summary,
    }


def promotion_gate(stats: dict[str, Any], transport: list[dict[str, Any]]) -> dict[str, Any]:
    edge_values = []
    all_edges_present = True
    for ladder in transport:
        acceptance = ladder.get("edge_acceptance", {})
        if set(acceptance) != {"0", "1", "2", "3", "4"}:
            all_edges_present = False
        edge_values.extend(float(value) for value in acceptance.values())
    checks = {
        "four_cold_chains": stats.get("n_chains") == 4,
        "rank_rhat": stats.get("rhat_minus1_max") is not None
        and float(stats["rhat_minus1_max"]) < 0.01,
        "bulk_ess": stats.get("ess_bulk_min") is not None
        and float(stats["ess_bulk_min"]) > 1000,
        "tail_ess": stats.get("ess_tail_min") is not None
        and float(stats["ess_tail_min"]) > 500,
        "occupancy_stability": float(stats.get("occupancy_half_difference", math.inf)) < 0.03,
        "four_ladders": len(transport) == 4,
        "roundtrips": len(transport) == 4
        and all(int(item.get("roundtrips", 0)) >= 2 for item in transport),
        "swap_edges": all_edges_present
        and bool(edge_values)
        and all(0.10 <= value <= 0.60 for value in edge_values),
    }
    return {
        "passed": all(checks.values()),
        "checks": checks,
        "thresholds": {
            "rhat_minus1_max": 0.01,
            "ess_bulk_min": 1000,
            "ess_tail_min": 500,
            "occupancy_half_difference_max": 0.03,
            "roundtrips_per_ladder_min": 2,
            "swap_acceptance_range": [0.10, 0.60],
        },
    }


def _roundtrips(root: Path) -> int:
    frames = []
    for path in sorted((root / "chains").glob("temp_*.csv")):
        frame = pd.read_csv(path, usecols=["step", "temperature_rank", "walker_id"])
        frames.append(frame)
    if not frames:
        return 0
    events = pd.concat(frames, ignore_index=True).sort_values(
        ["walker_id", "step", "temperature_rank"]
    )
    total = 0
    for _, group in events.groupby("walker_id"):
        phase = 0
        for rank in group["temperature_rank"].astype(int):
            if phase == 0 and rank == 0:
                phase = 1
            elif phase == 1 and rank == 5:
                phase = 2
            elif phase == 2 and rank == 0:
                total += 1
                phase = 1
    return total


def diagnose_transport(root: str | Path, ladder_index: int) -> dict[str, Any]:
    root = Path(root)
    swap_path = root / "swap_log.csv"
    acceptance: dict[str, float] = {}
    attempts: dict[str, int] = {}
    if swap_path.exists():
        swaps = pd.read_csv(swap_path)
        for edge, group in swaps.groupby("edge"):
            attempts[str(int(edge))] = int(len(group))
            acceptance[str(int(edge))] = float(group["accepted"].mean())
    return {
        "ladder": int(ladder_index),
        "root": str(root),
        "roundtrips": _roundtrips(root),
        "edge_attempts": attempts,
        "edge_acceptance": acceptance,
    }


def _find_ladder_roots(input_root: Path) -> list[Path]:
    return sorted({path.parent.parent for path in input_root.rglob("chains/temp_0.csv")})


def _write_outputs(
    output: Path,
    stats: dict[str, Any],
    transport: list[dict[str, Any]],
    gate: dict[str, Any],
) -> None:
    output.mkdir(parents=True, exist_ok=True)
    (output / "global_summary.json").write_text(
        json.dumps(stats, indent=2, allow_nan=False), encoding="utf-8"
    )
    (output / "promotion_gate.json").write_text(
        json.dumps(gate, indent=2, allow_nan=False), encoding="utf-8"
    )
    pd.DataFrame(
        [
            {
                "parameter": name,
                "rank_rhat": stats["rank_rhat"][name],
                "rank_rhat_minus1": stats["rank_rhat_minus1"][name],
                "ess_bulk": stats["ess_bulk"][name],
                "ess_tail": stats["ess_tail"][name],
            }
            for name in PARAMS
        ]
    ).to_csv(output / "rhat_ess.csv", index=False)
    pd.DataFrame(
        [
            {"chain": index, "active_probability": value}
            for index, value in enumerate(stats["per_chain_active_probability"])
        ]
    ).to_csv(output / "branch_occupancy.csv", index=False)
    transport_rows = []
    for item in transport:
        for edge in sorted(item["edge_acceptance"], key=int):
            transport_rows.append(
                {
                    "ladder": item["ladder"],
                    "roundtrips": item["roundtrips"],
                    "edge": int(edge),
                    "attempts": item["edge_attempts"].get(edge, 0),
                    "acceptance": item["edge_acceptance"][edge],
                }
            )
    pd.DataFrame(transport_rows).to_csv(output / "transport.csv", index=False)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Promotion gate for PEER global microphysics")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--burn", type=float, default=0.30)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    input_root = Path(args.input).resolve()
    output = Path(args.output).resolve()
    roots = _find_ladder_roots(input_root)
    if len(roots) != 4:
        raise SystemExit(f"Expected four ladder roots, found {len(roots)}: {roots}")
    cold_paths = [root / "chains" / "temp_0.csv" for root in roots]
    stats = diagnose_cold_chains(cold_paths, burn_fraction=args.burn)
    transport = [diagnose_transport(root, index) for index, root in enumerate(roots)]
    gate = promotion_gate(stats, transport)
    _write_outputs(output, stats, transport, gate)
    print(json.dumps({
        "passed": gate["passed"],
        "rhat_minus1_max": stats["rhat_minus1_max"],
        "ess_bulk_min": stats["ess_bulk_min"],
        "ess_tail_min": stats["ess_tail_min"],
        "active_branch_probability": stats["active_branch_probability"],
        "output": str(output),
    }, indent=2))
    return 0 if gate["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
