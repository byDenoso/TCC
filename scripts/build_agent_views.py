from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from runtime.nexo_agent_api import materialize_role_views


def main() -> int:
    parser = argparse.ArgumentParser(description="Materialize NEXO per-role bootstraps and queues.")
    parser.add_argument("--root", required=True, help="Path to TOWER_V06 root")
    args = parser.parse_args()
    result = materialize_role_views(Path(args.root))
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
