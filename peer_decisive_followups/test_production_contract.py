import math

import pytest

from peer_decisive_followups.production_contract import (
    build_science_manifest,
    canonical_json,
    classify_lane,
    quadrature,
    sha256_json,
)


def _config():
    return {
        "params": {
            "tau": {"prior": {"min": 0.0, "max": 0.10}},
            "Alens": {"prior": {"min": 0.5, "max": 1.5}},
            "peer_fede": {"value": 0.0},
            "peer_zc": {"value": 3.81},
            "peer_thetai": {"value": 2.89155},
        },
        "likelihood": {
            "act_dr6_cmbonly": {},
            "act_dr6_cmbonly.PlanckActCut": {},
            "planck_2018_lowl.TT": {},
            "planck_2018_lowl.EE_sroll2": {},
            "planck_2018_lensing.native": {},
            "bao.desi_dr2.desi_bao_all": {},
            "shoes_h0.SH0ESGaussian": {},
        },
        "sampler": {"polychord": {"nlive": 400, "nprior": "20nlive", "precision_criterion": 0.1}},
    }


def test_manifest_hash_is_deterministic_across_mapping_order():
    a = {"b": 2, "a": {"y": 2, "x": 1}}
    b = {"a": {"x": 1, "y": 2}, "b": 2}
    assert canonical_json(a) == canonical_json(b)
    assert sha256_json(a) == sha256_json(b)


def test_science_manifest_rejects_unknown_model():
    with pytest.raises(ValueError, match="M1|M3"):
        build_science_manifest("M2", _config())


def test_science_manifest_preserves_tau_prior_exactly():
    manifest = build_science_manifest("M1", _config())
    assert manifest["params"]["tau"]["prior"] == {"min": 0.0, "max": 0.10}
    assert manifest["sampler"]["polychord"]["nlive"] == 400
    assert manifest["sampler"]["polychord"]["nprior"] == "20nlive"


def test_science_identity_ignores_machine_specific_python_paths():
    a = _config()
    b = _config()
    a["theory"] = {"peer_scalar_n3.PEERScalarN3": {"python_path": "/runner/a", "path": "global", "extra_args": {"mnu": 0.06}}}
    b["theory"] = {"peer_scalar_n3.PEERScalarN3": {"python_path": "/runner/b", "path": "/different/runtime", "extra_args": {"mnu": 0.06}}}
    a["likelihood"]["shoes_h0.SH0ESGaussian"] = {"python_path": "/runner/a", "mean": 73.04, "sigma": 1.04}
    b["likelihood"]["shoes_h0.SH0ESGaussian"] = {"python_path": "/runner/b", "mean": 73.04, "sigma": 1.04}
    ma = build_science_manifest("M1", a)
    mb = build_science_manifest("M1", b)
    assert ma["sha256"] == mb["sha256"]


def test_lane_state_is_fail_closed():
    assert classify_lane(complete=True, resumable=True, fatal=False) == "COMPLETE"
    assert classify_lane(complete=False, resumable=True, fatal=False) == "RESUMABLE"
    assert classify_lane(complete=False, resumable=False, fatal=False) == "FAILED"
    assert classify_lane(complete=False, resumable=True, fatal=True) == "FAILED"


def test_quadrature_combines_independent_sigmas():
    assert quadrature(3.0, 4.0) == pytest.approx(5.0)
    assert quadrature(0.1, 0.2) == pytest.approx(math.sqrt(0.05))
