from __future__ import annotations

import io
import json
import time
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path
from typing import Any, Callable


Transport = Callable[[str, str, Any, bool], Any]


class GitHubActionsClient:
    def __init__(
        self,
        token: str,
        repository: str,
        *,
        transport: Transport | None = None,
        sleep_fn: Callable[[float], None] = time.sleep,
        poll_seconds: float = 2.0,
        max_polls: int = 150,
    ) -> None:
        if "/" not in repository:
            raise ValueError("repository must be owner/name")
        self.token = token
        self.repository = repository
        self.sleep_fn = sleep_fn
        self.poll_seconds = poll_seconds
        self.max_polls = max_polls
        self.transport = transport or self._http_transport

    def _http_transport(self, method: str, path: str, payload: Any = None, binary: bool = False) -> Any:
        url = "https://api.github.com" + path
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(url, data=body, method=method)
        request.add_header("Authorization", f"Bearer {self.token}")
        request.add_header("Accept", "application/vnd.github+json")
        request.add_header("X-GitHub-Api-Version", "2022-11-28")
        if body is not None:
            request.add_header("Content-Type", "application/json")
        with urllib.request.urlopen(request, timeout=60) as response:
            data = response.read()
        if binary:
            return data
        if not data:
            return None
        return json.loads(data.decode("utf-8"))

    def _workflow_name(self, workflow: str) -> str:
        return urllib.parse.quote(Path(workflow).name, safe="")

    def dispatch_workflow(self, workflow: str, ref: str, inputs: dict[str, Any]) -> None:
        name = self._workflow_name(workflow)
        path = f"/repos/{self.repository}/actions/workflows/{name}/dispatches"
        self.transport("POST", path, {"ref": ref, "inputs": inputs}, False)

    def find_correlated_runs(self, workflow: str, correlation_id: str, ref: str) -> list[dict[str, Any]]:
        name = self._workflow_name(workflow)
        query = urllib.parse.urlencode({"event": "workflow_dispatch", "branch": ref, "per_page": 50})
        path = f"/repos/{self.repository}/actions/workflows/{name}/runs?{query}"
        payload = self.transport("GET", path, None, False) or {}
        runs = payload.get("workflow_runs", [])
        return [
            run for run in runs
            if run.get("display_title") == correlation_id and run.get("head_branch") == ref
        ]

    def wait_for_correlated_run(self, workflow: str, correlation_id: str, ref: str) -> dict[str, Any]:
        for _ in range(self.max_polls):
            matches = self.find_correlated_runs(workflow, correlation_id, ref)
            if len(matches) == 1:
                return matches[0]
            if len(matches) > 1:
                raise ValueError("multiple matching runs for correlation ID")
            self.sleep_fn(self.poll_seconds)
        raise TimeoutError("timed out waiting for correlated workflow run")

    def get_run(self, run_id: int) -> dict[str, Any]:
        path = f"/repos/{self.repository}/actions/runs/{int(run_id)}"
        payload = self.transport("GET", path, None, False)
        if not isinstance(payload, dict):
            raise ValueError("invalid workflow run response")
        return payload

    def wait_for_run_completion(self, run_id: int) -> dict[str, Any]:
        for _ in range(self.max_polls):
            run = self.get_run(run_id)
            if run.get("status") == "completed":
                return run
            self.sleep_fn(self.poll_seconds)
        raise TimeoutError("timed out waiting for workflow completion")

    def list_artifacts(self, run_id: int) -> list[dict[str, Any]]:
        path = f"/repos/{self.repository}/actions/runs/{int(run_id)}/artifacts?per_page=100"
        payload = self.transport("GET", path, None, False) or {}
        artifacts = payload.get("artifacts", [])
        if not isinstance(artifacts, list):
            raise ValueError("invalid artifact list response")
        return artifacts

    def download_json_artifact(self, artifact_id: int, filename: str) -> dict[str, Any]:
        path = f"/repos/{self.repository}/actions/artifacts/{int(artifact_id)}/zip"
        data = self.transport("GET", path, None, True)
        if not isinstance(data, (bytes, bytearray)):
            raise ValueError("invalid artifact archive response")
        with zipfile.ZipFile(io.BytesIO(bytes(data))) as archive:
            names = archive.namelist()
            matches = [name for name in names if Path(name).name == filename]
            if len(matches) != 1:
                raise ValueError(f"artifact must contain exactly one {filename}")
            payload = json.loads(archive.read(matches[0]).decode("utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("artifact JSON must be an object")
        return payload
