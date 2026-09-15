from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any

from .scientific_intake import (
    ExistingTestRef,
    ScientificTestSpec,
    execution_subject,
    parse_execution_clauses,
    plan_scientific_test,
)


_ALLOWED_DEFAULTS = {
    "datasets",
    "rival",
    "null",
    "method",
    "decision_rule",
    "model_constraints",
    "test_group_id",
    "claim_boundary",
    "execution_capability",
}


def _tuple_default(defaults: dict[str, Any], key: str) -> tuple[str, ...]:
    value = defaults.get(key, ())
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    if isinstance(value, (list, tuple)) and all(isinstance(item, str) for item in value):
        return tuple(value)
    raise ValueError(f"{key} must be a string list")


def _spec_from_clause(clause: str, defaults: dict[str, Any]) -> ScientificTestSpec:
    unknown = sorted(set(defaults) - _ALLOWED_DEFAULTS)
    if unknown:
        raise ValueError("unsupported scientific intake defaults: " + ",".join(unknown))
    return ScientificTestSpec(
        question=execution_subject(clause),
        datasets=_tuple_default(defaults, "datasets"),
        rival=defaults.get("rival"),
        null=defaults.get("null"),
        method=defaults.get("method"),
        decision_rule=defaults.get("decision_rule"),
        model_constraints=_tuple_default(defaults, "model_constraints"),
        test_group_id=defaults.get("test_group_id"),
        claim_boundary=defaults.get("claim_boundary"),
        execution_capability=defaults.get("execution_capability"),
    )


def _receipt_mapping(receipt: Any) -> dict[str, Any]:
    if isinstance(receipt, dict):
        return dict(receipt)
    if is_dataclass(receipt):
        return asdict(receipt)
    if hasattr(receipt, "to_dict"):
        mapped = receipt.to_dict()
        if isinstance(mapped, dict):
            return dict(mapped)
    raise TypeError("submitter returned an unsupported receipt type")


class ScientificIntakeApplication:
    def __init__(self, catalog: Any, submitter: Any):
        self._catalog = catalog
        self._submitter = submitter

    def submit_utterance(
        self,
        utterance: str,
        *,
        source: str = "chat",
        defaults: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        del source  # provenance is frozen by the canonical submit gateway for v1
        clauses = parse_execution_clauses(utterance)
        if not clauses:
            raise ValueError("no explicit scientific execution command found")
        defaults = dict(defaults or {})
        existing = list(self._catalog.existing_tests())
        capabilities = list(self._catalog.capabilities())
        results: list[dict[str, Any]] = []

        for clause in clauses:
            spec = _spec_from_clause(clause, defaults)
            plan = plan_scientific_test(spec, existing, capabilities)
            receipt = self._submitter.submit(plan)
            mapped = _receipt_mapping(receipt)
            mapped["fingerprint"] = plan.fingerprint
            results.append(mapped)

            state = str(mapped.get("state", ""))
            if state not in {"DUPLICATE_TERMINAL", "ATTACH_EXISTING"}:
                existing.append(
                    ExistingTestRef(
                        test_id=plan.test_id,
                        fingerprint=plan.fingerprint,
                        status="DISPATCHED" if state == "DISPATCHED" else "READY",
                    )
                )
        return results
