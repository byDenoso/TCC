"""Read-only incident projection onto existing canonical WORK, never a second queue.

Operational verification is deliberately independent of the learning lifecycle.
A completed prerequisite repair cannot prove a runner, independence, temporal,
or scientific-result claim. Private handoff envelopes are never public data.
"""
from __future__ import annotations

from pathlib import Path
from . import execution_recovery as recovery, scientific_integrity as integrity
from .semantics import is_private, resolve

POLICY = "INCIDENT_OPERATIONS_V1"
# These are narrowly scoped diagnostic codes, not the broader materialization
# and scientific failures present in historical incidents.
READINESS_CODES = {"INPUT_PROVENANCE_INCOMPLETE",
                   "RECIPE_BINDING_MISSING", "RECIPE_OR_SMOKE_MISSING", "RECIPE_OR_SMOKE_INVALID"}
CAUSE_OWNER = {"INDEPENDENT_EVALUATORS_UNAVAILABLE": "ADVISOR",
               "RUNNER_ARTIFACT_EXECUTOR_UNAVAILABLE": "ADVISOR",
               "PRE_RESULT_TEMPORAL_ORDER_UNRESOLVED": "LEARNER",
               "EMPTY_FRONTIER_ACTIVE_ROADMAP": "LEARNER",
               "READY_INPUTS_NOT_MATERIALIZED": "EXECUTOR"}


def _public(entity: dict) -> bool:
    return (not entity.get("private") and not is_private(entity.get("semantic") or {})
            and not is_private(resolve(entity, entity_id=str(entity.get("id") or ""))))


def _role(value):
    return value if isinstance(value, str) and value in recovery.ROLES else None


def _accepted(root: Path, work: dict) -> bool:
    """Use the same canonical route/owner checks as ACK, including generation."""
    from . import AgentService
    from .handoff import _latest_by_handoff, _handoff_events, _recovery_context
    from .service import TowerAgentIssue
    rec = work.get("recovery") or {}
    source = rec.get("acceptance_source") or {}
    if rec.get("ownership_state") != "ACCEPTED" or not isinstance(source, dict):
        return False
    event = _latest_by_handoff(root).get(source.get("handoff_id"))
    if not event or event.get("entity_ref") != work.get("id") or event.get("state") not in {"ACK", "DONE", "FAILED", "SUPERSEDED"}:
        return False
    try:
        _, accepted = _recovery_context(AgentService(root), event)
        if accepted is None or accepted != source:
            return False
        # SUPERSEDED may follow PENDING with no recipient acceptance. Require
        # a real ACK receipt, not just a copied source or a terminal event label.
        for ack in _handoff_events(root):
            if (ack.get("handoff_id") == event.get("handoff_id")
                    and ack.get("entity_ref") == work.get("id")
                    and ack.get("state") == "ACK" and ack.get("event_type") == "HANDOFF_ACK"
                    and ack.get("writer_role") == event.get("to_role")
                    and ack.get("acceptance_source") == source):
                _, ack_source = _recovery_context(AgentService(root), ack)
                if ack_source == source:
                    return True
        return False
    except (TowerAgentIssue, ValueError, TypeError, OSError):
        return False


def _validation(root: Path, work: dict, test: dict) -> str:
    rec, evidence = work.get("recovery") or {}, work.get("completion_evidence") or {}
    if work.get("status") != "DONE":
        return "PENDING"
    if not test or rec.get("policy") != recovery.POLICY or not isinstance(evidence, dict):
        return "EVIDENCE_REQUIRED"
    if (evidence.get("kind") != "READINESS_VALIDATED" or evidence.get("test_id") != test.get("id")
            or not test.get("prereg_hash") or evidence.get("prereg_hash") != test.get("prereg_hash")
            or rec.get("fingerprint") != recovery.fingerprint(test)):
        return "EVIDENCE_REQUIRED"
    try:
        check = integrity.readiness(root, test, ignore_reservation=True)
    except (OSError, ValueError, TypeError):
        return "REVALIDATION_REQUIRED"
    # A scientifically terminal TEST is not schedulable, but that fact alone
    # does not invalidate its already verified operational prerequisites.
    prerequisites_ok = (check.get("eligible") is True or check.get("reasons") == ["TERMINAL_TEST"])
    if (not prerequisites_ok or not check.get("recipe_sha256")
            or evidence.get("recipe_sha256") != check["recipe_sha256"]):
        return "REVALIDATION_REQUIRED"
    return "PREREQUISITES_VALIDATED"


