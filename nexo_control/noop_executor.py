from __future__ import annotations

import argparse
import json
from pathlib import Path


def write_result(correlation_id: str, campaign_id: str, test_id: str, should_pass: bool, run_id: int, head_sha: str, output: Path) -> dict:
    payload = {
        "schema_version": 1,
        "correlation_id": correlation_id,
        "campaign_id": campaign_id,
        "test_id": test_id,
        "passed": bool(should_pass),
        "run_id": int(run_id),
        "head_sha": head_sha,
    }
    output.write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--correlation-id", required=True)
    parser.add_argument("--campaign-id", required=True)
    parser.add_argument("--test-id", required=True)
    parser.add_argument("--should-pass", required=True, choices=["true", "false"])
    parser.add_argument("--run-id", required=True, type=int)
    parser.add_argument("--head-sha", required=True)
    parser.add_argument("--output", default="executor-result.json", type=Path)
    args = parser.parse_args()
    payload = write_result(
        args.correlation_id,
        args.campaign_id,
        args.test_id,
        args.should_pass == "true",
        args.run_id,
        args.head_sha,
        args.output,
    )
    print(json.dumps(payload, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
