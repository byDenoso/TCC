#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from runtime.nexo_ssot.materialize import materialize_view


def main() -> int:
    parser=argparse.ArgumentParser(description="Materialize DENER SSOT static View API.")
    parser.add_argument("--input",required=True)
    parser.add_argument("--output",required=True)
    args=parser.parse_args()
    snapshot=json.loads(Path(args.input).read_text(encoding="utf-8"))
    result=materialize_view(snapshot,args.output)
    print(json.dumps(result,sort_keys=True))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
