from __future__ import annotations

from dataclasses import dataclass
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


def _fold(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    no_marks = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return " ".join(no_marks.casefold().split())


def is_execution_utterance(text: str) -> bool:
    folded = _fold(text).strip()
    return any(folded.startswith(prefix) for prefix in _EXECUTION_PREFIXES)


def parse_execution_clauses(text: str) -> list[str]:
    clauses = [part.strip() for part in re.split(r"[;\n]+", text) if part.strip()]
    return [clause for clause in clauses if is_execution_utterance(clause)]


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
