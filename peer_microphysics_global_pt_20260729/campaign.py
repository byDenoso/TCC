from __future__ import annotations

import json
from pathlib import Path
from typing import Any

TEMPERATURES = (1.0, 1.5, 2.5, 4.0, 7.0, 12.0)

BOUNDS = {
    "ombh2": (0.017, 0.027),
    "omch2": (0.09, 0.15),
    "cosmomc_theta": (0.01030, 0.01050),
    "logA": (2.6, 3.5),
    "ns": (0.90, 1.10),
    "tau": (0.0, 0.10),
    "A_planck": (0.90, 1.10),
    "peer_fede": (0.0, 0.18),
    "peer_n": (1.05, 8.0),
}

REFS = {
    "ombh2": 0.0229,
    "omch2": 0.124,
    "cosmomc_theta": 0.010401,
    "logA": 3.06,
    "ns": 0.992,
    "tau": 0.058,
    "A_planck": 1.0,
    "peer_fede": 0.085,
    "peer_n": 3.0,
}

PROPOSALS = {
    "ombh2": 6.5e-5,
    "omch2": 1.1e-3,
    "cosmomc_theta": 1.0e-5,
    "logA": 3.6e-3,
    "ns": 3.3e-3,
    "tau": 5.0e-3,
    "A_planck": 5.0e-4,
    "peer_fede": 8.0e-3,
    "peer_n": 0.12,
}

LIKELIHOODS = (
    "planck_2018_highl_plik.TTTEEE_lite_native",
    "planck_2018_lowl.TT",
    "planck_2018_lowl.EE_sroll2",
    "planck_2018_lensing.native",
    "bao.desi_2024_bao_all",
)


def sampled(name: str) -> dict[str, Any]:
    lo, hi = BOUNDS[name]
    return {
        "prior": {"min": float(lo), "max": float(hi)},
        "ref": {"dist": "norm", "loc": float(REFS[name]), "scale": float(PROPOSALS[name])},
        "proposal": float(PROPOSALS[name]),
    }


def build_info(packages_path: str, output: str | None = None) -> dict[str, Any]:
    params: dict[str, Any] = {
        "ombh2": sampled("ombh2"),
        "omch2": sampled("omch2"),
        "cosmomc_theta": sampled("cosmomc_theta"),
        "logA": sampled("logA"),
        "As": {"value": "lambda logA: 1e-10*np.exp(logA)", "derived": True, "latex": "A_s"},
        "ns": sampled("ns"),
        "tau": sampled("tau"),
        "A_planck": sampled("A_planck"),
        "peer_fede": sampled("peer_fede"),
        "peer_n": sampled("peer_n"),
        "peer_zc": {"value": 3.81, "latex": "\\log_{10}(z_c)"},
        "peer_thetai": {"value": 2.89155, "latex": "\\theta_i"},
        "Alens": {"value": 1.0, "latex": "A_\\mathrm{lens}"},
        "H0": {"derived": True, "latex": "H_0"},
        "omegam": {
            "derived": "lambda omch2, ombh2, H0: (omch2 + ombh2) / (H0/100.0)**2",
            "latex": "\\Omega_m",
        },
        "sigma8": {"derived": True, "latex": "\\sigma_8"},
        "S8": {
            "derived": "lambda sigma8, omegam: sigma8 * (omegam / 0.3)**0.5",
            "latex": "S_8",
        },
        "rdrag": {"derived": True, "latex": "r_d"},
        "thetastar": {"derived": True, "latex": "\\theta_*"},
    }
    for like in LIKELIHOODS:
        params[f"chi2__{like}"] = {"derived": True}

    info: dict[str, Any] = {
        "packages_path": packages_path,
        "debug": False,
        "stop_at_error": True,
        "theory": {
            "peer_scalar_nfree.PEERScalarNFree": {
                "python_path": str(Path(__file__).resolve().parent),
                "path": "global",
                "stop_at_error": True,
                "extra_args": {
                    "mnu": 0.06,
                    "omk": 0.0,
                    "nnu": 3.046,
                    "num_massive_neutrinos": 1,
                    "kmax": 10,
                    "k_per_logint": 130,
                    "nonlinear": True,
                    "lens_potential_accuracy": 8,
                    "lens_margin": 2050,
                    "lAccuracyBoost": 1.2,
                    "min_l_logl_sampling": 6000,
                    "DoLateRadTruncation": False,
                    "recombination_model": "CosmoRec",
                    "halofit_version": "mead2020",
                },
            }
        },
        "likelihood": {name: {"stop_at_error": True} for name in LIKELIHOODS},
        "prior": {
            "planck_calibration_prior": (
                "lambda A_planck: stats.norm.logpdf(A_planck, loc=1.0, scale=0.0025)"
            )
        },
        "params": params,
    }
    if output is not None:
        info["output"] = output
    return info


def write_manifest(root: str | Path, source_sha: str | None = None) -> Path:
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    manifest = {
        "campaign": "PEER microphysics global posterior",
        "stack": list(LIKELIHOODS),
        "anchors": [],
        "Alens": 1.0,
        "peer_log10_zc": 3.81,
        "peer_theta_i": 2.89155,
        "peer_fede_prior": list(BOUNDS["peer_fede"]),
        "peer_n_prior": list(BOUNDS["peer_n"]),
        "temperatures": list(TEMPERATURES),
        "ladders": 4,
        "chains_total": 24,
        "camb": "1.6.6+CosmoRec",
        "cobaya": "3.6.2",
        "source_sha": source_sha,
    }
    path = root / "campaign_manifest.json"
    path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return path