def project(root: str | Path, incident: dict, *, public: bool = False) -> dict:
    root = Path(root)
    tests = {t.get("id"): t for t in recovery._entities(root, "test")}
    works = {w.get("id"): w for w in recovery._entities(root, "work")}
    test_ids = set(incident.get("signal_test_ids") or []) | set(incident.get("test_ids") or [])
    hidden = False
    if public:
        visible_tests = {tid for tid in test_ids if tid in tests and _public(tests[tid])}
        hidden = visible_tests != test_ids
        # Protect the TEST->WORK edge too, even when the WORK has no reverse
        # TEST reference. An independent explicit public WORK link is still valid.
        test_ids = visible_tests
    work_ids = set(incident.get("signal_work_ids") or [])
    # Links are exact canonical identities, never topic, owner, or error similarity.
    for tid in test_ids:
        test = tests.get(tid) or {}
        for key in ("recovery_work_id", "work_id", "work_ref", "source_work_id", "parent_work_id"):
            if test.get(key):
                work_ids.add(test[key])
    for wid, work in works.items():
        if ((incident.get("incident_id") and (work.get("incident_id") == incident["incident_id"]
                or incident["incident_id"] in (work.get("linked_incident_ids") or [])))
                or work.get("test_id") in test_ids or work.get("target_test_id") in test_ids
                or (work.get("frozen_test") or {}).get("id") in test_ids):
            work_ids.add(wid)
    unresolved = sorted((test_ids - tests.keys()) | (work_ids - works.keys()))
    items = []
    for wid in sorted(work_ids & works.keys()):
        work = works[wid]
        tid = work.get("test_id") or work.get("target_test_id") or (work.get("frozen_test") or {}).get("id")
        test = tests.get(tid) or {}
        if public and (not _public(work) or (tid and (not test or not _public(test)))):
            hidden = True
            continue
        rec = work.get("recovery") or {}
        managed = rec.get("policy") == recovery.POLICY
        accepted = _accepted(root, work) if managed else False
        items.append({"work_id": wid, "test_id": tid, "current_owner": _role(work.get("owner_role")),
                      "assigned_to": _role(rec.get("target_role")) if managed else None,
                      "ownership_state": "ACCEPTED" if accepted else ("ASSIGNED_UNACCEPTED" if managed else "UNRECORDED"),
                      "accepted": accepted, "validation_state": _validation(root, work, test)})
    code = str(incident.get("signal_code") or "").upper()
    covered = {item["test_id"] for item in items}
    complete = (bool(items) and not hidden and not unresolved and test_ids <= covered
                and code in READINESS_CODES
                and all(item["validation_state"] == "PREREQUISITES_VALIDATED" for item in items))
    state = "RESOLVED" if complete else ("OPEN" if items else "UNLINKED")
    suggested = CAUSE_OWNER.get(code)
    if suggested is None and code in READINESS_CODES:
        suggested = recovery._route([code])[0]
    out = {"policy": POLICY, "state": state, "work_ids": [item["work_id"] for item in items], "items": items,
           "suggested_owner": suggested if not items else None, "reason_code": code if code in CAUSE_OWNER or code in READINESS_CODES else "OTHER",
           "next_action_code": ("RESOLVED" if complete else "LINK_EXISTING_WORK" if not items else
                                "VERIFY_INCIDENT_CRITERION" if all(i["validation_state"] == "PREREQUISITES_VALIDATED" for i in items) else "COMPLETE_RECOVERY"),
           "resolution_scope": "EXECUTION_PREREQUISITES" if complete else None,
           "scientific_effect": "NONE"}
    if not public:
        out["unresolved_refs"] = unresolved
    return out
