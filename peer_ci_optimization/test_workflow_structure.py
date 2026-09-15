from pathlib import Path

import yaml


WORKFLOW = Path(".github/workflows/peer-n31p-act-20chains-optimized.yml")


def _text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def _workflow() -> dict:
    return yaml.safe_load(_text())


def test_workflow_limits_full_matrix_to_five_parallel_runners() -> None:
    workflow = _workflow()
    shard = workflow["jobs"]["shard"]
    assert shard["strategy"]["max-parallel"] == 5
    assert shard["strategy"]["matrix"]["model"] == ["M2", "M3"]
    assert shard["strategy"]["matrix"]["shard"] == [0, 1, 2, 3, 4]


def test_workflow_builds_runtime_once_and_requires_exact_cache_in_shards() -> None:
    workflow = _workflow()
    preflight_steps = workflow["jobs"]["preflight"]["steps"]
    shard_steps = workflow["jobs"]["shard"]["steps"]
    preflight_cache = next(
        step
        for step in preflight_steps
        if step.get("uses") == "./.github/actions/peer-runtime-cache"
    )
    shard_cache = next(
        step
        for step in shard_steps
        if step.get("uses") == "./.github/actions/peer-runtime-cache"
    )
    assert preflight_cache["with"]["build_if_missing"] is True
    assert shard_cache["with"]["build_if_missing"] is False


def test_workflow_uses_segmented_resume_and_supported_cobaya_geometry() -> None:
    text = _text()
    for required in [
        "resume_run_id",
        "for SEGMENT in 1 2 3 4",
        "timeout --signal=TERM 65m",
        "mcmc['drag'] = True",
        "mcmc['oversample_power'] = 0.4",
        "mcmc['measure_speeds'] = True",
        "mcmc['proposal_scale'] = 1.9",
        "mcmc['Rminus1_stop'] = 0.01",
        "mcmc['Rminus1_cl_stop'] = 0.05",
    ]:
        assert required in text


def test_workflow_preserves_science_and_enforces_global_twenty_chain_gate() -> None:
    text = _text()
    for required in [
        "assert info['params']['peer_zc']['value'] == 3.81",
        "assert info['params']['peer_thetai']['value'] == 2.89155",
        "assert 'act_dr6_cmbonly' in info['likelihood']",
        "assert 'act_dr6_cmbonly.PlanckActCut' in info['likelihood']",
        "--minimum-chains 20",
        "--ess-bulk-limit 1000",
        "--ess-tail-limit 500",
        "--rhat-minus1-limit 0.01",
    ]:
        assert required in text


def test_workflow_prevents_duplicate_queue_hydras_without_killing_active_run() -> None:
    workflow = _workflow()
    assert workflow["concurrency"]["cancel-in-progress"] is False
    assert workflow["concurrency"]["group"] == "peer-act20-optimized"


def test_workflow_uses_absolute_cached_cobaya_and_robust_artifact_roots() -> None:
    text = _text()
    assert '"$RUNTIME/venv/bin/cobaya-run"' in text
    assert 'test -d "$SRC/mcmc"' in text
    assert 'ART="downloads/peer-n31p-act20-opt-${MODEL}-shard${SHARD}"' in text
    assert 'test -d "$ROOT/mcmc"' in text


def test_setup_python_uses_the_official_hyphenated_input_name() -> None:
    workflow = _workflow()
    for job in workflow["jobs"].values():
        for step in job["steps"]:
            if step.get("uses") == "actions/setup-python@v5":
                assert "python-version" in step["with"]
                assert "python_version" not in step["with"]
