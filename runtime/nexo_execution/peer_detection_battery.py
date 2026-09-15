from __future__ import annotations

from typing import Any, Mapping

from .peer_detection import EXECUTION_ORDER, evaluate_gate, load_gate_registry, policy_digest


def evaluate_battery(bundle: Mapping[str, Any]) -> dict[str, Any]:
    gates = bundle.get("gates")
    if not isinstance(gates, Mapping):
        gates = {}
    registry = load_gate_registry()
    results: dict[str, dict[str, Any]] = {}
    skipped: set[str] = set()
    stop_reason: str | None = None

    for gate_id in EXECUTION_ORDER:
        if gate_id == "D25":
            result = evaluate_gate("D25", {"results": results})
            results[gate_id] = result
            continue

        if gate_id in skipped:
            results[gate_id] = {
                "schema": "peer.detection.gate-result.v1",
                "battery_id": "PEER_DETECTION_V1",
                "gate_id": gate_id,
                "gate_status": "SKIPPED_BY_POLICY",
                "metrics": {"stop_reason": stop_reason},
                "classification_hint": None,
                "reason_codes": ["SKIPPED_AFTER_D09_ANCHOR_CONDITIONED_STOP"],
                "input_digest": None,
                "policy_digest": policy_digest(),
                "nexo_verification": {
                    "status": "PASS",
                    "decision": "VERIFIED",
                    "reason_code": "GATE_SKIPPED_BY_POLICY",
                    "scope": "SCIENTIFIC",
                },
            }
            continue

        evidence = None if gate_id == "D00" else gates.get(gate_id)
        result = evaluate_gate(gate_id, evidence if isinstance(evidence, Mapping) else None)
        results[gate_id] = result

        if gate_id == "D09" and result.get("classification_hint") == "ANCHOR_CONDITIONED_SIGNAL":
            for rule in registry.get("stop_rules", []):
                if rule.get("after_gate") == "D09" and rule.get("when_classification_hint") == "ANCHOR_CONDITIONED_SIGNAL":
                    skipped.update(str(item) for item in rule.get("skip", []))
                    stop_reason = "D09_ANCHOR_CONDITIONED_SIGNAL"

    d25 = results["D25"]
    classification = str(d25.get("classification_hint") or "INCONCLUSIVE")
    decision = "INCONCLUSIVE" if classification == "INCONCLUSIVE" else "VERIFIED"
    return {
        "schema": "peer.detection.battery-result.v1",
        "battery_id": "PEER_DETECTION_V1",
        "classification": classification,
        "policy_digest": policy_digest(),
        "execution_order": list(EXECUTION_ORDER),
        "stop_reason": stop_reason,
        "results": results,
        "nexo_verification": {
            "status": "PASS",
            "decision": decision,
            "reason_code": f"PEER_DETECTION_{classification}",
            "scope": "SCIENTIFIC",
        },
    }
