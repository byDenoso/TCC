#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, re
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser(); ap.add_argument("--root", type=Path, required=True); ap.add_argument("--exit-code", type=int, required=True)
    args = ap.parse_args()
    stats = list(args.root.rglob("*.stats")) + list(args.root.rglob("*stats*.txt"))
    text = "\n".join(p.read_text(encoding="utf-8", errors="replace") for p in stats)
    vals = []
    for pattern in [r"log\(Z\)\s*=\s*([-+0-9.eE]+)\s*\+/-\s*([-+0-9.eE]+)", r"logZ\s*[:=]\s*([-+0-9.eE]+).*?([-+0-9.eE]+)"]:
        for m in re.finditer(pattern, text, re.S):
            try: vals.append({"logZ": float(m.group(1)), "logZstd": float(m.group(2))})
            except Exception: pass
    completed = args.exit_code == 0 and bool(vals)
    out = {"status": "COMPLETE" if completed else "INCOMPLETE", "exit_code": args.exit_code, "stats_files": [str(p) for p in stats], "evidence": vals[-1] if vals else None}
    (args.root / "nested_status.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps(out, indent=2))
    return 0

if __name__ == "__main__": raise SystemExit(main())
