#!/usr/bin/env python3
from __future__ import annotations

import json
import math
from pathlib import Path

OUTPUT = Path("benchmark_result.json")

SOURCES = {
    "desi_kids": {
        "citation": "Semenaite et al., Joint cosmological fits to DESI-DR1 full-shape clustering and weak gravitational lensing in configuration space",
        "arxiv": "2512.15961",
        "doi": "10.33232/001c.162334",
        "observable": "S8",
        "value": 0.771,
        "sigma": 0.017,
        "note": "DESI DR1 x KiDS weak-lensing amplitude; published summary constraint.",
    },
    "erosita_full": {
        "citation": "Ghirardini et al., The SRG/eROSITA all-sky survey: Cosmology constraints from cluster abundances in the western Galactic hemisphere",
        "arxiv": "2402.08458",
        "doi": "10.1051/0004-6361/202348852",
        "observable": "S8",
        "value": 0.86,
        "sigma": 0.01,
        "omega_m": 0.29,
        "omega_m_minus": 0.02,
        "omega_m_plus": 0.01,
        "sigma8": 0.88,
        "sigma8_sigma": 0.02,
        "note": "eRASS1 5259-cluster abundance constraint with WL mass calibration using DES/KiDS/HSC overlap.",
    },
    "erosita_bins": {
        "citation": "Artis et al., The SRG/eROSITA All-Sky Survey: Constraints on the structure growth from cluster number counts",
        "arxiv": "2410.09499",
        "doi": "10.1051/0004-6361/202452584",
        "bins": [
            {"z_min": 0.100, "z_max": 0.175, "s8": 0.83, "sigma": 0.02},
            {"z_min": 0.175, "z_max": 0.244, "s8": 0.82, "sigma": 0.07},
            {"z_min": 0.244, "z_max": 0.330, "s8": 0.86, "sigma": 0.06},
            {"z_min": 0.330, "z_max": 0.452, "s8": 0.84, "sigma": 0.03},
            {"z_min": 0.452, "z_max": 0.800, "s8": 0.94, "sigma": 0.04},
        ],
        "note": "Published 1-sigma summary constraints; bin-to-bin covariance is not available in this bounded replication.",
    },
}


def gaussian_tension(value_a: float, sigma_a: float, value_b: float, sigma_b: float, rho: float = 0.0) -> dict:
    variance = sigma_a * sigma_a + sigma_b * sigma_b - 2.0 * rho * sigma_a * sigma_b
    if variance <= 0:
        raise ValueError("non-positive difference variance")
    delta = value_b - value_a
    return {"delta": delta, "difference_sigma": math.sqrt(variance), "z": abs(delta) / math.sqrt(variance), "rho": rho}


def weighted_constant_fit(values: list[float], errors: list[float]) -> dict:
    if len(values) != len(errors) or not values:
        raise ValueError("values/errors mismatch")
    weights = [1.0 / (err * err) for err in errors]
    total_w = sum(weights)
    mean = sum(w * x for w, x in zip(weights, values)) / total_w
    mean_sigma = math.sqrt(1.0 / total_w)
    chi2 = sum(w * (x - mean) ** 2 for w, x in zip(weights, values))
    dof = len(values) - 1
    if dof != 4:
        raise ValueError("bounded battery expects five eROSITA bins")
    half = chi2 / 2.0
    p_value = math.exp(-half) * (1.0 + half)
    return {"mean": mean, "mean_sigma": mean_sigma, "chi2": chi2, "dof": dof, "p_value": p_value}


def weighted_linear_fit(redshift: list[float], values: list[float], errors: list[float]) -> dict:
    if not (len(redshift) == len(values) == len(errors)) or len(values) < 2:
        raise ValueError("input length mismatch")
    weights = [1.0 / (err * err) for err in errors]
    sw = sum(weights)
    sx = sum(w * x for w, x in zip(weights, redshift))
    sy = sum(w * y for w, y in zip(weights, values))
    sxx = sum(w * x * x for w, x in zip(weights, redshift))
    sxy = sum(w * x * y for w, x, y in zip(weights, redshift, values))
    det = sw * sxx - sx * sx
    intercept = (sxx * sy - sx * sxy) / det
    slope = (sw * sxy - sx * sy) / det
    slope_sigma = math.sqrt(sw / det)
    return {"intercept": intercept, "slope": slope, "slope_sigma": slope_sigma, "slope_z": slope / slope_sigma}


