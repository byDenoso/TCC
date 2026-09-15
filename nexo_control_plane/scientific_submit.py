from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .scientific_intake import IntakeDisposition, ScientificIntakePlan


@dataclass(frozen=True)
class SubmitReceipt:
    test_id: str
    state: str
    correlation_id: str
    canonical_readback: bool
    dispatch_ref: str | None = None
    retryable: bool = False
    result_ref: str | None = None
    error: str | None = None


def _label(question: str) -> str:
    compact = " ".join(question.split())
    return compact if len(compact) <= 120 else compact[:117] + "..."


def build_test_entity(plan: ScientificIntakePlan) -> dict[str, Any]:
    capability_id = plan.capability.capability_id if plan.capability else plan.spec.execution_capability
    entity = {
        "id": plan.test_id,
        "kind": "TEST",
        "label": _label(plan.spec.question),
        "question": plan.spec.question,
        "status": "READY",
        "test_group_id": plan.spec.test_group_id or "TEST_GROUP::ADHOC::CHAT-SCIENCE",
        "writer_role": "EXECUTOR",
        "entity_version": 1,
        "scientific_fingerprint": plan.fingerprint,
        "claim_boundary": plan.spec.claim_boundary
        or "User-directed scientific test; intake does not promote a scientific claim.",
        "decision_rule": plan.spec.decision_rule
        or "Interpret only under the frozen test contract; no automatic claim promotion.",
        "provenance_refs": ["CHAT_SCIENTIFIC_INTAKE_V1"],
        "execution_capability": capability_id,
        "correlation_id": plan.correlation_id,
    }
    if plan.disposition == IntakeDisposition.CAPABILITY_GAP:
        entity["execution_state"] = "CAPABILITY_GAP"
    return entity


def build_dispatch_request(plan: ScientificIntakePlan) -> dict[str, Any]:
    if plan.disposition != IntakeDisposition.READY or plan.capability is None:
        raise ValueError("only READY plans with a resolved capability are dispatchable")
    capability = plan.capability
    parameters = {
        "question": plan.spec.question,
        "scientific_fingerprint": plan.fingerprint,
        "datasets": list(plan.spec.datasets),
        "rival": plan.spec.rival,
        "null": plan.spec.null,
        "method": plan.spec.method,
        "decision_rule": plan.spec.decision_rule,
        "model_constraints": list(plan.spec.model_constraints),
        "claim_boundary": plan.spec.claim_boundary,
    }
    return {
        "work_id": f"WORK::{plan.test_id}",
        "correlation_id": plan.correlation_id,
        "domain": "SCIENCE",
        "adapter": "execution",
        "source_revision": capability.source_revision,
        "attempt": 1,
        "args": {
            "runtime_requirement": capability.runtime_requirement,
            "task_id": capability.task_id,
            "repository": capability.repository,
            "required_outputs": list(capability.required_outputs),
            "parameters": parameters,
            "test_id": plan.test_id,
            "execute": True,
        },
    }


def _verify_ready_readback(plan: ScientificIntakePlan, entity: dict[str, Any]) -> None:
    if entity.get("id") != plan.test_id:
        raise ValueError("Tower readback test id mismatch")
    if entity.get("scientific_fingerprint") != plan.fingerprint:
        raise ValueError("Tower readback scientific fingerprint mismatch")
    if entity.get("status") != "READY":
        raise ValueError("Tower readback is not READY")


class ScientificSubmitService:
    def __init__(self, tower_gateway: Any, dispatch_gateway: Any):
        self._tower = tower_gateway
        self._dispatch = dispatch_gateway

    def submit(self, plan: ScientificIntakePlan) -> SubmitReceipt:
        if plan.disposition == IntakeDisposition.DUPLICATE_TERMINAL:
            return SubmitReceipt(
                test_id=plan.test_id,
                state=plan.disposition.value,
                correlation_id=plan.correlation_id,
                canonical_readback=True,
                result_ref=plan.existing.result_ref if plan.existing else None,
            )
        if plan.disposition == IntakeDisposition.ATTACH_EXISTING:
            return SubmitReceipt(
                test_id=plan.test_id,
                state=plan.disposition.value,
                correlation_id=plan.correlation_id,
                canonical_readback=True,
            )

        entity = build_test_entity(plan)
        self._tower.persist_test(entity)
        readback = self._tower.readback_test(plan.test_id)
        _verify_ready_readback(plan, readback)

        if plan.disposition == IntakeDisposition.CAPABILITY_GAP:
            return SubmitReceipt(
                test_id=plan.test_id,
                state=plan.disposition.value,
                correlation_id=plan.correlation_id,
                canonical_readback=True,
            )

        request = build_dispatch_request(plan)
        try:
            dispatch_ref = self._dispatch.submit(request)
        except Exception as exc:
            return SubmitReceipt(
                test_id=plan.test_id,
                state="READY",
                correlation_id=plan.correlation_id,
                canonical_readback=True,
                retryable=True,
                error=f"{type(exc).__name__}: {exc}",
            )

        self._tower.mark_dispatched(plan.test_id, dispatch_ref, plan.correlation_id)
        dispatched = self._tower.readback_test(plan.test_id)
        if dispatched.get("id") != plan.test_id or dispatched.get("status") != "DISPATCHED":
            raise ValueError("Tower dispatch readback mismatch")
        return SubmitReceipt(
            test_id=plan.test_id,
            state="DISPATCHED",
            correlation_id=plan.correlation_id,
            canonical_readback=True,
            dispatch_ref=dispatch_ref,
        )
