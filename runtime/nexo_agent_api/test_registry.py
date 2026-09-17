from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from .mutations import apply_mutation_request
from .scheduler_visibility import ensure_scheduler_visibility, scheduler_work_id
from .service import TowerAgentIssue


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _read_entity(root: Path, kind: str, entity_id: str) -> dict | None:
    path = root / "entities" / kind / f"{entity_id}.json"
    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else None


def _create_or_reuse(root: Path, *, kind: str, entity_id: str, changes: dict, writer_role: str, event_type: str) -> dict:
    existing = _read_entity(root, kind, entity_id)
    if existing is not None:
        return {
            "accepted": True,
            "readback": "PASS",
            "outcome": "REUSED",
            "entity_kind": kind,
            "entity_name": entity_id,
            "entity_version": int(existing.get("entity_version", 1)),
        }
    receipt = apply_mutation_request(root, {
        "request_id": f"REG-{kind.upper()}-{uuid4().hex[:16]}",
        "entity_kind": kind,
        "entity_name": entity_id,
        "expected_version": 0,
        "changes": {"id": entity_id, **changes},
        "writer_role": writer_role,
        "event_type": event_type,
    })
    if not receipt.get("accepted") or receipt.get("readback") != "PASS":
        issue = receipt.get("issue") if isinstance(receipt.get("issue"), dict) else {}
        raise TowerAgentIssue(
            str(issue.get("code") or "TEST_REGISTRY_MUTATION_FAILED"),
            str(issue.get("message") or f"Could not create {kind} {entity_id}."),
            issue.get("details") if isinstance(issue.get("details"), dict) else {},
        )
    return receipt


def _next_run_id(root: Path, test_id: str) -> str:
    run_dir = root / "entities" / "run"
    highest = 0
    if run_dir.exists():
        for path in run_dir.glob("*.json"):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if not isinstance(payload, dict) or str(payload.get("test_id")) != test_id:
                continue
            run_id = str(payload.get("id") or path.stem)
            try:
                highest = max(highest, int(run_id.rsplit("::", 1)[-1]))
            except ValueError:
                continue
    return f"RUN::{test_id}::{highest + 1:04d}"


