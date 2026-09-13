from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from nexo_control.github_api import GitHubActionsClient
from nexo_control.github_runner import execute_dispatch_request, summarize_results
from nexo_control.results import build_result_envelope


def _failure_envelope(
    request: dict[str, Any],
    *,
    campaign_id: str,
    campaign_commit: str,
    validator_commit: str,
    error: Exception,
) -> dict[str, Any]:
    execution = {
        "status": "FAILED",
        "conclusion": "failure",
        "workflow": request["workflow"],
        "run_id": None,
        "head_sha": None,
        "artifact_names": [],
    }
    validation = {
        "status": "FAILED",
        "validator": request["validator"],
        "metrics": {},
        "reasons": [f"ORCHESTRATION_ERROR:{type(error).__name__}"],
    }
    return build_result_envelope(
        campaign_id=campaign_id,
        test_id=request["test_id"],
        execution=execution,
        validation=validation,
        campaign_commit=campaign_commit,
        validator_commit=validator_commit,
    )


def execute_plan_bundle(
    bundle: dict[str, Any],
    client: Any,
    output_dir: Path,
    *,
    validator_commit: str,
) -> dict[str, Any]:
    output_dir = Path(output_dir)
    results_dir = output_dir / "results"
    results_dir.mkdir(parents=True, exist_ok=True)

    results: list[dict[str, Any]] = []
    for request in bundle.get("dispatches", []):
        try:
            envelope = execute_dispatch_request(
                client,
                request,
                campaign_id=bundle["campaign_id"],
                campaign_commit=bundle["campaign_commit"],
                validator_commit=validator_commit,
            )
        except Exception as error:
            envelope = _failure_envelope(
                request,
                campaign_id=bundle["campaign_id"],
                campaign_commit=bundle["campaign_commit"],
                validator_commit=validator_commit,
                error=error,
            )
        path = results_dir / f"{request['test_id']}.json"
        path.write_text(json.dumps(envelope, indent=2, allow_nan=False) + "\n", encoding="utf-8")
        results.append(envelope)

    summary = summarize_results(bundle["campaign_id"], results)
    summary.update(
        {
            "dry_run": bool(bundle.get("dry_run")),
            "campaign_commit": bundle.get("campaign_commit"),
            "attempt": bundle.get("attempt"),
            "predicted_dispatch_count": len(bundle.get("predicted_dispatches", [])),
            "executed_dispatch_count": len(bundle.get("dispatches", [])),
        }
    )
    (output_dir / "campaign-summary.json").write_text(
        json.dumps(summary, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return summary


def main() -> int:
    plan_path = Path(os.environ.get("NEXO_PLAN_PATH", "nexo-runtime/dispatch-plan.json"))
    output_dir = Path(os.environ.get("NEXO_OUTPUT_DIR", "nexo-runtime"))
    bundle = json.loads(plan_path.read_text(encoding="utf-8"))
    if bundle.get("dry_run"):
        output_dir.mkdir(parents=True, exist_ok=True)
        summary = summarize_results(bundle["campaign_id"], [])
        summary.update(
            {
                "dry_run": True,
                "campaign_commit": bundle.get("campaign_commit"),
                "attempt": bundle.get("attempt"),
                "predicted_dispatch_count": len(bundle.get("predicted_dispatches", [])),
                "executed_dispatch_count": 0,
            }
        )
        (output_dir / "campaign-summary.json").write_text(
            json.dumps(summary, indent=2, allow_nan=False) + "\n",
            encoding="utf-8",
        )
        print(json.dumps(summary, sort_keys=True))
        return 0

    token = os.environ.get("GITHUB_TOKEN")
    repository = os.environ.get("GITHUB_REPOSITORY")
    validator_commit = os.environ.get("GITHUB_SHA", "unknown")
    if not token or not repository:
        raise RuntimeError("GITHUB_TOKEN and GITHUB_REPOSITORY are required for execution")
    client = GitHubActionsClient(token, repository)
    summary = execute_plan_bundle(bundle, client, output_dir, validator_commit=validator_commit)
    print(json.dumps(summary, sort_keys=True))
    return 0 if summary["ready_for_learning"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
