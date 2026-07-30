from pathlib import Path

import numpy as np

from pt_driver import load_checkpoint, save_checkpoint


def test_checkpoint_roundtrip_preserves_sampler_state(tmp_path: Path):
    rng = np.random.default_rng(1234)
    payload = {
        "position": np.array([0.1, 0.5, 0.9]),
        "logprior": -2.5,
        "loglike": -101.25,
        "derived": {"H0": 70.8, "S8": 0.81},
        "walker_id": 17,
        "step": 321,
        "accepted_local": 88,
        "proposed_local": 320,
        "swap_attempts": np.array([10, 11]),
        "swap_accepts": np.array([4, 5]),
        "proposal_scale": 0.75,
        "adapt_count": 22,
        "adapt_mean": np.array([0.2, 0.3, 0.4]),
        "adapt_m2": np.eye(3),
        "rng_state": rng.bit_generator.state,
    }
    path = tmp_path / "rank_0.npz"
    save_checkpoint(path, payload)
    restored = load_checkpoint(path)

    for key in ("position", "swap_attempts", "swap_accepts", "adapt_mean", "adapt_m2"):
        assert np.array_equal(restored[key], payload[key])
    for key in (
        "logprior", "loglike", "walker_id", "step", "accepted_local",
        "proposed_local", "proposal_scale", "adapt_count",
    ):
        assert restored[key] == payload[key]
    assert restored["derived"] == payload["derived"]
    assert restored["rng_state"] == payload["rng_state"]
    assert not path.with_suffix(".tmp.npz").exists()