def register_test(
    root: str | Path,
    *,
    test_id: str,
    domain: str,
    title: str,
    objective: str,
    campaign_id: str,
    campaign_title: str | None = None,
    test_group_id: str | None = None,
    test_group_title: str | None = None,
    parent_id: str | None = None,
    project_id: str | None = None,
    hypothesis_id: str | None = None,
    work_id: str | None = None,
    capability_id: str | None = None,
    frozen_test: dict | None = None,
    writer_role: str = "ADVISOR",
    correlation_id: str | None = None,
    provenance: dict | None = None,
) -> dict:
    """Canonicalize a graph-visible TEST and its RUN before dispatch.

    A complete frozen_test contract also creates the scheduler-visible WORK projection.
    Legacy callers without a frozen contract remain registrable, but cannot acquire the
    scheduler-visibility invariant until their scientific execution contract is complete.
    CHECKs must not call this function unless they are explicitly promoted to TEST.
    """
    root = Path(root)
    clean_domain = " ".join(str(domain).strip().split()).upper()
    clean_title = " ".join(str(title).strip().split())
    clean_objective = " ".join(str(objective).strip().split())
    if not all((str(test_id).strip(), clean_domain, clean_title, clean_objective, str(campaign_id).strip())):
        raise TowerAgentIssue("TEST_REGISTRY_INVALID", "Canonical TEST registration is missing required identity fields.")

    corr = " ".join(str(correlation_id or f"TESTREG-{uuid4().hex}").strip().split())
    observed_at = _now()
    base_provenance = {
        "ingress": "register_test",
        "correlation_id": corr,
        "registered_at": observed_at,
        **(provenance or {}),
    }

    campaign_parent = project_id or hypothesis_id or work_id or parent_id
    receipts: list[dict] = []
    receipts.append(_create_or_reuse(
        root,
        kind="campaign",
        entity_id=campaign_id,
        changes={
            "domain": clean_domain,
            "project_id": project_id,
            "hypothesis_id": hypothesis_id,
            "work_id": work_id,
            "parent_id": campaign_parent,
            "label": campaign_title or campaign_id,
            "title": campaign_title or campaign_id,
            "status": "ACTIVE",
            "operational_status": "ACTIVE",
            "analytical_status": "UNASSESSED",
            "created_at": observed_at,
            "updated_at": observed_at,
            "provenance": base_provenance,
        },
        writer_role=writer_role,
        event_type="CAMPAIGN_REGISTERED",
    ))

    if test_group_id:
        receipts.append(_create_or_reuse(
            root,
            kind="test_group",
            entity_id=test_group_id,
            changes={
                "domain": clean_domain,
                "campaign_id": campaign_id,
                "project_id": project_id,
                "parent_id": campaign_id,
                "label": test_group_title or test_group_id,
                "title": test_group_title or test_group_id,
                "group_kind": "TEST_GROUP",
                "status": "ACTIVE",
                "operational_status": "ACTIVE",
                "analytical_status": "UNASSESSED",
                "created_at": observed_at,
                "updated_at": observed_at,
                "provenance": base_provenance,
            },
            writer_role=writer_role,
            event_type="TEST_GROUP_REGISTERED",
        ))

    run_id = _next_run_id(root, test_id)
    test_parent = test_group_id or campaign_id
    test_existing = _read_entity(root, "test", test_id)
    existing_runs = [str(value) for value in (test_existing or {}).get("run_ids", []) if str(value)]
    run_ids = [*existing_runs, run_id]
    test_changes = {
        "domain": clean_domain,
        "project_id": project_id,
        "hypothesis_id": hypothesis_id,
        "work_id": work_id,
        "campaign_id": campaign_id,
        "test_group_id": test_group_id,
        "parent_id": test_parent,
        "label": clean_title,
        "title": clean_title,
        "objective": clean_objective,
        "capability_id": capability_id,
        "status": "QUEUED",
        "operational_status": "QUEUED",
        "analytical_status": str((test_existing or {}).get("analytical_status") or "UNASSESSED"),
        "current_run_id": run_id,
        "run_ids": run_ids,
        "updated_at": observed_at,
        "created_at": str((test_existing or {}).get("created_at") or observed_at),
        "provenance": base_provenance,
    }
    if frozen_test is not None:
        test_changes["frozen_test"] = frozen_test

    if test_existing is None:
        receipts.append(_create_or_reuse(
            root,
            kind="test",
            entity_id=test_id,
            changes=test_changes,
            writer_role=writer_role,
            event_type="TEST_REGISTERED",
        ))
    else:
        receipt = apply_mutation_request(root, {
            "request_id": f"REG-TEST-RUN-{uuid4().hex[:16]}",
            "entity_kind": "test",
            "entity_name": test_id,
            "expected_version": int(test_existing.get("entity_version", 1)),
            "changes": test_changes,
            "writer_role": writer_role,
            "event_type": "TEST_RUN_QUEUED",
        })
        if not receipt.get("accepted") or receipt.get("readback") != "PASS":
            raise TowerAgentIssue("TEST_REGISTRY_MUTATION_FAILED", "Could not attach canonical RUN to TEST.", {"test_id": test_id})
        receipts.append(receipt)

    receipts.append(_create_or_reuse(
        root,
        kind="run",
        entity_id=run_id,
        changes={
            "domain": clean_domain,
            "project_id": project_id,
            "hypothesis_id": hypothesis_id,
            "work_id": work_id,
            "campaign_id": campaign_id,
            "test_group_id": test_group_id,
            "test_id": test_id,
            "parent_id": test_id,
            "capability_id": capability_id,
            "status": "QUEUED",
            "operational_status": "QUEUED",
            "analytical_status": "UNASSESSED",
            "correlation_id": corr,
            "created_at": observed_at,
            "updated_at": observed_at,
            "provenance": base_provenance,
        },
        writer_role=writer_role,
        event_type="RUN_REGISTERED",
    ))

    scheduler_visibility = None
    scheduler_id = None
    if frozen_test is not None:
        test_after_registration = _read_entity(root, "test", test_id)
        if test_after_registration is None:
            raise TowerAgentIssue("READBACK_FAILED", "TEST vanished before scheduler visibility admission.")
        scheduler_visibility = ensure_scheduler_visibility(root, test_after_registration, writer_role=writer_role)
        scheduler_id = scheduler_visibility.get("work_id") or scheduler_work_id(test_id)
        if not scheduler_visibility.get("visible"):
            raise TowerAgentIssue(
                str(scheduler_visibility.get("blocker_class") or "SCHEDULER_VISIBILITY_FAILED"),
                "Dispatch-ready TEST could not be made scheduler-visible.",
                {"test_id": test_id, "visibility": scheduler_visibility},
            )

    required = [
        ("campaign", campaign_id),
        ("test", test_id),
        ("run", run_id),
    ]
    if test_group_id:
        required.append(("test_group", test_group_id))
    if scheduler_id:
        required.append(("work", scheduler_id))
    if any(_read_entity(root, kind, entity_id) is None for kind, entity_id in required):
        raise TowerAgentIssue("READBACK_FAILED", "Universal TEST registration did not survive canonical readback.")

    return {
        "registered": True,
        "dispatch_ready": True,
        "scheduler_visible": bool(scheduler_visibility and scheduler_visibility.get("visible")) if frozen_test is not None else False,
        "work_id": scheduler_id,
        "domain": clean_domain,
        "project_id": project_id,
        "campaign_id": campaign_id,
        "test_group_id": test_group_id,
        "test_id": test_id,
        "run_id": run_id,
        "correlation_id": corr,
        "operational_status": "QUEUED",
        "analytical_status": "UNASSESSED",
        "receipts": receipts,
        "scheduler_visibility": scheduler_visibility,
        "readback": "PASS",
    }
