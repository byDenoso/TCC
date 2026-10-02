import json

import pytest

from runtime.nexo_agent_api.public_projection import build_public_projection, verify_projection
from runtime.nexo_agent_api.tower_paths import entity_path


def test_projection_preserves_terminal_attempt_and_review_as_separate_axes(tmp_path):
    root = tmp_path / "tower"
    path = entity_path(root, "test", "TEST-PUBLIC-LIFECYCLE")
    path.parent.mkdir(parents=True)
    original = {
        "id": "TEST-PUBLIC-LIFECYCLE", "status": "DONE", "state": "DONE",
        "execution_phase": "RUNNING", "review_state": "PENDING_REVIEW",
        "verdict": "SUPPORTED", "prereg_hash": "frozen-design",
        "domain": "science", "semantic": {"domain_id": "D1"},
        "execution_attempt": {"private_runner_diagnostic": "DO_NOT_PUBLISH"},
    }
    path.write_text(json.dumps(original), encoding="utf-8")
    projection = build_public_projection(root)
    [test] = projection["tests"]
    assert test["status"] == "DONE"
    assert test["execution_phase"] == "RUNNING"
    assert test["review_state"] == "PENDING_REVIEW"
    assert test["prereg_hash"] == "frozen-design"
    assert "DO_NOT_PUBLISH" not in json.dumps(projection)
    assert json.loads(path.read_text(encoding="utf-8")) == original
    verify_projection(projection)


def test_projection_does_not_invent_a_phase_for_legacy_records(tmp_path):
    root = tmp_path / "tower"
    path = entity_path(root, "test", "TEST-LEGACY-LIFECYCLE")
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"id": "TEST-LEGACY-LIFECYCLE", "status": "DONE", "domain": "science"}), encoding="utf-8")
    [test] = build_public_projection(root)["tests"]
    assert "execution_phase" not in test


def test_projection_drops_unrecognized_phase_diagnostics(tmp_path):
    root = tmp_path / "tower"
    path = entity_path(root, "test", "TEST-INVALID-LIFECYCLE")
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({
        "id": "TEST-INVALID-LIFECYCLE", "status": "DONE", "domain": "science",
        "execution_phase": {"private_reason": "DO_NOT_PUBLISH"},
    }), encoding="utf-8")
    projection = build_public_projection(root)
    assert "execution_phase" not in projection["tests"][0]
    assert "DO_NOT_PUBLISH" not in json.dumps(projection)


@pytest.mark.parametrize("phase", ["DISPATCH_PENDING", "DISPATCHED", "READY"])
def test_projection_preserves_actual_dispatch_and_failure_lifecycle(phase, tmp_path):
    root = tmp_path / "tower"
    path = entity_path(root, "test", "TEST-DISPATCH-LIFECYCLE")
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({
        "id": "TEST-DISPATCH-LIFECYCLE", "status": "READY", "domain": "science",
        "execution_phase": phase,
    }), encoding="utf-8")
    [test] = build_public_projection(root)["tests"]
    assert test["execution_phase"] == phase
    assert test["status"] == "READY"
