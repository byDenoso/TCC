"""Integrity of the installable artifact, including its safe fallback boundary."""
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACK_PATH = ROOT / "gpt/automations/nexo-automation-prompt-pack-v1.1.0.json"


def _pack():
    return json.loads(PACK_PATH.read_text(encoding="utf-8"))


def _digest(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def test_prepared_artifact_cannot_overwrite_scheduler_configuration():
    pack = _pack()
    assert pack["status"] == "PREPARED_INACTIVE"
    assert pack["scheduler_changes_applied"] is False
    assert pack["mandate_activated"] is False
    forbidden = {"schedule", "rrule", "is_enabled", "model", "reasoning_effort", "timezone"}
    assert forbidden.isdisjoint(pack)
    assert len(pack["tasks"]) == 5
    assert {task["source"] for task in pack["tasks"]} == {
        "LEARNER", "EXECUTOR", "ENGINEER", "REFEREE_1", "GUARDIAO"
    }
    ids = [task["observed_task_id"] for task in pack["tasks"]]
    assert len(set(ids)) == 5
    for task in pack["tasks"]:
        assert forbidden.isdisjoint(task)
        assert task["id_status"] == "RECONCILIATION_HINT_RECHECK_LIVE_INVENTORY"


def test_bootstrap_core_and_seed_hashes_match_exact_installable_text():
    pack = _pack()
    core = pack["immutable_core"]
    assert _digest(core) == pack["immutable_core_sha256"]
    for task in pack["tasks"]:
        bootstrap = task["bootstrap_prompt"]
        seed = task["fragment_seed"]
        assert bootstrap.startswith(core + "\n\n")
        assert _digest(bootstrap) == task["bootstrap_sha256"]
        assert seed["role"] == task["source"]
        assert seed["version"] == 1
        assert seed["status"] == "CANDIDATE_NOT_CANONICAL"
        assert _digest(seed["text"]) == seed["sha256"]
        assert bootstrap.endswith(seed["text"])
        assert "approval_ref" not in seed and "mandate_id" not in seed


def test_human_copy_and_json_install_same_five_prompts():
    rendered = PACK_PATH.with_suffix(".md").read_text(encoding="utf-8")
    copied_prompts = [part.split("\n```", 1)[0] for part in rendered.split("```text\n")[1:]]
    assert copied_prompts == [task["bootstrap_prompt"] for task in _pack()["tasks"]]


def test_prepared_canonical_fragment_contract_matches_runtime():
    from runtime.nexo_agent_api.autonomy import FRAGMENT_SCHEMA, FRAGMENTS_DOC, ROLES

    pack = _pack()
    assert pack["fragment_contract"] == FRAGMENT_SCHEMA
    assert pack["canonical_fragment_path"] == FRAGMENTS_DOC
    assert {task["source"] for task in pack["tasks"]} == ROLES
