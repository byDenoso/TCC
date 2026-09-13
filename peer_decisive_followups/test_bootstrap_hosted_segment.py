from __future__ import annotations

import importlib.util


def _load():
    spec = importlib.util.find_spec("peer_decisive_followups.bootstrap_hosted_segment")
    assert spec is not None, "bootstrap_hosted_segment module is required"
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_classifies_expected_pre_resume_checkpoint_exit():
    module = _load()
    assert module.classify_segment(exit_code=86, bootstrap_valid=True, native_resumable=False) == "BOOTSTRAP_REQUIRED"


def test_native_resume_wins_over_process_exit():
    module = _load()
    assert module.classify_segment(exit_code=143, bootstrap_valid=False, native_resumable=True) == "RESUMABLE"


def test_unexpected_exit_is_failed_even_if_stale_bootstrap_exists():
    module = _load()
    assert module.classify_segment(exit_code=1, bootstrap_valid=True, native_resumable=False) == "FAILED"


def test_zero_exit_without_native_resume_is_failed():
    module = _load()
    assert module.classify_segment(exit_code=0, bootstrap_valid=False, native_resumable=False) == "FAILED"


def test_segment_budget_is_execution_only_environment():
    module = _load()
    env = module.segment_environment(1000, base={"KEEP": "x"})
    assert env["POLYCHORD_BOOTSTRAP_SEGMENT_VALID"] == "1000"
    assert env["KEEP"] == "x"
    for forbidden in ("tau", "peer_fede", "Alens", "nlive", "nprior", "precision_criterion"):
        assert forbidden not in env
