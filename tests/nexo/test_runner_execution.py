from __future__ import annotations

from nexo_control.github_runner import execute_dispatch_request


class FakeClient:
    def __init__(self, existing=None, final=None, artifacts=None, diagnostics=None):
        self.existing = list(existing or [])
        self.final = final or {
            "id": 99,
            "status": "completed",
            "conclusion": "success",
            "head_sha": "executor-sha",
            "display_title": "CORR",
            "head_branch": "feature",
        }
        self.artifacts = list(artifacts or [{"id": 7, "name": "nexo-executor-result-CORR"}])
        self.diagnostics = dict(diagnostics or {"passed": True, "score": 1.0})
        self.dispatch_calls = []

    def find_correlated_runs(self, workflow, correlation_id, ref):
        return list(self.existing)

    def dispatch_workflow(self, workflow, ref, inputs):
        self.dispatch_calls.append((workflow, ref, dict(inputs)))

    def wait_for_correlated_run(self, workflow, correlation_id, ref):
        return dict(self.final)

    def wait_for_run_completion(self, run_id):
        return dict(self.final)

    def list_artifacts(self, run_id):
        return list(self.artifacts)

    def download_json_artifact(self, artifact_id, filename):
        assert filename == "executor-result.json"
        return dict(self.diagnostics)


def request() -> dict:
    return {
        "test_id": "T-ENG001",
        "workflow_alias": "nexo_noop",
        "workflow": ".github/workflows/nexo-noop-executor.yml",
        "ref": "feature",
        "correlation_id": "CORR",
        "inputs": {
            "correlation_id": "CORR",
            "campaign_id": "NEXO-NOOP-001",
            "test_id": "T-ENG001",
            "should_pass": True,
        },
        "validator": "contract_test_pass",
    }


def test_new_request_dispatches_once_and_promotes():
    client = FakeClient()
    envelope = execute_dispatch_request(
        client,
        request(),
        campaign_id="NEXO-NOOP-001",
        campaign_commit="campaign-sha",
        validator_commit="validator-sha",
    )
    assert len(client.dispatch_calls) == 1
    assert envelope["validation"]["status"] == "PASSED"
    assert envelope["execution"]["run_id"] == 99
    assert envelope["provenance"]["campaign_commit"] == "campaign-sha"


def test_existing_correlated_run_is_reused_without_duplicate_dispatch():
    existing = [{
        "id": 99,
        "status": "completed",
        "conclusion": "success",
        "head_sha": "executor-sha",
        "display_title": "CORR",
        "head_branch": "feature",
    }]
    client = FakeClient(existing=existing)
    envelope = execute_dispatch_request(
        client,
        request(),
        campaign_id="NEXO-NOOP-001",
        campaign_commit="campaign-sha",
        validator_commit="validator-sha",
    )
    assert client.dispatch_calls == []
    assert envelope["validation"]["status"] == "PASSED"


def test_scientific_gate_failure_is_not_technical_failure():
    client = FakeClient(diagnostics={"passed": False, "score": 0.0})
    envelope = execute_dispatch_request(
        client,
        request(),
        campaign_id="NEXO-NOOP-001",
        campaign_commit="campaign-sha",
        validator_commit="validator-sha",
    )
    assert envelope["validation"]["status"] == "NOT_PROMOTED"
    assert envelope["execution"]["conclusion"] == "success"
