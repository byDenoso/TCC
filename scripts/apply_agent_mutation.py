from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from runtime.nexo_agent_api.mutations import apply_mutation_request


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True)
    parser.add_argument("--request", required=True)
    parser.add_argument("--receipt", required=True)
    args = parser.parse_args()

    request_path = Path(args.request)
    receipt_path = Path(args.receipt)
    if receipt_path.exists():
        print(receipt_path.read_text(encoding="utf-8"))
        return 0

    payload = json.loads(request_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("request root must be an object")
    receipt = apply_mutation_request(Path(args.root), payload)
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(receipt, ensure_ascii=False, sort_keys=True)
    receipt_path.write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
