from __future__ import annotations

import io
import json
import zipfile

from nexo_control.github_api import GitHubActionsClient


class FakeTransport:
    def __init__(self):
        self.calls = []
        self.responses = []

    def queue(self, value):
        self.responses.append(value)

    def __call__(self, method, path, payload=None, binary=False):
        self.calls.append((method, path, payload, binary))
        return self.responses.pop(0) if self.responses else None


def zipped_json(name: str, payload: dict) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(name, json.dumps(payload))
    return buffer.getvalue()


def test_dispatch_uses_registered_workflow_filename_and_structured_inputs():
    transport = FakeTransport()
    client = GitHubActionsClient("token", "owner/repo", transport=transport)
    client.dispatch_workflow(
        ".github/workflows/nexo-noop-executor.yml",
        "feature",
        {"correlation_id": "CORR", "should_pass": True},
    )
    method, path, payload, binary = transport.calls[0]
    assert method == "POST"
    assert path.endswith("/actions/workflows/nexo-noop-executor.yml/dispatches")
    assert payload == {"ref": "feature", "inputs": {"correlation_id": "CORR", "should_pass": True}}
    assert binary is False


def test_find_correlated_runs_filters_exact_title_and_ref():
    transport = FakeTransport()
    transport.queue({
        "workflow_runs": [
            {"id": 1, "display_title": "OTHER", "head_branch": "feature"},
            {"id": 2, "display_title": "CORR", "head_branch": "feature"},
            {"id": 3, "display_title": "CORR", "head_branch": "other"},
        ]
    })
    client = GitHubActionsClient("token", "owner/repo", transport=transport)
    matches = client.find_correlated_runs(".github/workflows/nexo-noop-executor.yml", "CORR", "feature")
    assert [run["id"] for run in matches] == [2]


def test_download_json_artifact_extracts_exact_file():
    transport = FakeTransport()
    transport.queue(zipped_json("executor-result.json", {"passed": True, "score": 1.0}))
    client = GitHubActionsClient("token", "owner/repo", transport=transport)
    result = client.download_json_artifact(7, "executor-result.json")
    assert result == {"passed": True, "score": 1.0}
    assert transport.calls[0][3] is True
