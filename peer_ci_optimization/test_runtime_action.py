from pathlib import Path

import yaml


ACTION = Path(".github/actions/peer-runtime-cache/action.yml")


def _load() -> dict:
    return yaml.safe_load(ACTION.read_text(encoding="utf-8"))


def test_runtime_action_uses_exact_immutable_cache_key() -> None:
    action = _load()
    steps = action["runs"]["steps"]
    cache = next(step for step in steps if step.get("uses") == "actions/cache@v4")
    assert "restore-keys" not in cache["with"]
    key = cache["with"]["key"]
    for token in [
        "${{ runner.os }}",
        "${{ inputs.python_version }}",
        "${{ inputs.source_run_id }}",
        "${{ inputs.act_commit }}",
        "${{ inputs.cache_version }}",
    ]:
        assert token in key


def test_runtime_action_verifies_payload_and_installs_act_from_wheel() -> None:
    action = _load()
    scripts = "\n".join(step.get("run", "") for step in action["runs"]["steps"])
    assert "sha256sum -c" in scripts
    assert "pip wheel" in scripts
    assert "pip install -e" not in scripts
    assert "validated-act-cosmorec-runtime-gslfix" in scripts
    assert "official-likelihood-packages-v3" in scripts


def test_runtime_action_exposes_stable_paths_and_refuses_unexpected_miss() -> None:
    action = _load()
    assert set(action["outputs"]) == {"runtime_root", "python", "packages_path", "cache_hit"}
    scripts = "\n".join(step.get("run", "") for step in action["runs"]["steps"])
    assert "build_if_missing" in action["inputs"]
    assert "Runtime cache miss and build_if_missing=false" in scripts
    assert "$GITHUB_PATH" in scripts
    assert "$GITHUB_ENV" in scripts
    assert scripts.count("from importlib.metadata import version") >= 2
    assert "version('cobaya')" in scripts


def test_runtime_action_uses_bracket_access_for_hyphenated_cache_output() -> None:
    text = ACTION.read_text(encoding="utf-8")
    assert "steps.cache.outputs['cache-hit']" in text
    assert "steps.cache.outputs.cache-hit" not in text


def test_runtime_action_materializes_cosmorec_paths_at_workspace_root() -> None:
    action = _load()
    scripts = "\n".join(step.get("run", "") for step in action["runs"]["steps"])
    assert 'ln -sfn "$RUNTIME/Rec_database" "$GITHUB_WORKSPACE/Rec_database"' in scripts
    assert 'ln -sfn "$RUNTIME/Development" "$GITHUB_WORKSPACE/Development"' in scripts
    assert "Effective_Rates.HI/Effective_Rate_Tables.nS_3/res_state_list.dat" in scripts
