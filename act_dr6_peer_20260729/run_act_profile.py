#!/usr/bin/env python3
"""ACT DR6 CMB-only stress test for the PEER high-n_s branch.

Uses the official ACT DR6 foreground-marginalized SACC payload and exactly
reimplements the public ACTDR6CMBonly window/covariance projection. CAMB
computes lensed TT/TE/EE spectra including EarlyQuintessence for PEER.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
import time
from dataclasses import asdict, dataclass, replace
from pathlib import Path

import camb
import numpy as np
import pandas as pd
import sacc
from camb import dark_energy, model
from scipy.optimize import minimize


@dataclass(frozen=True)
class CosmoPoint:
    label: str
    H0: float
    ombh2: float
    omch2: float
    tau: float
    As: float
    ns: float
    peer_fede: float
    Alens: float
    peer_zc: float = 3.81
    peer_thetai: float = 2.89155


class ACTDR6Projection:
    def __init__(self, fits_path: Path, ell_min: int = 600, ell_max: int = 6500):
        inp = sacc.Sacc.load_fits(str(fits_path))
        pol_dt = {"t": "0", "e": "e", "b": "b"}
        self.spec_meta: list[dict] = []
        cull: list[np.ndarray] = []
        idx_max = 0
        for pol in ["TT", "TE", "EE"]:
            p1, p2 = pol.lower()
            dt = f"cl_{pol_dt[p1]}{pol_dt[p2]}"
            for tr1, tr2 in inp.get_tracer_combinations(dt):
                ls, mu, ind = inp.get_ell_cl(dt, tr1, tr2, return_ind=True)
                mask = np.logical_and(ls >= ell_min, ls <= ell_max)
                if not np.all(mask):
                    cull.append(ind[~mask])
                if np.any(mask):
                    window = inp.get_bandpower_windows(ind[mask])
                    self.spec_meta.append({
                        "pol": pol.lower(), "ell": ls[mask], "spec": mu[mask],
                        "idx": ind[mask], "window": window,
                    })
                    idx_max = max(idx_max, int(max(ind)))
        self.data_vec = np.zeros((idx_max + 1,))
        self.pol_indices: dict[str, list[int]] = {"tt": [], "te": [], "ee": []}
        for m in self.spec_meta:
            self.data_vec[m["idx"]] = m["spec"]
            self.pol_indices[m["pol"]].extend([int(i) for i in m["idx"]])
        self.covmat = np.array(inp.covariance.covmat, dtype=float, copy=True)
        for inds in cull:
            self.covmat[inds, :] = 0.0
            self.covmat[:, inds] = 0.0
            self.covmat[inds, inds] = 1e10
        self.inv_cov = np.linalg.inv(self.covmat)
        self.n_data = len(self.data_vec)

    def prediction(self, cls: dict[str, np.ndarray], A_act: float, P_act: float) -> np.ndarray:
        ps_vec = np.zeros_like(self.data_vec)
        for m in self.spec_meta:
            idx = m["idx"]
            win = m["window"].weight.T
            ls = m["window"].values.astype(int)
            pol = m["pol"]
            dat = cls[pol][ls] / (A_act * A_act)
            if pol[0] == "e":
                dat = dat / P_act
            if pol[1] == "e":
                dat = dat / P_act
            ps_vec[idx] = win @ dat
        return ps_vec

    def chi2(self, cls: dict[str, np.ndarray], A_act: float, P_act: float) -> float:
        delta = self.data_vec - self.prediction(cls, A_act, P_act)
        return float(delta @ self.inv_cov @ delta)

    def chi2_by_pol(self, cls: dict[str, np.ndarray], A_act: float, P_act: float) -> dict[str, float]:
        pred = self.prediction(cls, A_act, P_act)
        out = {}
        for pol, inds0 in self.pol_indices.items():
            inds = np.array(sorted(set(inds0)), dtype=int)
            d = self.data_vec[inds] - pred[inds]
            c = self.covmat[np.ix_(inds, inds)]
            out[pol] = float(d @ np.linalg.inv(c) @ d)
        return out


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def camb_cls(point: CosmoPoint, lmax: int, precision: str = "official") -> tuple[dict[str, np.ndarray], dict]:
    kwargs = dict(
        H0=point.H0,
        ombh2=point.ombh2,
        omch2=point.omch2,
        mnu=0.06,
        omk=0.0,
        nnu=3.046,
        num_massive_neutrinos=1,
        tau=point.tau,
        As=point.As,
        ns=point.ns,
        Alens=point.Alens,
        lmax=lmax,
        lens_potential_accuracy=8 if precision == "official" else 10,
        min_l_logl_sampling=6000,
    )
    pars = camb.set_params(**kwargs)
    pars.NonLinear = model.NonLinear_both
    pars.set_for_lmax(lmax, lens_potential_accuracy=kwargs["lens_potential_accuracy"])
    if point.peer_fede > 1e-10:
        ede = dark_energy.EarlyQuintessence()
        ede.n = 3
        ede.fde_zc = point.peer_fede
        ede.zc = 10.0 ** point.peer_zc
        ede.theta_i = point.peer_thetai
        pars.DarkEnergy = ede
    t0 = time.time()
    results = camb.get_results(pars)
    powers = results.get_cmb_power_spectra(pars, CMB_unit="muK", raw_cl=False, lmax=lmax)
    total = powers["total"]
    cls = {"tt": total[:, 0], "ee": total[:, 1], "te": total[:, 3]}
    derived = results.get_derived_params()
    meta = {
        "runtime_s": time.time() - t0,
        "H0": point.H0,
        "rdrag": float(derived.get("rdrag", np.nan)),
        "thetastar": float(derived.get("thetastar", np.nan)),
    }
    return cls, meta


def optimize_calibration(like: ACTDR6Projection, cls: dict[str, np.ndarray]) -> dict:
    def objective(x: np.ndarray) -> float:
        return like.chi2(cls, float(x[0]), float(x[1]))
    res = minimize(objective, np.array([1.0, 1.0]), method="L-BFGS-B",
                   bounds=[(0.5, 1.5), (0.9, 1.1)],
                   options={"ftol": 1e-12, "gtol": 1e-8, "maxiter": 500})
    pol = like.chi2_by_pol(cls, float(res.x[0]), float(res.x[1]))
    return {
        "chi2_act": float(res.fun), "A_act": float(res.x[0]), "P_act": float(res.x[1]),
        "calibration_success": bool(res.success), "calibration_message": str(res.message),
        "chi2_tt_only": pol["tt"], "chi2_te_only": pol["te"], "chi2_ee_only": pol["ee"],
    }


def eval_point(like: ACTDR6Projection, point: CosmoPoint, lmax: int, precision: str = "official") -> dict:
    cls, meta = camb_cls(point, lmax, precision=precision)
    cal = optimize_calibration(like, cls)
    return {**asdict(point), **meta, **cal, "precision": precision}


def quadratic_minimum(x: np.ndarray, y: np.ndarray) -> dict:
    order = np.argsort(y)
    take = np.sort(order[:min(5, len(order))])
    xx, yy = x[take], y[take]
    try:
        a, b, c = np.polyfit(xx, yy, 2)
        xm = -b / (2 * a) if a > 0 else float(x[order[0]])
        xm = float(np.clip(xm, x.min(), x.max()))
        ym = float(a * xm * xm + b * xm + c)
        return {"ns_quad": xm, "chi2_quad": ym, "quad_a": float(a), "fit_ok": bool(a > 0)}
    except Exception:
        return {"ns_quad": float(x[order[0]]), "chi2_quad": float(y[order[0]]), "quad_a": np.nan, "fit_ok": False}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fits", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--lmax", type=int, default=9000)
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    fits = Path(args.fits)
    like = ACTDR6Projection(fits)

    manifest = {
        "python": sys.version,
        "platform": platform.platform(),
        "numpy": np.__version__,
        "camb": camb.__version__,
        "sacc": getattr(sacc, "__version__", "unknown"),
        "fits": str(fits),
        "fits_sha256": sha256(fits),
        "n_data": like.n_data,
        "ell_cuts": [600, 6500],
        "lmax": args.lmax,
    }
    (out / "runtime_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    shoes = CosmoPoint(
        label="peer_alens_shoes_trgb_mean", H0=71.438, ombh2=0.0230254,
        omch2=0.125299, tau=0.0551353, As=2.10858e-9, ns=0.992643,
        peer_fede=0.0903422, Alens=1.0869,
    )
    anchor_free = CosmoPoint(
        label="peer_alens_planck_bao_best", H0=70.226598, ombh2=0.022802383,
        omch2=0.12296062, tau=0.047808176, As=2.0614514e-9, ns=0.9846679,
        peer_fede=0.061362115, Alens=1.1060144,
    )

    rows: list[dict] = []
    for p in [
        shoes,
        replace(shoes, label="shoes_same_point_ns_0p965", ns=0.965),
        replace(shoes, label="shoes_same_point_f0_ns_0p965", peer_fede=0.0, ns=0.965),
        anchor_free,
        replace(anchor_free, label="anchor_free_same_point_ns_0p965", ns=0.965),
        replace(anchor_free, label="anchor_free_same_point_f0_ns_0p965", peer_fede=0.0, ns=0.965),
    ]:
        print(f"EVAL {p.label}", flush=True)
        rows.append(eval_point(like, p, args.lmax))
    pd.DataFrame(rows).to_csv(out / "archived_point_act_scores.csv", index=False)

    f_grid = [0.0, 0.06, 0.09, 0.12]
    ns_grid = [0.960, 0.970, 0.980, 0.990, 0.995, 1.000, 1.010]
    grid_rows: list[dict] = []
    for f in f_grid:
        for ns in ns_grid:
            p = replace(shoes, label=f"grid_f{f:.3f}_ns{ns:.3f}", peer_fede=f, ns=ns)
            print(f"GRID f={f:.3f} ns={ns:.3f}", flush=True)
            r = eval_point(like, p, args.lmax)
            grid_rows.append(r)
            pd.DataFrame(grid_rows).to_csv(out / "fpeer_ns_act_grid.partial.csv", index=False)
    grid = pd.DataFrame(grid_rows)
    grid["delta_chi2_global_grid"] = grid["chi2_act"] - grid["chi2_act"].min()
    grid.to_csv(out / "fpeer_ns_act_grid.csv", index=False)

    profile_rows = []
    for f, g in grid.groupby("peer_fede"):
        g = g.sort_values("ns")
        q = quadratic_minimum(g["ns"].to_numpy(), g["chi2_act"].to_numpy())
        i = int(g["chi2_act"].idxmin())
        best = grid.loc[i]
        profile_rows.append({
            "peer_fede": float(f), "ns_grid_best": float(best["ns"]),
            "chi2_grid_best": float(best["chi2_act"]), **q,
        })
    prof = pd.DataFrame(profile_rows).sort_values("peer_fede")
    prof["delta_chi2_profile"] = prof["chi2_grid_best"] - prof["chi2_grid_best"].min()
    prof.to_csv(out / "fpeer_profile_from_act_grid.csv", index=False)

    best_idx = int(grid["chi2_act"].idxmin())
    br = grid.loc[best_idx]
    bp = replace(shoes, label="best_grid_high_precision", peer_fede=float(br["peer_fede"]), ns=float(br["ns"]))
    hp = eval_point(like, bp, args.lmax, precision="high")
    official_best = dict(br)
    precision = {
        "official_best": {k: (float(v) if isinstance(v, (np.floating, float, int)) else v) for k, v in official_best.items()},
        "high_precision": hp,
        "delta_chi2_high_minus_official": float(hp["chi2_act"] - br["chi2_act"]),
    }
    (out / "precision_gate.json").write_text(json.dumps(precision, indent=2, default=str), encoding="utf-8")

    gbest = grid.loc[grid["chi2_act"].idxmin()]
    f0best = grid[grid.peer_fede == 0.0].sort_values("chi2_act").iloc[0]
    active = grid[grid.peer_fede > 0.0].sort_values("chi2_act").iloc[0]
    summary = {
        "test_class": "OFFICIAL_ACT_DR6_CMBONLY_FIXED_BACKGROUND_PROFILE",
        "global_grid_best": {"f_PEER": float(gbest.peer_fede), "ns": float(gbest.ns), "chi2_ACT": float(gbest.chi2_act)},
        "best_null_grid": {"f_PEER": 0.0, "ns": float(f0best.ns), "chi2_ACT": float(f0best.chi2_act)},
        "best_active_grid": {"f_PEER": float(active.peer_fede), "ns": float(active.ns), "chi2_ACT": float(active.chi2_act)},
        "delta_chi2_active_minus_null": float(active.chi2_act - f0best.chi2_act),
        "archived_shoes_point": rows[0],
        "archived_anchor_free_point": rows[3],
        "precision_delta_chi2": precision["delta_chi2_high_minus_official"],
        "claim_boundary": [
            "ACT DR6 data and official projection are used.",
            "The f_PEER-ns scan fixes the remaining cosmological background to the archived PEER+A_lens mean.",
            "This is a direct damping-tail stress test and likelihood-geometry diagnostic, not a matched full-stack posterior or model-selection result."
        ]
    }
    (out / "act_profile_summary.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    print(json.dumps(summary, indent=2, default=str), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
