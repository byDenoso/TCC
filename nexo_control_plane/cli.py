from __future__ import annotations

import argparse
import json
from pathlib import Path

from .shadow import build_shadow_plan


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="nexo-control-plane")
    sub = parser.add_subparsers(dest="command", required=True)
    shadow = sub.add_parser("shadow", help="Evaluate a JSON snapshot without mutating state")
    shadow.add_argument("snapshot", type=Path)
    args = parser.parse_args(argv)

    if args.command == "shadow":
        snapshot = json.loads(args.snapshot.read_text(encoding="utf-8"))
        print(json.dumps(build_shadow_plan(snapshot), indent=2, sort_keys=True))
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
