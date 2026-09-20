from __future__ import annotations

import argparse
import csv
import json
import math
import os
import signal
import sys
from pathlib import Path
from typing import Any

import numpy as np

from campaign import BOUNDS, PROPOSALS, REFS, TEMPERATURES, build_info, write_manifest
from pt_core import (
    metropolis_accept,
    pair_schedule,
    reflect_unit_box,
    swap_log_alpha,
    validate_temperatures,
)

_STOP_REQUESTED = False


def _request_stop(signum, frame):  # pragma: no cover
    del signum, frame
    global _STOP_REQUESTED
    _STOP_REQUESTED = True


def _json_default(value):
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    raise TypeError(f"Cannot JSON encode {type(value)!r}")


def save_checkpoint(path: str | Path, payload: dict[str, Any]) -> None:
    """Atomically persist a sampler state without pickle."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp.npz")
    arrays = {
        "position": np.asarray(payload["position"], dtype=float),
        "logprior": np.asarray(payload["logprior"], dtype=float),
        "loglike": np.asarray(payload["loglike"], dtype=float),
        "derived_json": np.asarray(json.dumps(payload.get("derived", {}), default=_json_default)),
        "walker_id": np.asarray(payload["walker_id"], dtype=np.int64),
        "step": np.asarray(payload["step"], dtype=np.int64),
        "accepted_local": np.asarray(payload["accepted_local"], dtype=np.int64),
        "proposed_local": np.asarray(payload["proposed_local"], dtype=np.int64),
        "swap_attempts": np.asarray(payload["swap_attempts"], dtype=np.int64),
        "swap_accepts": np.asarray(payload["swap_accepts"], dtype=np.int64),
        "proposal_scale": np.asarray(payload["proposal_scale"], dtype=float),
        "adapt_count": np.asarray(payload["adapt_count"], dtype=np.int64),
        "adapt_mean": np.asarray(payload["adapt_mean"], dtype=float),
        "adapt_m2": np.asarray(payload["adapt_m2"], dtype=float),
        "rng_json": np.asarray(json.dumps(payload["rng_state"], default=_json_default)),
    }
    np.savez_compressed(temporary, **arrays)
    os.replace(temporary, path)


def load_checkpoint(path: str | Path) -> dict[str, Any]:
    path = Path(path)
    with np.load(path, allow_pickle=False) as data:
        return {
            "position": np.asarray(data["position"], dtype=float),
            "logprior": float(data["logprior"].item()),
            "loglike": float(data["loglike"].item()),
            "derived": json.loads(str(data["derived_json"].item())),
            "walker_id": int(data["walker_id"].item()),
            "step": int(data["step"].item()),
            "accepted_local": int(data["accepted_local"].item()),
            "proposed_local": int(data["proposed_local"].item()),
            "swap_attempts": np.asarray(data["swap_attempts"], dtype=np.int64),
            "swap_accepts": np.asarray(data["swap_accepts"], dtype=np.int64),
            "proposal_scale": float(data["proposal_scale"].item()),
            "adapt_count": int(data["adapt_count"].item()),
            "adapt_mean": np.asarray(data["adapt_mean"], dtype=float),
            "adapt_m2": np.asarray(data["adapt_m2"], dtype=float),
            "rng_state": json.loads(str(data["rng_json"].item())),
        }


def _unit_from_physical(names: list[str], values: dict[str, float]) -> np.ndarray:
    return np.asarray(
        [
            (float(values[name]) - BOUNDS[name][0]) / (BOUNDS[name][1] - BOUNDS[name][0])
            for name in names
        ],
        dtype=float,
    )


def _physical_from_unit(names: list[str], position: np.ndarray) -> dict[str, float]:
    return {
        name: float(BOUNDS[name][0] + position[index] * (BOUNDS[name][1] - BOUNDS[name][0]))
        for index, name in enumerate(names)
    }


def _base_scales(names: list[str]) -> np.ndarray:
    return np.asarray(
        [PROPOSALS[name] / (BOUNDS[name][1] - BOUNDS[name][0]) for name in names],
        dtype=float,
    )


def _initial_physical(
    ladder_id: int, temperature_rank: int, rng: np.random.Generator
) -> dict[str, float]:
    point = dict(REFS)
    active = ladder_id % 2 == 0
    if active:
        point["peer_fede"] = (0.075, 0.105)[(ladder_id // 2) % 2]
        point["peer_n"] = (2.85, 3.20)[(ladder_id // 2) % 2]
        point["ns"] = 0.990 + 0.004 * ((ladder_id // 2) % 2)
    else:
        point["peer_fede"] = (0.006, 0.014)[(ladder_id // 2) % 2]
        point["peer_n"] = (1.4, 6.6)[(ladder_id // 2) % 2]
        point["ns"] = 0.969 + 0.004 * ((ladder_id // 2) % 2)
    names = list(BOUNDS)
    unit = _unit_from_physical(names, point)
    jitter = rng.normal(
        0.0, 0.01 * math.sqrt(TEMPERATURES[temperature_rank]), size=len(names)
    )
    return _physical_from_unit(names, reflect_unit_box(unit + jitter))


def _sum_log_parts(parts) -> float:
    values = parts.values() if hasattr(parts, "values") else parts
    return float(sum(float(value) for value in values))


def resolve_sampled_names(model) -> list[str]:
    expected = list(BOUNDS)
    actual = list(model.parameterization.sampled_params())
    if set(actual) != set(expected):
        raise RuntimeError(f"Unexpected sampled parameters: {actual}; expected {expected}")
    return expected


def _exception_name(exc: BaseException) -> str:
    cls = type(exc)
    return f"{cls.__module__}.{cls.__name__}"


def _is_recoverable_numerical_error(exc: BaseException) -> bool:
    """Return true only for numerical theory failures at an otherwise valid proposal."""
    exception_name = _exception_name(exc)
    if exception_name == "camb.baseconfig.CAMBError":
        return True
    if isinstance(exc, (FloatingPointError, OverflowError)):
        return True
    message = str(exc).lower()
    numerical_markers = (
        "integration timed out",
        "integrate, integration timed out",
        "error in dverk",
        "non-finite",
        "non finite",
        "nan in",
    )
    return exception_name == "cobaya.log.LoggedError" and any(
        marker in message for marker in numerical_markers
    )


def _append_invalid_evaluation(
    path: str | Path,
    *,
    physical: dict[str, float],
    exc: BaseException,
    context: dict[str, Any] | None = None,
) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        **(context or {}),
        "exception_type": _exception_name(exc),
        "message": str(exc),
        "parameters": physical,
    }
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True, default=_json_default) + "\n")


def _evaluate_model(
    model,
    names: list[str],
    position: np.ndarray,
    *,
    invalid_log_path: str | Path | None = None,
    context: dict[str, Any] | None = None,
):
    physical = _physical_from_unit(names, position)
    try:
        result = model.logposterior(
            physical, as_dict=True, return_derived=True, make_finite=False
        )
    except BaseException as exc:
        if not _is_recoverable_numerical_error(exc):
            raise
        if invalid_log_path is not None:
            _append_invalid_evaluation(
                invalid_log_path,
                physical=physical,
                exc=exc,
                context=context,
            )
        return -math.inf, -math.inf, {}
    logprior = _sum_log_parts(result["logpriors"])
    loglike = _sum_log_parts(result["loglikes"])
    if not math.isfinite(logprior) or not math.isfinite(loglike):
        return -math.inf, -math.inf, {}
    derived = {
        key: float(value)
        for key, value in result.get("derived", {}).items()
        if value is not None and np.isscalar(value) and math.isfinite(float(value))
    }
    return logprior, loglike, derived


def _append_chain_row(
    path: Path,
    names: list[str],
    rank: int,
    temperature: float,
    state: dict[str, Any],
    local_accepted: bool,
    swapped: bool,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    physical = _physical_from_unit(names, state["position"])
    row = {
        "step": state["step"],
        "temperature_rank": rank,
        "temperature": temperature,
        "beta": 1.0 / temperature,
        "walker_id": state["walker_id"],
        "local_accepted": int(local_accepted),
        "swapped": int(swapped),
        "logprior": state["logprior"],
        "loglike": state["loglike"],
        "logpost_tempered": state["logprior"] + state["loglike"] / temperature,
        **physical,
        **{f"derived__{key}": value for key, value in state.get("derived", {}).items()},
    }
    exists = path.exists() and path.stat().st_size > 0
    with path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(row))
        if not exists:
            writer.writeheader()
        writer.writerow(row)


def _state_for_exchange(state: dict[str, Any]) -> dict[str, Any]:
    return {
        "position": np.asarray(state["position"], dtype=float),
        "logprior": float(state["logprior"]),
        "loglike": float(state["loglike"]),
        "derived": dict(state.get("derived", {})),
        "walker_id": int(state["walker_id"]),
    }


def _apply_exchange(state: dict[str, Any], exchanged: dict[str, Any]) -> None:
    for key in ("position", "logprior", "loglike", "derived", "walker_id"):
        state[key] = exchanged[key]


def _adapt(state: dict[str, Any], accepted: bool, warmup_steps: int) -> None:
    if state["step"] > warmup_steps:
        return
    position = np.asarray(state["position"], dtype=float)
    state["adapt_count"] += 1
    count = state["adapt_count"]
    delta = position - state["adapt_mean"]
    state["adapt_mean"] += delta / count
    state["adapt_m2"] += np.outer(delta, position - state["adapt_mean"])
    gain = min(0.05, 1.0 / math.sqrt(max(1, state["step"])))
    state["proposal_scale"] *= math.exp(
        gain * ((1.0 if accepted else 0.0) - 0.234)
    )
    state["proposal_scale"] = float(np.clip(state["proposal_scale"], 0.15, 4.0))


def _proposal_covariance(
    state: dict[str, Any], base_scales: np.ndarray, warmup_steps: int
) -> np.ndarray:
    diagonal = np.diag(base_scales**2)
    if state["adapt_count"] < max(20, len(base_scales) * 2):
        return diagonal
    empirical = state["adapt_m2"] / max(1, state["adapt_count"] - 1)
    covariance = empirical + diagonal * 0.05 + np.eye(len(base_scales)) * 1e-10
    return covariance.copy() if state["step"] > warmup_steps else covariance


def _checkpoint_payload(
    state: dict[str, Any], rng: np.random.Generator
) -> dict[str, Any]:
    payload = dict(state)
    payload["rng_state"] = rng.bit_generator.state
    return payload


def _initialize_state(
    model,
    names: list[str],
    ladder_id: int,
    rank: int,
    rng: np.random.Generator,
    swap_edges: int,
) -> dict[str, Any]:
    for attempt in range(80):
        point = _initial_physical(ladder_id, rank, rng)
        position = _unit_from_physical(names, point)
        if attempt:
            position = reflect_unit_box(
                position + rng.normal(0.0, 0.015, len(names))
            )
        logprior, loglike, derived = _evaluate_model(model, names, position)
        if math.isfinite(logprior) and math.isfinite(loglike):
            return {
                "position": position,
                "logprior": logprior,
                "loglike": loglike,
                "derived": derived,
                "walker_id": ladder_id * len(TEMPERATURES) + rank,
                "step": 0,
                "accepted_local": 0,
                "proposed_local": 0,
                "swap_attempts": np.zeros(swap_edges, dtype=np.int64),
                "swap_accepts": np.zeros(swap_edges, dtype=np.int64),
                "proposal_scale": 1.0,
                "adapt_count": 0,
                "adapt_mean": np.zeros(len(names), dtype=float),
                "adapt_m2": np.zeros((len(names), len(names)), dtype=float),
            }
    raise RuntimeError("Could not find a finite initial point after 80 attempts")


def _run_synthetic_self_test() -> int:
    from mpi4py import MPI

    comm = MPI.COMM_WORLD
    rank = comm.Get_rank()
    size = comm.Get_size()
    if size != 6:
        if rank == 0:
            print("self-test requires exactly 6 MPI ranks", file=sys.stderr)
        return 2
    temperatures = validate_temperatures(TEMPERATURES)
    beta = 1.0 / temperatures[rank]
    loglike = -0.5 * float((rank - 2.5) ** 2)
    gathered = comm.gather({"rank": rank, "loglike": loglike}, root=0)
    if rank == 0:
        attempts = []
        for left, right in pair_schedule(0, size):
            attempts.append(
                swap_log_alpha(
                    1 / temperatures[left],
                    1 / temperatures[right],
                    gathered[left]["loglike"],
                    gathered[right]["loglike"],
                )
            )
        ok = len(attempts) == 3 and all(math.isfinite(value) for value in attempts) and beta == 1.0
    else:
        ok = None
    ok = comm.bcast(ok, root=0)
    return 0 if ok else 3


def run(args: argparse.Namespace) -> int:
    from cobaya.model import get_model
    from mpi4py import MPI

    comm = MPI.COMM_WORLD
    rank = comm.Get_rank()
    size = comm.Get_size()
    temperatures = validate_temperatures(TEMPERATURES)
    if size != len(temperatures):
        if rank == 0:
            print(f"Expected {len(temperatures)} MPI ranks, received {size}", file=sys.stderr)
        return 2

    root = Path(args.root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    if rank == 0:
        write_manifest(root, source_sha=os.environ.get("GITHUB_SHA"))
    comm.Barrier()

    signal.signal(signal.SIGTERM, _request_stop)
    signal.signal(signal.SIGINT, _request_stop)

    info = build_info(os.environ.get("COBAYA_PACKAGES_PATH", "packages"))
    model = get_model(info, stop_at_error=True)
    names = resolve_sampled_names(model)

    seed = 202607290000 + args.ladder_id * 1000 + rank
    rng = np.random.default_rng(seed)
    checkpoint_path = root / "checkpoints" / f"rank_{rank}.npz"
    if args.resume and checkpoint_path.exists():
        state = load_checkpoint(checkpoint_path)
        rng.bit_generator.state = state.pop("rng_state")
    else:
        state = _initialize_state(model, names, args.ladder_id, rank, rng, size - 1)

    base_scales = _base_scales(names)
    temperature = temperatures[rank]
    beta = 1.0 / temperature
    final_step = state["step"] + args.steps
    swap_round = state["step"] // max(1, args.swap_every)
    chain_path = root / "chains" / f"temp_{rank}.csv"
    swap_path = root / "swap_log.csv"
    invalid_log_path = root / "logs" / f"rank_{rank}_invalid_theory.jsonl"

    while state["step"] < final_step and not _STOP_REQUESTED:
        covariance = _proposal_covariance(state, base_scales, args.warmup)
        step_scale = state["proposal_scale"] * math.sqrt(temperature)
        proposal = reflect_unit_box(
            state["position"]
            + rng.multivariate_normal(np.zeros(len(names)), covariance) * step_scale
        )
        new_logprior, new_loglike, new_derived = _evaluate_model(
            model,
            names,
            proposal,
            invalid_log_path=invalid_log_path,
            context={
                "ladder_id": args.ladder_id,
                "rank": rank,
                "temperature": float(temperature),
                "step": int(state["step"] + 1),
            },
        )
        state["proposed_local"] += 1
        log_alpha = (new_logprior + beta * new_loglike) - (
            state["logprior"] + beta * state["loglike"]
        )
        accepted = metropolis_accept(log_alpha, float(rng.random()))
        if accepted:
            state["position"] = proposal
            state["logprior"] = new_logprior
            state["loglike"] = new_loglike
            state["derived"] = new_derived
            state["accepted_local"] += 1
        state["step"] += 1
        _adapt(state, accepted, args.warmup)

        swapped = False
        if state["step"] % args.swap_every == 0:
            gathered = comm.gather(_state_for_exchange(state), root=0)
            if rank == 0:
                swap_rows = []
                for left, right in pair_schedule(swap_round, size):
                    edge = left
                    state["swap_attempts"][edge] += 1
                    left_before = gathered[left]["walker_id"]
                    right_before = gathered[right]["walker_id"]
                    loga = swap_log_alpha(
                        1.0 / temperatures[left],
                        1.0 / temperatures[right],
                        gathered[left]["loglike"],
                        gathered[right]["loglike"],
                    )
                    is_accepted = metropolis_accept(loga, float(rng.random()))
                    if is_accepted:
                        gathered[left], gathered[right] = gathered[right], gathered[left]
                        state["swap_accepts"][edge] += 1
                    swap_rows.append(
                        {
                            "step": state["step"],
                            "swap_round": swap_round,
                            "left": left,
                            "right": right,
                            "edge": edge,
                            "accepted": int(is_accepted),
                            "log_alpha": loga,
                            "walker_left_before": left_before,
                            "walker_right_before": right_before,
                        }
                    )
                exists = swap_path.exists() and swap_path.stat().st_size > 0
                with swap_path.open("a", newline="", encoding="utf-8") as handle:
                    writer = csv.DictWriter(handle, fieldnames=list(swap_rows[0]))
                    if not exists:
                        writer.writeheader()
                    writer.writerows(swap_rows)
                counters = (state["swap_attempts"], state["swap_accepts"])
            else:
                counters = None
            exchanged = comm.scatter(gathered, root=0)
            before_id = state["walker_id"]
            _apply_exchange(state, exchanged)
            swapped = state["walker_id"] != before_id
            counters = comm.bcast(counters, root=0)
            state["swap_attempts"] = np.asarray(counters[0], dtype=np.int64)
            state["swap_accepts"] = np.asarray(counters[1], dtype=np.int64)
            swap_round += 1

        if state["step"] > args.warmup and state["step"] % args.thin == 0:
            _append_chain_row(
                chain_path, names, rank, temperature, state, accepted, swapped
            )
        if state["step"] % args.checkpoint_every == 0:
            save_checkpoint(checkpoint_path, _checkpoint_payload(state, rng))

    save_checkpoint(checkpoint_path, _checkpoint_payload(state, rng))
    invalid_count = 0
    if invalid_log_path.exists():
        with invalid_log_path.open("r", encoding="utf-8") as handle:
            invalid_count = sum(1 for line in handle if line.strip())
    summary = {
        "ladder_id": args.ladder_id,
        "rank": rank,
        "temperature": temperature,
        "step": state["step"],
        "accepted_local": state["accepted_local"],
        "proposed_local": state["proposed_local"],
        "local_acceptance": state["accepted_local"] / max(1, state["proposed_local"]),
        "invalid_theory_evaluations": invalid_count,
        "walker_id": state["walker_id"],
        "stop_requested": _STOP_REQUESTED,
    }
    (root / f"rank_{rank}_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    comm.Barrier()
    return 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="MPI parallel-tempering sampler for global PEER microphysics"
    )
    parser.add_argument("--root", default="peer_microphysics_pt_output")
    parser.add_argument("--ladder-id", type=int, default=0)
    parser.add_argument("--steps", type=int, default=100000)
    parser.add_argument("--swap-every", type=int, default=10)
    parser.add_argument("--checkpoint-every", type=int, default=25)
    parser.add_argument("--thin", type=int, default=2)
    parser.add_argument("--warmup", type=int, default=300)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.self_test:
        return _run_synthetic_self_test()
    if not 0 <= args.ladder_id < 4:
        raise SystemExit("--ladder-id must be in [0, 3]")
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
