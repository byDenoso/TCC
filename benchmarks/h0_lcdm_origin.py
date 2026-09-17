from __future__ import annotations

import json
import os
from pathlib import Path

_ALLOWED = {f"T-H0LCDM26-{i:03d}" for i in range(1, 16)}


def main() -> int:
    test_id = str(os.getenv("NEXO_PARAM_TEST_ID") or os.getenv("NEXO_TEST_ID") or "").strip()
    output = Path(str(os.getenv("NEXO_PARAM_RESULT_PATH") or "h0_lcdm_origin_result.json"))
    if test_id not in _ALLOWED:
        output.write_text(json.dumps({"status": "NOT_EXECUTED", "reason": "test_id_not_allowlisted", "test_id": test_id}, indent=2), encoding="utf-8")
        return 2
    # This entrypoint is deliberately fail-closed until the selected TEST has
    # immutable input artifacts/capabilities bound by its ExecutionContract.
    # It must never manufacture scientific inputs or promote setup to evidence.
    output.write_text(json.dumps({
        "schema": "nexo.h0-lcdm-origin-result.v1",
        "test_id": test_id,
        "status": "READY_FOR_BOUND_INPUT_EXECUTION",
        "scientific_result": None,
        "claim_boundary": "NO_CAMPAIGN_CLAIM_BEFORE_T-H0LCDM26-015",
    }, indent=2, sort_keys=True), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
