from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

from runtime.nexo_execution.peer_detection_battery import evaluate_battery

OUTPUT_PATH = Path("peer_detection_battery_result.json")


def _bound_path() -> str:
    for key in ("NEXO_BINDING_RESULTS_BUNDLE_PATH", "NEXO_BINDING_INPUT_PATH", "NEXO_PARAM_RESULTS_BUNDLE_PATH", "NEXO_PARAM_INPUT_PATH"):
        value = os.environ.get(key, "").strip()
        if value:
            return value
    return ""


def _read_bundle(raw: str) -> tuple[dict[str, Any], dict[str, Any]]:
    if not raw:
        return {"gates": {}}, {"source": "unbound"}
    path = Path(raw).expanduser().resolve()
    if not path.is_file():
        raise ValueError(f"PEER battery evidence bundle not found: {raw}")
    data = path.read_bytes()
    value = json.loads(data.decode("utf-8"))
    if not isinstance(value, dict):
        raise ValueError("PEER battery evidence bundle must be a JSON object")
    return value, {"source": "path", "path": str(path), "sha256": hashlib.sha256(data).hexdigest()}


def main() -> None:
    bundle, binding = _read_bundle(_bound_path())
    result = evaluate_battery(bundle)
    result["binding_provenance"] = binding
    OUTPUT_PATH.write_text(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
