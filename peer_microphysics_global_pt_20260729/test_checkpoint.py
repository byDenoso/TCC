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


class _FakeParameterization:
    def sampled_params(self):
        return {"peer_n": None, "ombh2": None, "peer_fede": None}


class _FakeModel:
    parameterization = _FakeParameterization()

    def __init__(self, mapping_parts: bool):
        self.mapping_parts = mapping_parts

    def logposterior(self, values, **kwargs):
        assert set(values) == {"ombh2", "peer_fede", "peer_n"}
        priors = {"p": -1.25} if self.mapping_parts else [-1.25]
        likes = {"l1": -2.0, "l2": -3.0} if self.mapping_parts else [-2.0, -3.0]
        return {"logpriors": priors, "loglikes": likes, "derived": {"H0": 70.0}}


def test_sampled_parameter_resolution_is_deterministic_and_set_based(monkeypatch):
    from pt_driver import resolve_sampled_names

    monkeypatch.setattr("pt_driver.BOUNDS", {
        "ombh2": (0.0, 1.0),
        "peer_fede": (0.0, 1.0),
        "peer_n": (0.0, 1.0),
    })
    assert resolve_sampled_names(_FakeModel(mapping_parts=True)) == [
        "ombh2", "peer_fede", "peer_n"
    ]


def test_model_evaluation_accepts_mapping_and_sequence_log_parts(monkeypatch):
    from pt_driver import _evaluate_model

    monkeypatch.setattr("pt_driver.BOUNDS", {
        "ombh2": (0.0, 1.0),
        "peer_fede": (0.0, 1.0),
        "peer_n": (0.0, 1.0),
    })
    names = ["ombh2", "peer_fede", "peer_n"]
    position = np.array([0.2, 0.3, 0.4])
    for mapping_parts in (True, False):
        logprior, loglike, derived = _evaluate_model(
            _FakeModel(mapping_parts), names, position
        )
        assert logprior == -1.25
        assert loglike == -5.0
        assert derived == {"H0": 70.0}
