from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from uuid import uuid4

from .mutations import apply_mutation_request
from . import scientific_integrity as integrity
from .tower_paths import entity_path

RUNNABLE_TEST_STATES = {"READY", "RUNNING", "CHECKPOINTED", "QUEUED"}
EXECUTOR_WORK_STATES = {"READY", "RUNNING", "CHECKPOINTED"}


def canonical_test_state(test: dict[str, Any]) -> str:
    return str(test.get("status") or test.get("state") or test.get("operational_status") or "").upper()


def scheduler_work_id(test_id: str) -> str:
    return f"WORK::{test_id}"


def _complete_frozen_test(contract: Any) -> bool:
    return isinstance(contract, dict) and all(
        bool(contract.get(key)) for key in ("id", "method", "decision_rule", "outputs", "claim_boundary")
    )


def frozen_contract_from_test(test: dict[str, Any]) -> dict[str, Any] | None:
    # Preserve the current canonical definition verbatim. A legacy method plus
    # decision_rule is descriptive metadata, not readiness or an input binding.
    if all(test.get(key) for key in integrity.FROZEN[:-1]):
        return {"id": str(test.get("id") or test.get("test_id") or ""),
                **{key: test.get(key) for key in integrity.FROZEN},
                "decision_rule": {"success": test["success_criteria"], "kill": test["kill_criteria"]},
                "outputs": test.get("outputs") or ["scientific_result"]}
    frozen = test.get("frozen_test")
    if _complete_frozen_test(frozen):
        return dict(frozen)

    test_id = str(test.get("id") or test.get("test_id") or "")
    if not test_id:
        return None

    method = test.get("method")
    if not method:
        method_parts = {
            key: test[key]
            for key in ("mechanism", "input_contract", "estimator_contract", "null_contract")
            if test.get(key) not in (None, "", {}, [])
        }
        method = method_parts or None

    decision_rule = test.get("decision_rule") or test.get("decision_contract")
    outputs = test.get("outputs")
    if not outputs and "scientific_result" in test:
        outputs = ["scientific_result"]
    claim_boundary = test.get("claim_boundary")

    candidate = {
        "id": test_id,
        "method": method,
        "decision_rule": decision_rule,
        "outputs": outputs,
        "claim_boundary": claim_boundary,
    }
    return candidate if _complete_frozen_test(candidate) else None


def scheduler_work_projection(test: dict[str, Any], *, repair: bool) -> dict[str, Any] | None:
    state = canonical_test_state(test)
    if state not in RUNNABLE_TEST_STATES:
        return None
    test_id = str(test.get("id") or test.get("test_id") or "")
    contract = frozen_contract_from_test(test)
    if not test_id or contract is None:
        return None

    work_state = "READY" if state == "QUEUED" else state
    if work_state not in EXECUTOR_WORK_STATES:
        return None
    work_id = scheduler_work_id(test_id)
    return {
        "id": work_id,
        "kind": "ACTION",
        "domain": str(test.get("domain") or "SCIENCE").upper(),
        "owner_role": "EXECUTOR",
        "priority": str(test.get("priority") or "NORMAL").upper(),
        "status": work_state,
        "operational_status": work_state,
        "test_id": test_id,
        "campaign_id": test.get("campaign_id"),
        "test_group_id": test.get("test_group_id"),
        "parent_id": test_id,
        "project_id": test.get("project_id"),
        "hypothesis_id": test.get("hypothesis_id"),
        "capability_id": test.get("capability_id"),
        "frozen_test": contract,
        "source_test_ref": f"entities/test/{test_id}.json",
        "scheduler_visibility_repair": bool(repair),
        "execution_policy": str(test.get("execution_policy") or "AUTO").upper(),
    }


