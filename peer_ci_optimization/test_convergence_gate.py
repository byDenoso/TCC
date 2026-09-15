from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from peer_ci_optimization.convergence_gate import diagnose, expand_trace, write_result


def _write_chain(path: Path, values: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        handle.write("# weight minuslogpost H0 peer_fede ns\n")
        for value in values:
            handle.write(
                f"1 0 {value:.12g} {0.08 + 0.001 * value:.12g} "
                f"{0.99 + 0.0005 * value:.12g}\n"
            )


def _write_checkpoint(root: Path, converged: bool, rminus1: str = "0.005") -> None:
    path = root / "mcmc" / "chain.checkpoint"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "sampler:\n  mcmc:\n"
        f"    converged: {str(converged).lower()}\n"
        f"    Rminus1_last: {rminus1}\n",
        encoding="utf-8",
    )


def test_expand_trace_reconstructs_cobaya_run_lengths() -> None:
    values = np.array([10.0, 20.0, 30.0])
    weights = np.array([1.0, 3.0, 2.0])
    assert expand_trace(values, weights).tolist() == [
        10.0,
        20.0,
        20.0,
        20.0,
        30.0,
        30.0,
    ]


def test_converged_synthetic_chains_pass_all_requested_gates(tmp_path: Path) -> None:
    rng = np.random.default_rng(20260730)
    for index in range(4):
        _write_chain(
            tmp_path / "mcmc" / f"chain.{index + 1}.txt",
            rng.normal(71.0, 0.7, 4000),
        )
    _write_checkpoint(tmp_path, True)

    result = diagnose(
        tmp_path,
        burn_fraction=0.20,
        params=["H0", "peer_fede", "ns"],
        minimum_chains=4,
        rhat_minus1_limit=0.02,
        ess_bulk_limit=500,
        ess_tail_limit=300,
        mcse_relative_limit=0.10,
    )

    assert result["converged"] is True
    assert result["n_chains_read"] == 4
    assert result["rhat_minus1_max"] < 0.02
    assert result["ess_bulk_min"] >= 500
    assert result["ess_tail_min"] >= 300
    assert result["mcse_mean_relative_max"] <= 0.10


def test_split_chains_fail_rank_rhat_even_with_native_checkpoint(tmp_path: Path) -> None:
    rng = np.random.default_rng(7)
    for index, mean in enumerate([68.0, 68.0, 74.0, 74.0], start=1):
        _write_chain(
            tmp_path / "mcmc" / f"chain.{index}.txt",
            rng.normal(mean, 0.4, 2500),
        )
    _write_checkpoint(tmp_path, True)

    result = diagnose(
        tmp_path,
        burn_fraction=0.20,
        params=["H0"],
        minimum_chains=4,
        rhat_minus1_limit=0.01,
        ess_bulk_limit=50,
        ess_tail_limit=50,
        mcse_relative_limit=1.0,
    )

    assert result["converged"] is False
    assert result["gate_results"]["rhat"] is False


def test_nonfinite_checkpoint_is_json_null_and_cannot_pass(tmp_path: Path) -> None:
    rng = np.random.default_rng(9)
    for index in range(4):
        _write_chain(
            tmp_path / "mcmc" / f"chain.{index + 1}.txt",
            rng.normal(71.0, 0.7, 1000),
        )
    _write_checkpoint(tmp_path, False, ".inf")

    result = diagnose(
        tmp_path,
        params=["H0"],
        minimum_chains=4,
        rhat_minus1_limit=0.10,
        ess_bulk_limit=10,
        ess_tail_limit=10,
        mcse_relative_limit=1.0,
    )
    output = tmp_path / "gate.json"
    write_result(result, output)
    decoded = json.loads(output.read_text(encoding="utf-8"))

    assert decoded["cobaya"]["Rminus1_last"] is None
    assert decoded["converged"] is False
