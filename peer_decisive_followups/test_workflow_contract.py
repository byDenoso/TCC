from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"


def _read(name: str) -> str:
    text = (WORKFLOWS / name).read_text(encoding="utf-8")
    assert isinstance(yaml.safe_load(text), dict)
    return text


def test_continuation_workflow_is_restore_resume_only():
    text = _read("peer-nested-continuation-20260911.yml")
    assert "workflow_dispatch" in text
    assert "parent_run_id" in text
    assert "expected_parent_digest" in text
    assert "--seconds 19200" in text
    assert "orchestrate_segment" in text
    assert "concurrency:" in text
    for forbidden in ("tau['prior']", '"10nlive"', "patch_historical_runner", ".replace("):
        assert forbidden not in text


def test_bootstrap_workflow_requires_long_lived_self_hosted_runner():
    text = _read("peer-nested-matched-20260910.yml")
    assert "workflow_dispatch" in text
    assert "self-hosted" in text
    assert "timeout-minutes: 1440" in text
    assert "bootstrap_production" in text
    for forbidden in ("tau['prior']", '"10nlive"', "patch_historical_runner", ".replace("):
        assert forbidden not in text


def test_prior_normalization_is_separate_from_data_sampling():
    text = _read("act-dr6-laneb-full-planck.yml")
    assert "prior_normalization" in text
    assert "bootstrap_production" not in text
    assert "orchestrate_segment" not in text
    assert "tau['prior']" not in text
    assert '"10nlive"' not in text


def test_tdd_gate_never_runs_production_science():
    text = _read("peer-nested-segment-launch-20260911.yml")
    assert "pytest" in text
    assert "bootstrap_production" not in text
    assert "orchestrate_segment" not in text
