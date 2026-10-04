#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from runtime.nexo_ssot.reconcile import reconcile_exports


def main() -> int:
    parser = argparse.ArgumentParser(description="Reconcile Drive SSOT and GitHub TOWER exports.")
    parser.add_argument("--drive-export", required=True)
    parser.add_argument("--tower-export", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    drive = json.loads(Path(args.drive_export).read_text(encoding="utf-8"))
    tower = json.loads(Path(args.tower_export).read_text(encoding="utf-8"))
    result = reconcile_exports(drive, tower)
    Path(args.output).write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0 if result["material_conflict_count"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
