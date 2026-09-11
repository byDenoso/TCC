from pathlib import Path

import yaml

from peer_decisive_followups.production_config import (
    build_production_configs,
    validate_frozen_config,
)

LIKES = [
    "act_dr6_cmbonly",
    "act_dr6_cmbonly.PlanckActCut",
    "planck_2018_lowl.TT",
    "planck_2018_lowl.EE_sroll2",
    "planck_2018_lensing.native",
    "bao.desi_dr2.desi_bao_all",
    "shoes_h0.SH0ESGaussian",
]


def _science_tree(tmp_path: Path) -> Path:
    root = tmp_path / "science"
    module = root / "act_dr6_mcmc_20260729"
    module.mkdir(parents=True)
    likes = repr({name: {} for name in LIKES})
    (module / "campaign.py").write_text(
        "def base_info(model, packages, output):\n"
        "    params = {\n"
        "      'tau': {'prior': {'min': 0.0, 'max': 0.10}},\n"
        "      'peer_zc': {'value': 3.81},\n"
        "      'peer_thetai': {'value': 2.89155},\n"
        "      'Alens': {'prior': {'min': 0.5, 'max': 1.5}},\n"
        "    }\n"
        "    params['peer_fede'] = ({'prior': {'min': 0.0, 'max': 0.18}} if model == 'M3' else {'value': 0.0})\n"
        f"    return {{'packages_path': packages, 'output': output, 'force': True, 'theory': {{'peer_scalar_n3.PEERScalarN3': {{}}}}, 'likelihood': {likes}, 'prior': {{}}, 'params': params}}\n",
        encoding="utf-8",
    )
    return root


def test_build_preserves_scientific_priors_and_production_sampler(tmp_path: Path):
    science = _science_tree(tmp_path)
    root = tmp_path / "out"
    result = build_production_configs(science, "M3", "/packages", root, 1234, continuation=False)
    data = yaml.safe_load((root / "data.yaml").read_text(encoding="utf-8"))
    pc = data["sampler"]["polychord"]
    assert data["params"]["tau"]["prior"] == {"min": 0.0, "max": 0.10}
    assert data["params"]["peer_fede"]["prior"] == {"min": 0.0, "max": 0.18}
    assert data["params"]["Alens"]["prior"] == {"min": 0.5, "max": 1.5}
    assert pc["nlive"] == 400
    assert pc["nprior"] == "20nlive"
    assert pc["precision_criterion"] == 0.001
    assert data["resume"] is False and data["force"] is True
    assert result["science_manifest"]["model"] == "M3"


def test_continuation_changes_only_execution_resume_semantics(tmp_path: Path):
    science = _science_tree(tmp_path)
    root = tmp_path / "out"
    build_production_configs(science, "M1", "/packages", root, 4321, continuation=True)
    data = yaml.safe_load((root / "data.yaml").read_text(encoding="utf-8"))
    assert data["resume"] is True and data["force"] is False
    assert data["params"]["tau"]["prior"]["min"] == 0.0
    assert data["params"]["peer_fede"] == {"value": 0.0}


def test_validate_frozen_config_rejects_science_drift(tmp_path: Path):
    science = _science_tree(tmp_path)
    root = tmp_path / "out"
    build_production_configs(science, "M1", "/packages", root, 77)
    path = root / "data.yaml"
    info = yaml.safe_load(path.read_text(encoding="utf-8"))
    info["params"]["tau"]["prior"]["min"] = 0.01
    path.write_text(yaml.safe_dump(info, sort_keys=False), encoding="utf-8")
    try:
        validate_frozen_config(path, "M1")
    except ValueError as exc:
        assert "tau" in str(exc)
    else:
        raise AssertionError("tau prior drift was accepted")


def test_validate_requires_exact_likelihood_stack(tmp_path: Path):
    science = _science_tree(tmp_path)
    root = tmp_path / "out"
    build_production_configs(science, "M1", "/packages", root, 78)
    path = root / "data.yaml"
    info = yaml.safe_load(path.read_text(encoding="utf-8"))
    info["likelihood"].pop("shoes_h0.SH0ESGaussian")
    path.write_text(yaml.safe_dump(info, sort_keys=False), encoding="utf-8")
    try:
        validate_frozen_config(path, "M1")
    except ValueError as exc:
        assert "likelihood" in str(exc).lower()
    else:
        raise AssertionError("likelihood drift was accepted")
