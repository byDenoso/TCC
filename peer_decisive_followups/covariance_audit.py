#!/usr/bin/env python3
"""Fail-closed gate for an ACT×SPT joint high-ell likelihood."""
from __future__ import annotations
import argparse, json
from pathlib import Path
import numpy as np


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cross-cov", type=Path)
    ap.add_argument("--act-size", type=int)
    ap.add_argument("--spt-size", type=int)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    report = {
        "question": "Can ACT DR6 and SPT-3G high-l likelihoods be multiplied as a joint likelihood with adequate covariance?",
        "joint_likelihood_allowed": False,
        "separate_likelihood_replication_allowed": True,
        "cross_covariance": None,
        "status": "BLOCKED_NO_CROSS_COVARIANCE",
        "rule": "Do not multiply overlapping high-l CMB likelihoods unless the ACT×SPT cross-covariance or an explicitly non-overlapping validated construction is supplied.",
    }
    if args.cross_cov and args.cross_cov.exists():
        arr = np.load(args.cross_cov)
        if isinstance(arr, np.lib.npyio.NpzFile):
            keys = list(arr.files)
            if len(keys) != 1:
                raise SystemExit("cross-cov npz must contain exactly one matrix")
            cov = np.asarray(arr[keys[0]], dtype=float)
        else:
            cov = np.asarray(arr, dtype=float)
        expected = (args.act_size, args.spt_size)
        shape_ok = cov.shape == expected
        finite = bool(np.isfinite(cov).all())
        report["cross_covariance"] = {"path": str(args.cross_cov), "shape": list(cov.shape), "expected": list(expected), "finite": finite}
        if shape_ok and finite:
            report["status"] = "CROSS_COV_PRESENT_DIMENSIONALLY_VALID"
            report["joint_likelihood_allowed"] = True
        else:
            report["status"] = "BLOCKED_INVALID_CROSS_COVARIANCE"
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["status"] in {"BLOCKED_NO_CROSS_COVARIANCE", "CROSS_COV_PRESENT_DIMENSIONALLY_VALID"} else 2

if __name__ == "__main__":
    raise SystemExit(main())
