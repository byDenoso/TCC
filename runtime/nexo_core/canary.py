from __future__ import annotations

from typing import Any

from runtime.nexo_core.guard import apply_transition, make_dedupe_key, verify_readback
from runtime.nexo_core.models import CanonicalEntity, CanonicalEvent
from runtime.nexo_core.projection import build_snapshot, validate_snapshot


def _transition_event(
    *,
    event_id: str,
    correlation_id: str,
    run_id: str,
    state_from: str,
    state_to: str,
) -> CanonicalEvent:
    entity_ref = "WORK::W-V05-CANARY"
    payload = {"state_from": state_from, "state_to": state_to}
    return CanonicalEvent(
        event_id=event_id,
        entity_ref=entity_ref,
        event_type="STATE_TRANSITION",
        correlation_id=correlation_id,
        source_role="Executor",
        state_from=state_from,
        state_to=state_to,
        resource_key=entity_ref,
        dedupe_key=make_dedupe_key(
            role="Executor",
            run_id=run_id,
            entity_ref=entity_ref,
            event_type="STATE_TRANSITION",
            payload=payload,
        ),
        run_id=run_id,
    )


def run_v05_canary(*, generated_at: str) -> dict[str, Any]:
    entity = CanonicalEntity(
        entity_ref="WORK::W-V05-CANARY",
        state="READY",
        entity_version=1,
        writer_role="Executor",
        data={"label": "NEXO Core v0.5 canary", "domain": "NEXO"},
    )
    seen: set[str] = set()
    events: list[CanonicalEvent] = []

    running = _transition_event(
        event_id="EVT-V05-CANARY-1",
        correlation_id="CORR-V05-CANARY",
        run_id="RUN-V05-CANARY",
        state_from="READY",
        state_to="RUNNING",
    )
    first = apply_transition(
        entity,
        running,
        expected_version=1,
        owner_role="Executor",
        seen_dedupe_keys=seen,
    )
    if first.status != "APPLIED":
        return {"status": "FAIL", "stage": "READY_TO_RUNNING", "detail": first.status}
    seen.add(running.dedupe_key)
    events.append(running)

    passed = _transition_event(
        event_id="EVT-V05-CANARY-2",
        correlation_id="CORR-V05-CANARY",
        run_id="RUN-V05-CANARY",
        state_from="RUNNING",
        state_to="PASS",
    )
    second = apply_transition(
        first.entity,
        passed,
        expected_version=2,
        owner_role="Executor",
        seen_dedupe_keys=seen,
    )
    if second.status != "APPLIED":
        return {"status": "FAIL", "stage": "RUNNING_TO_PASS", "detail": second.status}
    seen.add(passed.dedupe_key)
    events.append(passed)

    readback = verify_readback(second.entity, second.entity)
    snapshot = build_snapshot(
        [second.entity],
        snapshot_id="SNAP-V05-CANARY",
        generated_at=generated_at,
        event_cursor=passed.event_id,
    )
    snapshot_errors = validate_snapshot(snapshot)
    status = "PASS" if readback == "PASS" and not snapshot_errors else "FAIL"

    return {
        "status": status,
        "readback": readback,
        "snapshot_errors": snapshot_errors,
        "events": events,
        "snapshot": snapshot,
    }
