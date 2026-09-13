from __future__ import annotations

from typing import Any

from nexo_control.results import build_result_envelope
from nexo_control.validators import run_validator


def select_correlated_run(runs: list[dict[str, Any]], correlation_id: str, ref: str) -> dict[str, Any]:
    matches = [
        run
        for run in runs
        if run.get("display_title") == correlation_id and run.get("head_branch") == ref
    ]
    if not matches:
        raise ValueError("zero matching runs for correlation ID")
    if len(matches) > 1:
        raise ValueError("multiple matching runs for correlation ID")
    return matches[0]


def _select_artifact(artifacts: list[dict[str, Any]], expected_name: str) -> dict[str, Any]:
    matches = [artifact for artifact in artifacts if artifact.get("name") == expected_name]
    if not matches:
        raise ValueError(f"required artifact missing: {expected_name}")
    if len(matches) > 1:
        raise ValueError(f"multiple artifacts named: {expected_name}")
    return matches[0]


def execute_dispatch_request(
    client: Any,
    request: dict[str, Any],
    *,
    campaign_id: str,
    campaign_commit: str,
    validator_commit: str,
) -> dict[str, Any]:
    workflow = request["workflow"]
    correlation_id = request["correlation_id"]
    ref = request["ref"]

    existing = client.find_correlated_runs(workflow, correlation_id, ref)
    if len(existing) > 1:
        raise ValueError("multiple matching runs for correlation ID")
    if existing:
        run = select_correlated_run(existing, correlation_id, ref)
    else:
        client.dispatch_workflow(workflow, ref, request["inputs"])
        run = client.wait_for_correlated_run(workflow, correlation_id, ref)

    run = client.wait_for_run_completion(run["id"])
    artifacts = client.list_artifacts(run["id"])
    expected_artifact = f"nexo-executor-result-{correlation_id}"
    artifact = _select_artifact(artifacts, expected_artifact)
    diagnostics = client.download_json_artifact(artifact["id"], "executor-result.json")

    execution = {
        "status": "COMPLETED" if run.get("status") == "completed" else str(run.get("status", "UNKNOWN")).upper(),
        "conclusion": run.get("conclusion"),
        "workflow": workflow,
        "run_id": int(run["id"]),
        "head_sha": run.get("head_sha"),
        "artifact_names": [item.get("name") for item in artifacts if item.get("name")],
    }
    validation = run_validator(request["validator"], execution, diagnostics)
    return build_result_envelope(
        campaign_id=campaign_id,
        test_id=request["test_id"],
        execution=execution,
        validation=validation,
        campaign_commit=campaign_commit,
        validator_commit=validator_commit,
    )


def summarize_results(campaign_id: str, results: list[dict[str, Any]]) -> dict[str, Any]:
    statuses = [result.get("validation", {}).get("status") for result in results]
    ready = bool(results) and all(status in {"PASSED", "NOT_PROMOTED"} for status in statuses)
    return {
        "schema_version": 1,
        "campaign_id": campaign_id,
        "test_count": len(results),
        "statuses": statuses,
        "ready_for_learning": ready,
        "results": [result.get("test_id") for result in results],
    }
