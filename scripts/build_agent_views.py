from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from runtime.nexo_agent_api import materialize_role_views
from runtime.nexo_agent_api.telemetry import enrich_materialized_state


def _stage_derived_state(root: Path) -> str:
    root = root.resolve()
    repo_root = root.parent
    if not (repo_root / ".git").exists():
        return "SKIPPED_NOT_GIT_WORKTREE"

    relative_root = root.relative_to(repo_root)
    paths = [
        str(relative_root / "indexes" / "active-work.json"),
        str(relative_root / "snapshot" / "latest.json"),
        str(relative_root / "snapshot" / "ai-roi.json"),
    ]
    subprocess.run(["git", "add", "--", *paths], cwd=repo_root, check=True)
    return "STAGED"


def main() -> int:
    parser = argparse.ArgumentParser(description="Materialize NEXO canonical hot state plus role views and telemetry.")
    parser.add_argument("--root", required=True, help="Path to TOWER_V06 root")
    args = parser.parse_args()
    root = Path(args.root)
    result = materialize_role_views(root)
    result["telemetry_enrichment"] = enrich_materialized_state(root)
    result["derived_state_git_stage"] = _stage_derived_state(root)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
