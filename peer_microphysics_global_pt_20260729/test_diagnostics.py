from pathlib import Path

import numpy as np
import pandas as pd

from diagnostics import diagnose_cold_chains, promotion_gate


def _write_chains(root: Path, split: bool) -> list[Path]:
    rng = np.random.default_rng(20260729)
    paths = []
    for chain in range(4):
        n = 4000
        active = rng.random(n) < 0.78
        fede = np.where(active, rng.normal(0.085, 0.015, n), rng.uniform(0.001, 0.018, n))
        peer_n = np.where(active, rng.normal(3.05, 0.25, n), rng.uniform(1.05, 8.0, n))
        shift = 2.5 if split and chain >= 2 else 0.0
        frame = pd.DataFrame({
            "ombh2": rng.normal(0.0228 + shift * 1e-3, 0.0002, n),
            "omch2": rng.normal(0.123 + shift * 0.01, 0.002, n),
            "cosmomc_theta": rng.normal(0.010401, 5e-6, n),
            "logA": rng.normal(3.06, 0.01, n),
            "ns": rng.normal(0.992 + shift * 0.02, 0.005, n),
            "tau": rng.normal(0.058, 0.006, n),
            "A_planck": rng.normal(1.0, 0.001, n),
            "peer_fede": np.clip(fede, 0, 0.18),
            "peer_n": np.clip(peer_n + shift, 1.05, 8.0),
        })
        path = root / f"cold_{chain}.csv"
        frame.to_csv(path, index=False)
        paths.append(path)
    return paths


def _good_transport():
    return [
        {"ladder": i, "roundtrips": 3, "edge_acceptance": {str(e): 0.25 for e in range(5)}}
        for i in range(4)
    ]


def test_converged_global_mixture_passes_gate(tmp_path: Path):
    stats = diagnose_cold_chains(_write_chains(tmp_path, split=False), burn_fraction=0.30)
    gate = promotion_gate(stats, _good_transport())
    assert gate["passed"] is True
    assert stats["n_chains"] == 4
    assert stats["occupancy_half_difference"] < 0.03


def test_split_chains_fail_gate(tmp_path: Path):
    stats = diagnose_cold_chains(_write_chains(tmp_path, split=True), burn_fraction=0.30)
    gate = promotion_gate(stats, _good_transport())
    assert gate["passed"] is False
    assert gate["checks"]["rank_rhat"] is False


def test_transport_failure_blocks_promotion(tmp_path: Path):
    stats = diagnose_cold_chains(_write_chains(tmp_path, split=False), burn_fraction=0.30)
    transport = _good_transport()
    transport[2]["roundtrips"] = 0
    gate = promotion_gate(stats, transport)
    assert gate["passed"] is False
    assert gate["checks"]["roundtrips"] is False
