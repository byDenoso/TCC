from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_noop_executor_contract():
    path = ROOT / ".github" / "workflows" / "nexo-noop-executor.yml"
    text = path.read_text(encoding="utf-8")
    assert "workflow_dispatch:" in text
    for token in ["correlation_id:", "campaign_id:", "test_id:", "should_pass:"]:
        assert token in text
    assert "run-name:" in text
    assert "inputs.correlation_id" in text
    assert "permissions:\n  contents: read" in text
    assert "actions/upload-artifact@v4" in text
    assert "executor-result.json" in text
    assert "nexo-executor-result-" in text


def test_orchestrator_is_fail_closed_and_dry_run_by_default_when_present():
    path = ROOT / ".github" / "workflows" / "nexo-orchestrator.yml"
    if not path.exists():
        return
    text = path.read_text(encoding="utf-8")
    assert "default: true" in text
    assert "pull_request_target" not in text
    assert "schedule:" not in text
    assert "actions: write" in text
    assert "ready_for_learning" in text
