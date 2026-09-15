from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import json
import re
import unicodedata


_EXECUTION_PREFIXES = (
    "teste ",
    "testar ",
    "rode ",
    "rodar ",
    "execute ",
    "executar ",
    "faca o teste ",
)
_EXECUTION_SUBJECT_RE = re.compile(
    r"^\s*(?:teste|testar|rode|rodar|execute|executar|fa[cç]a\s+o\s+teste)\s+(.+?)\s*$",
    flags=re.IGNORECASE,
)
_CLAUSE_SPLIT_RE = re.compile(
    r"(?:[;\n]+|,\s*(?=(?:teste|testar|rode|rodar|execute|executar|fa[cç]a\s+o\s+teste)\b))",
    flags=re.IGNORECASE,
)
_TERMINAL_STATUSES = {"VERIFIED", "DONE", "FAILED", "INCONCLUSIVE", "SUPERSEDED"}
_ACTIVE_STATUSES = {"READY", "QUEUED", "DISPATCHED", "RUNNING", "CHECKPOINTED", "RESULT_AVAILABLE", "VERIFYING"}


def _fold(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    no_marks = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return " ".join(no_marks.casefold().split())


def is_execution_utterance(text: str) -> bool:
    folded = _fold(text).strip()
    return any(folded.startswith(prefix) for prefix in _EXECUTION_PREFIXES)


def parse_execution_clauses(text: str) -> list[str]:
    clauses = [part.strip() for part in _CLAUSE_SPLIT_RE.split(text) if part.strip()]
    return [clause for clause in clauses if is_execution_utterance(clause)]


def execution_subject(clause: str) -> str:
    match = _EXECUTION_SUBJECT_RE.match(clause)
    if not match:
        raise ValueError("clause is not an explicit execution command")
    subject = " ".join(match.group(1).split())
    if not subject:
        raise ValueError("execution command has no scientific subject")
    return subject


def _canon_scalar(value: str | None) -> str | None:
    if value is None:
        return None
    return _fold(value)


def _canon_seq(values: tuple[str, ...]) -> list[str]:
    return sorted({_fold(value) for value in values if value and value.strip()})


@dataclass(frozen=True)
class ScientificTestSpec:
    question: str
    datasets: tuple[str, ...] = ()
    rival: str | None = None
    null: str | None = None
    method: str | None = None
    decision_rule: str | None = None
    model_constraints: tuple[str, ...] = ()
    test_group_id: str | None = None
    claim_boundary: str | None = None
    execution_capability: str | None = None


@dataclass(frozen=True)
class ExistingTestRef:
    test_id: str
    fingerprint: str
    status: str
    result_ref: str | None = None


@dataclass(frozen=True)
class CapabilityRef:
    capability_id: str
    task_id: str
    repository: str
    source_revision: str
    runtime_requirement: str
    required_outputs: tuple[str, ...]
    supported_methods: tuple[str, ...] = ()


class IntakeDisposition(str, Enum):
    DUPLICATE_TERMINAL = "DUPLICATE_TERMINAL"
    ATTACH_EXISTING = "ATTACH_EXISTING"
    READY = "READY"
    CAPABILITY_GAP = "CAPABILITY_GAP"


@dataclass(frozen=True)
class ScientificIntakePlan:
    spec: ScientificTestSpec
    fingerprint: str
    disposition: IntakeDisposition
    test_id: str
    correlation_id: str
    capability: CapabilityRef | None = None
    existing: ExistingTestRef | None = None


def scientific_fingerprint(spec: ScientificTestSpec) -> str:
    payload = {
        "question": _canon_scalar(spec.question),
        "datasets": _canon_seq(spec.datasets),
        "rival": _canon_scalar(spec.rival),
        "null": _canon_scalar(spec.null),
        "method": _canon_scalar(spec.method),
        "decision_rule": _canon_scalar(spec.decision_rule),
        "model_constraints": _canon_seq(spec.model_constraints),
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def _identity_from_fingerprint(fingerprint: str) -> tuple[str, str]:
    digest = fingerprint.split(":", 1)[1]
    test_id = f"T-CHAT-{digest[:12].upper()}"
    correlation_id = f"CORR-{digest[:16].upper()}"
    return test_id, correlation_id


def _resolve_capability(spec: ScientificTestSpec, capabilities: list[CapabilityRef]) -> CapabilityRef | None:
    if spec.execution_capability:
        target = _fold(spec.execution_capability)
        for capability in capabilities:
            if _fold(capability.capability_id) == target:
                return capability
        return None
    if spec.method:
        method = _fold(spec.method)
        for capability in capabilities:
            if method in {_fold(item) for item in capability.supported_methods}:
                return capability
    return None


def plan_scientific_test(
    spec: ScientificTestSpec,
    existing_tests: list[ExistingTestRef],
    capabilities: list[CapabilityRef],
) -> ScientificIntakePlan:
    fingerprint = scientific_fingerprint(spec)
    for existing in existing_tests:
        if existing.fingerprint != fingerprint:
            continue
        status = existing.status.upper()
        if status in _TERMINAL_STATUSES:
            return ScientificIntakePlan(
                spec=spec,
                fingerprint=fingerprint,
                disposition=IntakeDisposition.DUPLICATE_TERMINAL,
                test_id=existing.test_id,
                correlation_id=f"CORR-{existing.test_id}",
                existing=existing,
            )
        if status in _ACTIVE_STATUSES:
            return ScientificIntakePlan(
                spec=spec,
                fingerprint=fingerprint,
                disposition=IntakeDisposition.ATTACH_EXISTING,
                test_id=existing.test_id,
                correlation_id=f"CORR-{existing.test_id}",
                existing=existing,
            )

    test_id, correlation_id = _identity_from_fingerprint(fingerprint)
    capability = _resolve_capability(spec, capabilities)
    disposition = IntakeDisposition.READY if capability else IntakeDisposition.CAPABILITY_GAP
    return ScientificIntakePlan(
        spec=spec,
        fingerprint=fingerprint,
        disposition=disposition,
        test_id=test_id,
        correlation_id=correlation_id,
        capability=capability,
    )
