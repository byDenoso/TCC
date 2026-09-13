from __future__ import annotations

import json
import os
from pathlib import Path

from nexo_control.contracts import load_campaign
from nexo_control.dispatch import build_dispatches

ROOT = Path(__file__).resolve().parents[1]
CAMPAIGN_ROOT = (ROOT / ".nexo" / "campaigns").resolve()


def resolve_campaign_path(raw: str) -> Path:
    candidate = Path(raw)
    if not candidate.is_absolute():
        candidate = ROOT / candidate
    candidate = candidate.resolve()
    if candidate.parent != CAMPAIGN_ROOT:
        raise ValueError("campaign path must be a direct file under .nexo/campaigns")
    if candidate.suffix not in {".yaml", ".yml"}:
        raise ValueError("campaign path must be YAML")
    return candidate


def main() -> int:
    campaign_path = resolve_campaign_path(os.environ.get("NEXO_CAMPAIGN_PATH", ".nexo/campaigns/example-noop.yaml"))
    dry_run = os.environ.get("NEXO_DRY_RUN", "true").lower() == "true"
    attempt = int(os.environ.get("NEXO_ATTEMPT", "1"))
    sha = os.environ.get("GITHUB_SHA", "local00000000")
    output = Path(os.environ.get("NEXO_PLAN_OUTPUT", "nexo-runtime/dispatch-plan.json"))

    campaign = load_campaign(campaign_path)
    bundle = build_dispatches(campaign, sha=sha, attempt=attempt, dry_run=dry_run)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(bundle, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({
        "campaign_id": bundle["campaign_id"],
        "dry_run": bundle["dry_run"],
        "runnable": len(bundle["predicted_dispatches"]),
        "output": str(output),
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