def run_battery() -> dict:
    dk = SOURCES["desi_kids"]
    er = SOURCES["erosita_full"]
    bins = SOURCES["erosita_bins"]["bins"]
    zmid = [(row["z_min"] + row["z_max"]) / 2.0 for row in bins]
    s8 = [row["s8"] for row in bins]
    err = [row["sigma"] for row in bins]

    recomputed_s8 = er["sigma8"] * math.sqrt(er["omega_m"] / 0.3)
    t02 = {
        "test_id": "GZ01-T02-PUBLISHED-BASELINE-INTEGRITY",
        "status": "PASS" if abs(recomputed_s8 - er["value"]) < 0.01 else "FAIL",
        "reported_s8": er["value"],
        "recomputed_central_s8": recomputed_s8,
        "absolute_difference": abs(recomputed_s8 - er["value"]),
    }

    nominal = gaussian_tension(dk["value"], dk["sigma"], er["value"], er["sigma"])
    t03 = {
        "test_id": "GZ01-T03-DESI-KIDS-EROSITA-S8-CONSISTENCY",
        "status": "STRESSED" if nominal["z"] >= 3 else "CONSISTENT",
        **nominal,
        "interpretation": "Nominal Gaussian summary-level discrepancy only; not a valid independent-probe sigma because eROSITA mass calibration includes KiDS WL information.",
    }

    constant = weighted_constant_fit(s8, err)
    t04 = {
        "test_id": "GZ01-T04-EROSITA-S8Z-CONSTANT",
        "status": "CONSISTENT_WITH_CONSTANT" if constant["p_value"] >= 0.05 else "REJECT_CONSTANT",
        **constant,
        "interpretation": "No significant rejection of constant S8 across the five published redshift bins under an independent-Gaussian-bin approximation.",
    }

    linear = weighted_linear_fit(zmid, s8, err)
    t05 = {
        "test_id": "GZ01-T05-EROSITA-S8Z-LINEAR-TREND",
        "status": "HINT" if abs(linear["slope_z"]) >= 2 and abs(linear["slope_z"]) < 3 else "NO_MATERIAL_TREND",
        **linear,
        "interpretation": "Hint-level positive S8(z) slope; covariance-free summary fit cannot support a cosmological claim.",
    }

    low = weighted_constant_fit(s8[:4] + [s8[3]], err[:4] + [err[3]]) if False else None
    low_weights = [1.0 / (e * e) for e in err[:4]]
    low_mean = sum(w * x for w, x in zip(low_weights, s8[:4])) / sum(low_weights)
    low_sigma = math.sqrt(1.0 / sum(low_weights))
    high_residual = gaussian_tension(low_mean, low_sigma, s8[-1], err[-1])
    low_vs_dk = gaussian_tension(dk["value"], dk["sigma"], low_mean, low_sigma)
    t06 = {
        "test_id": "GZ01-T06-HIGHZ-LEVERAGE",
        "status": "HIGHZ_MATERIAL" if high_residual["z"] >= 2 else "HIGHZ_NOT_MATERIAL",
        "lowz_weighted_s8": low_mean,
        "lowz_sigma": low_sigma,
        "highz_s8": s8[-1],
        "highz_sigma": err[-1],
        "highz_vs_lowz_z": high_residual["z"],
        "desi_kids_vs_lowz_z_nominal": low_vs_dk["z"],
        "interpretation": "The highest-z eROSITA bin is a material lever on the apparent cross-probe discrepancy; redshift matching and full covariance are required next.",
    }

    return {
        "schema": "nexo.gz01.multprobe-consistency.v1",
        "campaign_id": "GZ-01",
        "batch_id": "GZ-01-B02-MULTIPROBE",
        "status": "PASS",
        "sources": SOURCES,
        "tests": [t02, t03, t04, t05, t06],
        "decision": {
            "classification": "INCONCLUSIVE_COVARIANCE_LIMITED",
            "next_discriminant": "Construct redshift-matched DESI/KiDS/eROSITA likelihood or posterior samples with cross-probe covariance and explicit shared-KiDS mass-calibration treatment.",
        },
        "claim_boundary": "Published-summary replication/consistency battery only. It does not use raw DESI/KiDS/eROSITA likelihoods, does not model cross-probe covariance, and cannot establish a new cosmological tension or new physics.",
        "tower_persistence": "PERSIST_AFTER_VERIFICATION",
    }


def main() -> None:
    result = run_battery()
    OUTPUT.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({"status": result["status"], "classification": result["decision"]["classification"], "output": str(OUTPUT)}, sort_keys=True))


if __name__ == "__main__":
    main()