def ensure_scheduler_visibility(root: str | Path, test: dict[str, Any], *, writer_role: str = "EXECUTOR") -> dict[str, Any]:
    root = Path(root)
    test_id = str(test.get("id") or test.get("test_id") or "")
    work_id = scheduler_work_id(test_id) if test_id else ""
    if not test_id:
        return {"visible": False, "reason": "TEST_ID_MISSING"}

    work_path = entity_path(root, "work", work_id)
    existing = json.loads(work_path.read_text(encoding="utf-8")) if work_path.exists() else None
    check = integrity.readiness(root, test)
    if not check["eligible"]:
        # Only withdraw our own unreserved projection. Never steal ownership or
        # interrupt an admitted execution merely because it is already active.
        if (existing and existing.get("test_id") == test_id and existing.get("owner_role") == "EXECUTOR"
                and existing.get("scheduler_visibility_repair")
                and existing.get("status") in {"READY", "CHECKPOINTED"}
                and "ACTIVE_ATTEMPT" not in check["reasons"]):
            receipt = apply_mutation_request(root, {
                "request_id": f"VISIBILITY-WAIT-{uuid4().hex[:16]}", "entity_kind": "work",
                "entity_name": work_id, "expected_version": int(existing.get("entity_version", 1)),
                "changes": {"status": "WAIT_DEPENDENCY", "operational_status": "WAIT_DEPENDENCY",
                            "scheduler_visibility_blocker": check["reasons"]},
                "writer_role": writer_role, "event_type": "SCHEDULER_VISIBILITY_WITHDRAWN"})
            if not receipt.get("accepted") or receipt.get("readback") != "PASS":
                return {"visible": False, "outcome": "MUTATION_FAILED", "work_id": work_id, "receipt": receipt}
        return {"visible": False, "outcome": "EXECUTION_PREREQUISITES_MISSING",
                "work_id": work_id, "blocker_class": "EXECUTION_PREREQUISITES_MISSING",
                "readiness": check, "recovery_work_id": test.get("recovery_work_id")}
    projection = scheduler_work_projection(test, repair=True)
    if projection is None:
        return {"visible": False, "outcome": "TEST_NOT_RUNNABLE", "work_id": work_id,
                "blocker_class": "TEST_NOT_RUNNABLE", "readiness": check}
    if existing:
        payload = existing
        if (payload.get("test_id") == test_id and payload.get("owner_role") == "EXECUTOR"
                and str(payload.get("status") or "").upper() in EXECUTOR_WORK_STATES
                and payload.get("frozen_test") == projection["frozen_test"]):
            return {"visible": True, "outcome": "REUSED", "work_id": work_id, "work": payload}
        if (payload.get("test_id") == test_id and payload.get("owner_role") == "EXECUTOR"
                and payload.get("scheduler_visibility_repair") and payload.get("status") == "WAIT_DEPENDENCY"
                and payload.get("scheduler_visibility_blocker")):
            changes = {k: v for k, v in projection.items() if k != "id"}
            changes["scheduler_visibility_blocker"] = None
            receipt = apply_mutation_request(root, {
                "request_id": f"VISIBILITY-RESUME-{uuid4().hex[:16]}", "entity_kind": "work",
                "entity_name": work_id, "expected_version": int(payload.get("entity_version", 1)),
                "changes": changes, "writer_role": writer_role, "event_type": "SCHEDULER_VISIBILITY_RESTORED"})
            if receipt.get("accepted") and receipt.get("readback") == "PASS":
                return {"visible": True, "outcome": "RESTORED", "work_id": work_id,
                        "work": json.loads(work_path.read_text(encoding="utf-8")), "receipt": receipt}
            return {"visible": False, "outcome": "MUTATION_FAILED", "work_id": work_id, "receipt": receipt}
        return {"visible": False, "outcome": "EXISTING_WORK_NOT_RUNNABLE", "work_id": work_id,
                "blocker_class": "SCHEDULER_WORK_RECONCILIATION_REQUIRED"}

    receipt = apply_mutation_request(root, {
        "request_id": f"VISIBILITY-{uuid4().hex[:16]}",
        "entity_kind": "work",
        "entity_name": work_id,
        "expected_version": 0,
        "changes": projection,
        "writer_role": writer_role,
        "event_type": "SCHEDULER_VISIBILITY_REPAIRED",
    })
    if not receipt.get("accepted") or receipt.get("readback") != "PASS":
        return {
            "visible": False,
            "outcome": "MUTATION_FAILED",
            "work_id": work_id,
            "receipt": receipt,
        }
    payload = json.loads(work_path.read_text(encoding="utf-8"))
    return {"visible": True, "outcome": "CREATED", "work_id": work_id, "work": payload, "receipt": receipt}


def repair_orphan_runnable_tests(root: str | Path) -> dict[str, int]:
    root = Path(root)
    test_dir = root / "entities" / "test"
    if not test_dir.exists():
        return {"runnable_tests": 0, "repaired": 0, "already_visible": 0, "scientific_definition_missing": 0}

    counts = {"runnable_tests": 0, "repaired": 0, "already_visible": 0, "scientific_definition_missing": 0}
    for path in sorted(test_dir.glob("*.json")):
        try:
            test = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(test, dict) or canonical_test_state(test) not in RUNNABLE_TEST_STATES:
            continue
        counts["runnable_tests"] += 1
        outcome = ensure_scheduler_visibility(root, test)
        if outcome.get("outcome") == "CREATED":
            counts["repaired"] += 1
        elif outcome.get("visible"):
            counts["already_visible"] += 1
        elif outcome.get("blocker_class") == "SCIENTIFIC_DEFINITION_MISSING":
            counts["scientific_definition_missing"] += 1
    return counts
