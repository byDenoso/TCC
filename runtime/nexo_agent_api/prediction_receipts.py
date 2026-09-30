"""Writer-owned prospective observation receipts; never reconstruct old dates."""
from __future__ import annotations

import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import scientific_integrity as integrity

CONTRACT = "NEXO_PREDICTION_RECEIPT_V1"


class PredictionReceiptError(ValueError):
    pass


def prediction_hash(test_id: str, prediction: dict) -> str:
    return "sha256:" + integrity.digest({"test_id": test_id, "prediction": prediction})


def prepare_changes(root: Path, current: dict, changes: dict) -> dict:
    """Run inside the same TEST version CAS; caller timestamps are never used."""
    if "prediction_receipt" in changes:
        raise PredictionReceiptError("PREDICTION_RECEIPT_WRITER_OWNED")
    if "prediction" not in changes:
        return changes
    proposed = changes["prediction"]
    previous = current.get("prediction_receipt")
    if previous:
        try:
            proposed_hash = prediction_hash(str(current["id"]), proposed)
            current_hash = prediction_hash(str(current["id"]), current.get("prediction"))
        except (ValueError, TypeError) as exc:
            raise PredictionReceiptError("RECORDED_PREDICTION_IMMUTABLE") from exc
        # Python equates 1, 1.0 and True. They are different committed JSON;
        # equality alone would keep an old receipt while replacing its bytes.
        if proposed_hash != previous.get("prediction_hash") or proposed_hash != current_hash:
            raise PredictionReceiptError("RECORDED_PREDICTION_IMMUTABLE")
        return changes  # exact replay preserves the first observation and hash
    if proposed is None:
        return changes
    if not isinstance(proposed, dict) or not proposed:
        raise PredictionReceiptError("PREDICTION_MUST_BE_NONEMPTY_OBJECT")
    p = proposed.get("p_promoted")
    if p is not None and (isinstance(p, bool) or not isinstance(p, (float, int)) or not 0 <= p <= 1 or not math.isfinite(p)):
        raise PredictionReceiptError("PREDICTION_PROBABILITY_INVALID")
    merged = {**current, **changes}
    states = {str(holder.get(key) or "").upper() for holder in (current, merged)
              for key in ("status", "state", "operational_status", "execution_phase")}
    observed_execution = any(holder.get(key) for holder in (current, merged)
                             for key in ("attempt_id", "battery_id", "run_ref", "started_at", "executed_at"))
    historical_reservation = any(str(spec.get("test_id")) == str(current.get("id"))
                                 for battery in integrity.batteries(root) if isinstance(battery, dict)
                                 for spec in battery.get("tests") or [] if isinstance(spec, dict))
    reserved = (bool(states & (integrity.ACTIVE | integrity.TERMINAL | {"CHECKPOINTED", "EXECUTING", "VERIFY_PENDING"}))
                or observed_execution or historical_reservation)
    late = integrity.terminal(current) or integrity.terminal(merged) or reserved
    try:
        digest = prediction_hash(str(current["id"]), proposed)
    except (ValueError, TypeError) as exc:
        raise PredictionReceiptError("PREDICTION_PAYLOAD_NOT_CANONICAL_JSON") from exc
    receipt = {
        "contract": CONTRACT,
        "prediction_hash": digest,
        "received_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "classification": "AFTER_EXECUTION_OR_RESERVATION" if late else "PROSPECTIVE",
        "source": "WRITER_VERSION_CAS",
        "scope": "CANONICAL_OBSERVATION_NOT_EXTERNAL_PREREGISTRATION_PROOF",
    }
    return {**changes, "prediction_receipt": receipt}


def public_receipt(test_id: str, prediction: Any, receipt: Any, executed_at: Any = None) -> dict | None:
    """Expose the observed time only when its exact prediction still matches."""
    if not isinstance(prediction, dict) or not isinstance(receipt, dict):
        return None
    if (receipt.get("contract") != CONTRACT or receipt.get("source") != "WRITER_VERSION_CAS"
            or receipt.get("classification") != "PROSPECTIVE"):
        return None
    observed = integrity.timestamp(receipt.get("received_at"))
    try:
        matches = receipt.get("prediction_hash") == prediction_hash(test_id, prediction)
    except (ValueError, TypeError):
        return None
    if observed is None or not matches:
        return None
    if executed_at is not None:
        executed = integrity.timestamp(executed_at.get("at") if isinstance(executed_at, dict) else executed_at)
        if executed is None or observed >= executed:
            return None
    return {"recorded_at": observed.isoformat().replace("+00:00", "Z"),
            "receipt_contract": CONTRACT, "prediction_hash": receipt["prediction_hash"]}
