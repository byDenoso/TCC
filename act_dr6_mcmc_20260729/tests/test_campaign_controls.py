import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
import yaml

from act_dr6_mcmc_20260729.convergence_gate import diagnose, expand_trace
from act_dr6_mcmc_20260729.lane_b_campaign import configure_lane_b
from act_dr6_mcmc_20260729.matched_compare import build_comparison


def write_chain(path: Path, values: np.ndarray, weights=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    if weights is None:
        weights = np.ones(len(values), dtype=int)
    with path.open("w", encoding="utf-8") as handle:
        handle.write("# weight minuslogpost x y\n")
        for weight, value in zip(weights, values):
            handle.write(f"{int(weight)} 0 {float(value):.12g} {float(0.5 * value):.12g}\n")


def write_checkpoint(root: Path, converged: bool, rminus1: float):
    (root / "mcmc").mkdir(parents=True, exist_ok=True)
    payload = {"sampler": {"mcmc": {"converged": converged, "Rminus1_last": rminus1}}}
    (root / "mcmc/chain.checkpoint").write_text(yaml.safe_dump(payload), encoding="utf-8")


def write_model(base: Path, model: str, chi2: float, converged: bool = True):
    root = base / model
    root.mkdir(parents=True)
    best = {"minuslogpost": chi2 / 2, "chi2__act_dr6_cmbonly": chi2 - 20,
            "chi2__shoes_h0.SH0ESGaussian": 20, "H0": 70.0}
    (root / "best_minimum.json").write_text(json.dumps(best), encoding="utf-8")
    (root / "convergence_gate.json").write_text(json.dumps({"converged": converged}), encoding="utf-8")


class CampaignControlTests(unittest.TestCase):
    def test_expand_trace_reconstructs_repeated_states(self):
        out = expand_trace(np.array([1.0, 2.0, 3.0]), np.array([2, 1, 3]), max_draws=100)
        np.testing.assert_array_equal(out, np.array([1, 1, 2, 3, 3, 3], dtype=float))

    def test_converged_chains_pass_and_shifted_chain_fails(self):
        rng = np.random.default_rng(20260729)
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            write_checkpoint(root, True, 0.006)
            for i in range(4):
                write_chain(root / "mcmc" / f"chain.{i + 1}.txt", rng.normal(0, 1, 5000))
            self.assertTrue(diagnose(root, params=["x", "y"])["converged"])
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            write_checkpoint(root, True, 0.006)
            for i in range(4):
                write_chain(root / "mcmc" / f"chain.{i + 1}.txt", rng.normal(1.5 if i == 3 else 0, 1, 4000))
            self.assertFalse(diagnose(root, params=["x"])["converged"])

    def test_checkpoint_false_blocks_promotion(self):
        rng = np.random.default_rng(7)
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            write_checkpoint(root, False, 0.2)
            for i in range(4):
                write_chain(root / "mcmc" / f"chain.{i + 1}.txt", rng.normal(0, 1, 4000))
            self.assertFalse(diagnose(root, params=["x"])["converged"])

    def test_lane_b_uses_full_planck_and_separate_calibrations(self):
        info = {"likelihood": {"act_dr6_cmbonly": {}, "act_dr6_cmbonly.PlanckActCut": {},
                               "planck_2018_lowl.TT": {}, "planck_2018_lowl.EE_sroll2": {},
                               "planck_2018_lensing.native": {}, "bao.desi_dr2.desi_bao_all": {},
                               "shoes_h0.SH0ESGaussian": {}},
                "prior": {}, "params": {"A_planck": {"value": "lambda A_act: A_act"}, "A_act": {}}}
        out = configure_lane_b(info)
        self.assertNotIn("act_dr6_cmbonly.PlanckActCut", out["likelihood"])
        self.assertIn("planck_2018_highl_plik.TTTEEE_lite_native", out["likelihood"])
        self.assertIn("prior", out["params"]["A_planck"])
        self.assertIn("planck_calibration_prior", out["prior"])

    def test_matched_comparison_requires_all_models_converged(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            for model, chi2 in (("M0", 500), ("M1", 490), ("M2", 480), ("M3", 470)):
                write_model(base, model, chi2, converged=model != "M3")
            out = build_comparison(base)
            self.assertEqual(out["contrasts"]["M2_vs_M0"]["delta_chi2"], -20)
            self.assertEqual(out["contrasts"]["M2_vs_M0"]["delta_aic"], -18)
            self.assertFalse(out["publishable_matched_comparison"])


if __name__ == "__main__":
    unittest.main()
