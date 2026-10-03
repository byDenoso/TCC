"""Fixed, bounded recipe for the user-defined engineering control [1,2,3].

No scientific identity, no credentials, no network, no dependency installation.
The recipe implements the requested method; independent review is a deployment
gate, not a claim made by this file's author.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path


def calculate(raw: bytes) -> dict:
    if len(raw) > 2 * 1024 * 1024:
        raise ValueError("INPUT_TOO_LARGE")
    data = json.loads(raw)
    if set(data) != {"contract", "values"} or data["contract"] != "NEXO_DRIVE_OPERATIONAL_CONTROL_V1":
        raise ValueError("INPUT_CONTRACT_INVALID")
    values = data["values"]
    if not isinstance(values, list) or not 0 < len(values) <= 10000:
        raise ValueError("VALUES_INVALID")
    if not all(type(x) in (int, float) and math.isfinite(x) for x in values):
        raise ValueError("VALUES_NONFINITE_OR_NONNUMERIC")
    total = math.fsum(values)
    result = {"count": len(values), "sum": total, "mean": total / len(values)}
    if not math.isfinite(total) or not math.isfinite(result["mean"]):
        raise ValueError("RESULT_NONFINITE")
    return result


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("usage: operational_sum.py INPUT.json OUTPUT.json")
    output = calculate(Path(sys.argv[1]).read_bytes())
    Path(sys.argv[2]).write_text(json.dumps(output, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n")
