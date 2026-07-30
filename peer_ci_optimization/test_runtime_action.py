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
        "${{ inputs.python-version }}",
        "${{ inputs.source-run-id }}",
        "${{ inputs.act-commit }}",
        "${{ inputs.cache-version }}",
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
    assert set(action["outputs"]) == {
        "runtime-root",
        "python",
        "packages-path",
        "cache-hit",
    }
    scripts = "\n".join(step.get("run", "") for step in action["runs"]["steps"])
    assert "build-if-missing" in action["inputs"]
    assert "Runtime cache miss and build-if-missing=false" in scripts
    assert "$GITHUB_PATH" in scripts
    assert "$GITHUB_ENV" in scripts
