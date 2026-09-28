"""Deterministic public projection of canonical Tower state.

This is the single generator of the public presentation surface. It lives on the
truth side on purpose: if the presentation repository compiled canonical state
itself, it would own the interpretation of that state, and an interpretation that
lives outside the Tower is how a second truth is born.

Properties this module guarantees:

* **Derived, never authoritative.** It reads canonical state and emits a snapshot
  labelled `projection_only` with `writeback: FORBIDDEN`.
* **Existence comes from entities.** A WORK id present in an index but with no
  `entities/work/<id>.json` never reaches the public surface. Indexes carry
  priority, never existence.
* **Deterministic.** The same canonical input yields the same bytes and the same
  `projection_fingerprint`. Wall-clock time is recorded but excluded from the
  fingerprint, so an unchanged Tower does not produce a churn-only republish.
* **Allowlisted fields.** Every emitted field is explicitly listed. A new field in
  a canonical entity does not leak to the public surface by default.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Iterable
from .live_tower import LIVE_TOWER_FILE_ID
from .semantics import is_private, public_tree, resolve as resolve_semantic, status_group
from .tower_paths import json_file

SCHEMA_VERSION = "1"
PROJECTION_CONTRACT = "NEXO_PUBLIC_PROJECTION_V1"

# Only these fields ever reach the public surface. Anything else in a canonical
# entity stays canonical.
WORK_FIELDS = (
    "id",
    "kind",
    "status",
    "operational_status",
    "priority",
    "domain",
    "target_domain",
    "owner_role",
    "title",
    "campaign_id",
    "test_group_id",
    "blocker_class",
    "dependency_class",
)
TEST_FIELDS = (
    "id",
    "status",
    "state",
    "roadmap_id",
    "domain",
    "target_domain",
    "title",
    "campaign_id",
    "test_group_id",
    "scientific_fingerprint",
    "hypothesis_id",
    "hypothesis_ref",
    "method",
    "methodology",
    "mechanism",
    "dataset",
    "datasets",
    "verdict",
    "scientific_verdict",
    "claim_level",
    "publication_status",
    "review_state",
    "rank_score",
    "origin_kind",
    "prereg_hash",
    "contests_test_id",
    "decoy",
)
TEST_INPUT_FIELDS = ("input_contract", "result", "statistics", "scientific_result")
# Inputs used only to derive a narrow, sanitized entity read model for NEXO ONE.
# They are never copied wholesale to the public projection.
TEST_DETAIL_INPUT_FIELDS = (
    "question",
    "prediction",
    "null",
    "rival",
    "success_criteria",
    "kill_criteria",
    "claim_boundary",
    "limitations",
    "created_at",
    "updated_at",
    "executed_at",
    "frozen_at",
    "prereg_ref",
    "reviews",
    "contests",
    "parent_test_id",
    "depends_on",
    "battery_id",
    "run_ref",
    "execution",
    "reproducibility",
)
TEST_STATISTICS_FIELDS = ("delta_chi2", "delta_bic", "ln_bayes_factor", "sigma_raw", "sigma_lee", "p_value")
TEST_RESULT_FIELDS = ("parameter", "value", "err_lo", "err_hi", "unit")
CAMPAIGN_FIELDS = (
    "roadmap_id",
    "campaign_id",
    "title",
    "domain",
    "subdomain",
    "state",
    "priority",
    "created_at",
    "question",
    "semantic_description",
    "semantic_state",
    "claim_boundary",
)
ATLAS_PROJECTION_FIELDS = (
    "visible",
    "node_type",
    "parent_subdomain",
    "label",
    "show_tests",
    "show_hypothesis_nodes",
    "description_mode",
)
LESSON_FIELDS = (
    "id",
    "status",
    "title",
    "semantic",
    "gap_type",
    "intuition",
    "explanation",
    "exercise",
    "source_signal_count",
    "linked_test_ids",
    "updated_at",
)
CAPABILITY_FIELDS = ("status", "backend", "contract_name")
INTERDOMAIN_FIELDS = (
    "id",
    "status",
    "relation_type",
    "source_domains",
    "target_domains",
    "advisor_disposition",
    "test_ref",
    "test_refs",
    "evidence_refs",
    "lesson_refs",
    "updated_at",
)

# Reproduced from CONTROL.json so the projection can state, in its own manifest,
# under which authority rules it was produced.
CONTROL_FIELDS = (
    "truth_owner",
    "write_model",
    "write_guard",
    "derived_indexes_authority",
    "atlas_role",
    "drive_role",
    "runtime_revision",
)


def _read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def _pick(payload: dict[str, Any], fields: Iterable[str]) -> dict[str, Any]:
    return {field: payload[field] for field in fields if payload.get(field) is not None}


def _canonical_blob(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _fingerprint(payload: Any) -> str:
    return "sha256:" + hashlib.sha256(_canonical_blob(payload).encode("utf-8")).hexdigest()


def _fold_gpt_performance(value: Any) -> Any:
    """GPT performance is NEXO engineering, not its own domain: fold every domain-like field."""
    if isinstance(value, dict):
        return {k: ("ENGINEERING" if k in ("domain", "target_domain", "domain_id") and str(v or "").upper().replace("-", "_")
                    in {"GPT_PERFORMANCE", "GPT_PERF"} else _fold_gpt_performance(v)) for k, v in value.items()}
    if isinstance(value, list):
        return [_fold_gpt_performance(v) for v in value]
    return value


def _apply_target_domain_projection(payload: dict[str, Any]) -> dict[str, Any]:
    """Render target-owned work/tests under the target domain without erasing provenance."""
    projected = dict(payload)
    for key in ("domain", "target_domain"):
        # GPT performance is part of NEXO engineering, not a domain of its own (Dener, 2026-09-25).
        if str(projected.get(key) or "").upper() in {"GPT_PERFORMANCE", "GPT-PERFORMANCE"}:
            projected[key] = "ENGINEERING"
    source_domain = projected.get("domain")
    target_domain = projected.get("target_domain")
    if target_domain and source_domain and target_domain != source_domain:
        projected["method_domain"] = source_domain
        projected["domain"] = target_domain
        projected["domain_projection"] = "TARGET_DOMAIN"
    return projected



def _public_dataset_values(value: Any) -> list[str | int | float]:
    values = value if isinstance(value, list) else [value]
    projected: list[str | int | float] = []
    for item in values:
        candidate: Any = item
        if isinstance(item, dict):
            candidate = next(
                (item.get(key) for key in ("dataset", "dataset_id", "id", "name", "label")
                 if isinstance(item.get(key), (str, int, float)) and not isinstance(item.get(key), bool)),
                None,
            )
        if isinstance(candidate, (str, int, float)) and not isinstance(candidate, bool):
            if not isinstance(candidate, str) or candidate.strip():
                projected.append(candidate.strip() if isinstance(candidate, str) else candidate)
    return list(dict.fromkeys(projected))


def _public_numeric_fields(value: Any, fields: Iterable[str]) -> dict[str, int | float]:
    if not isinstance(value, dict):
        return {}
    return {
        key: value[key]
        for key in fields
        if isinstance(value.get(key), (int, float)) and not isinstance(value.get(key), bool)
    }


_STAT_ALIASES = {
    "p_value": ("p_value", "global_p", "p", "pvalue", "p_global", "gaussian_full_covariance_global_p"),
    "sigma_raw": ("sigma_raw", "sigma", "significance_sigma", "tension_sigma", "n_sigma", "z_sigma"),
    "sigma_lee": ("sigma_lee", "sigma_global", "global_sigma"),
    "delta_chi2": ("delta_chi2", "dchi2", "delta_chisq", "chi2_improvement"),
    "delta_bic": ("delta_bic", "dbic", "bic_difference"),
    "ln_bayes_factor": ("ln_bayes_factor", "lnB", "ln_b", "log_bayes_factor"),
}


def _aliased_statistics(entity: dict[str, Any], result: dict[str, Any]) -> dict[str, float]:
    """Results store statistics under many names (the Learner flagged this as META-RESULT26-001);
    map the common aliases onto the fields the site knows. Numbers only; nothing is computed."""
    pools = [d for d in (entity.get("statistics"), result.get("statistics"), result.get("numbers"), result, entity)
             if isinstance(d, dict)]
    found: dict[str, float] = {}
    for field, names in _STAT_ALIASES.items():
        for pool in pools:
            value = next((pool[n] for n in names if isinstance(pool.get(n), (int, float)) and not isinstance(pool.get(n), bool)), None)
            if value is not None:
                found[field] = value
                break
    return found


def _public_text(value: Any, limit: int = 1200) -> str | None:
    """Return one bounded public string; nested/untyped payloads never pass through."""
    if not isinstance(value, str):
        return None
    text = " ".join(value.split()).strip()
    if not text:
        return None
    if len(text) > limit:
        text = text[: limit - 1].rsplit(" ", 1)[0].rstrip() + "…"
    return text


def _public_text_values(value: Any, *, limit: int = 1200, max_items: int = 16) -> list[str]:
    values = value if isinstance(value, list) else [value]
    output: list[str] = []
    for item in values:
        text = _public_text(item, limit=limit)
        if text and text not in output:
            output.append(text)
        if len(output) >= max_items:
            break
    return output


def _public_timestamp(value: Any) -> str | None:
    text = _public_text(value, limit=64)
    if not text:
        return None
    # Public timestamps must be explicit ISO-like values, not arbitrary text.
    return text if re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}", text) else None


def _public_prediction(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    output: dict[str, Any] = {}
    effect = _public_text(value.get("expected_effect"), limit=800)
    if effect:
        output["expected_effect"] = effect
    probability = value.get("p_promoted")
    if isinstance(probability, (int, float)) and not isinstance(probability, bool):
        output["p_promoted"] = probability
    return output or None


def _public_prereg(entity: dict[str, Any]) -> dict[str, Any] | None:
    """Project only frozen scientific intent needed to compare promise with result."""
    prereg: dict[str, Any] = {}
    prediction = _public_prediction(entity.get("prediction"))
    if prediction:
        prereg["prediction"] = prediction
    for source, target in (("null", "null"), ("rival", "rival")):
        value = _public_text(entity.get(source), limit=1400)
        if value:
            prereg[target] = value

    success = _public_text_values(entity.get("success_criteria"), limit=1200)
    kill = _public_text_values(entity.get("kill_criteria"), limit=1200)
    if success or kill:
        criterion: dict[str, Any] = {}
        if success:
            criterion["success"] = success
        if kill:
            criterion["kill"] = kill
        prereg["criterion"] = criterion

    prereg_hash = _public_text(entity.get("prereg_hash"), limit=160)
    prereg_ref = _public_text(entity.get("prereg_ref"), limit=400)
    if prereg_hash:
        prereg["hash"] = prereg_hash
    if prereg_ref:
        prereg["ref"] = prereg_ref
    at = next(
        (
            stamp
            for stamp in (
                _public_timestamp(entity.get("frozen_at")),
                _public_timestamp(entity.get("created_at")),
            )
            if stamp
        ),
        None,
    )
    if at:
        prereg["at"] = at
    return prereg or None


def _public_reviews(entity: dict[str, Any]) -> list[dict[str, Any]]:
    """Normalize contest/review history without leaking raw evidence or refs."""
    events: list[dict[str, Any]] = []
    axes: dict[str, str] = {}
    for contest in entity.get("contests") or []:
        if not isinstance(contest, dict):
            continue
        contest_id = _public_text(contest.get("contest_test_id"), limit=240)
        axis = _public_text(contest.get("reason"), limit=700)
        if contest_id and axis:
            axes[contest_id] = axis
        event = {
            "kind": "CONTEST",
            "by": _public_text(contest.get("by"), limit=80) or "REFEREE_1",
            "axis": axis,
            "outcome": "PENDING",
            "at": _public_timestamp(contest.get("at")),
            "contest_test_id": contest_id,
        }
        events.append({k: v for k, v in event.items() if v is not None})

    for review in entity.get("reviews") or []:
        if not isinstance(review, dict):
            continue
        contest_id = _public_text(review.get("contest_test_id"), limit=240)
        event = {
            "kind": "VERDICT_REVIEW",
            "by": _public_text(review.get("referee"), limit=80),
            "axis": axes.get(contest_id or ""),
            "outcome": _public_text(review.get("outcome"), limit=80),
            "at": _public_timestamp(review.get("at")),
            "contest_test_id": contest_id,
        }
        events.append({k: v for k, v in event.items() if v is not None})

    return sorted(
        events,
        key=lambda item: (
            str(item.get("at") or ""),
            str(item.get("kind") or ""),
            str(item.get("contest_test_id") or ""),
        ),
    )


def _public_execution(entity: dict[str, Any]) -> dict[str, Any] | None:
    execution: dict[str, Any] = {}
    stamp = _public_timestamp(entity.get("executed_at"))
    if stamp:
        execution["at"] = stamp
    reproducibility = entity.get("reproducibility")
    if not isinstance(reproducibility, dict):
        reproducibility = {}
    for key in ("battery_id", "run_ref", "runner"):
        value = _public_text(entity.get(key), limit=400) or _public_text(reproducibility.get(key), limit=400)
        if value:
            execution[key] = value
    return execution or None


def _public_test_parents(entity: dict[str, Any]) -> list[str]:
    parents: list[str] = []
    for value in (
        entity.get("hypothesis_id"),
        entity.get("hypothesis_ref"),
        entity.get("parent_test_id"),
        entity.get("contests_test_id"),
    ):
        text = _public_text(value, limit=260)
        if text and text not in parents and text != str(entity.get("id") or ""):
            parents.append(text)
    return parents


def _attach_public_test_details(projected: dict[str, Any], entity: dict[str, Any]) -> dict[str, Any]:
    """Add the bounded read model used by entity pages. Call only after privacy classification."""
    projected["entity_kind"] = "TEST"
    question = _public_text(entity.get("question"), limit=1600)
    if question:
        projected["question"] = question
    prereg = _public_prereg(entity)
    if prereg:
        projected["prereg"] = prereg
    reviews = _public_reviews(entity)
    if reviews:
        projected["review"] = reviews
    limitations = _public_text_values(entity.get("limitations"), limit=1200, max_items=20)
    if limitations:
        projected["limitations"] = limitations
    claim_boundary = _public_text(entity.get("claim_boundary"), limit=1600)
    if claim_boundary:
        projected["claim_boundary"] = claim_boundary
    for key in ("created_at", "updated_at", "executed_at"):
        stamp = _public_timestamp(entity.get(key))
        if stamp:
            projected[key] = stamp
    execution = _public_execution(entity)
    if execution:
        projected["execution"] = execution
    parents = _public_test_parents(entity)
    if parents:
        projected["parents"] = parents
    dependencies = [
        item
        for item in (_public_text(value, limit=300) for value in (entity.get("depends_on") or []))
        if item
    ]
    if dependencies:
        projected["depends_on"] = list(dict.fromkeys(dependencies))[:24]
    return projected


def _attach_test_children(tests: list[dict[str, Any]]) -> None:
    """Invert only direct public test lineage; dependency edges remain separate."""
    by_id = {str(test.get("id")): test for test in tests if test.get("id") and not test.get("private")}
    for child in by_id.values():
        child_id = str(child["id"])
        for parent_id in child.get("parents") or []:
            parent = by_id.get(str(parent_id))
            if not parent or parent is child:
                continue
            parent.setdefault("children", [])
            if child_id not in parent["children"]:
                parent["children"].append(child_id)
    for test in by_id.values():
        if test.get("children"):
            test["children"] = sorted(test["children"])


def _public_test_entity(entity: dict[str, Any]) -> dict[str, Any]:
    """Project only the scientific fields consumed by ScienceProjectionV1."""
    projected = _pick(entity, TEST_FIELDS)
    input_contract = entity.get("input_contract")
    dataset_value = projected.get("datasets", projected.get("dataset"))
    if dataset_value is None and isinstance(input_contract, dict):
        dataset_value = input_contract.get("datasets", input_contract.get("dataset"))
    datasets = _public_dataset_values(dataset_value)
    projected.pop("dataset", None)
    if datasets:
        projected["datasets"] = datasets
    else:
        projected.pop("datasets", None)

    scientific_result = entity.get("result")
    if not isinstance(scientific_result, dict):
        scientific_result = entity.get("scientific_result")
    result = {
        key: scientific_result[key]
        for key in TEST_RESULT_FIELDS
        if isinstance(scientific_result, dict)
        and key in scientific_result
        and isinstance(scientific_result[key], (str, int, float))
        and not isinstance(scientific_result[key], bool)
    }
    if result:
        projected["scientific_result"] = result

    statistics = _public_numeric_fields(entity.get("statistics"), TEST_STATISTICS_FIELDS)
    if not statistics and isinstance(scientific_result, dict):
        statistics = _public_numeric_fields(scientific_result.get("statistics"), TEST_STATISTICS_FIELDS)
    if not statistics:
        statistics = _aliased_statistics(entity, scientific_result if isinstance(scientific_result, dict) else {})
    if statistics:
        projected["statistics"] = statistics
    if not projected.get("verdict"):
        # Results store the verdict under several names; the site needs one.
        sr = scientific_result if isinstance(scientific_result, dict) else {}
        verdict = next((v for v in (entity.get("scientific_verdict"), entity.get("decision"), sr.get("verdict"),
                                    sr.get("decision"), sr.get("claim_decision"), (entity.get("semantic") or {}).get("verdict_plain"))
                        if isinstance(v, str) and v.strip()), None)
        if verdict:
            projected["verdict"] = verdict.strip()
    projected = _with_semantics(projected, entity)
    semantic = projected["semantic"]
    if not projected.get("private"):
        projected = _attach_public_test_details(projected, entity)
    if projected.get("private") and projected.get("verdict"):
        # Private verdict codes can embed names (e.g. "..._<NAME>_SENSITIVITY_ONLY"): publish only the class.
        raw = str(projected["verdict"]).upper()
        projected["verdict"] = next((k for k in ("PROMOT", "REJECT", "INCONCLUS", "SUPPORT", "CONTRADICT") if k in raw), "REGISTRADO")
        projected["verdict"] = {"PROMOT": "PROMOTED", "REJECT": "REJECTED", "INCONCLUS": "INCONCLUSIVE",
                                "SUPPORT": "SUPPORTED", "CONTRADICT": "REJECTED"}.get(projected["verdict"], projected["verdict"])
        for key in ("verdict_plain",):
            semantic.pop(key, None)
    if not semantic.get("result_meaning"):
        # Private (Olympus) tests only get the verdict sentence, never their free-text summary.
        source = {} if projected.get("private") else (scientific_result if isinstance(scientific_result, dict) else {})
        derived = _derived_meaning({} if projected.get("private") else entity, source, verdict=projected.get("verdict"))
        if derived:
            # Stopgap until the GPT writes the real plain reading; the site labels it as automatic.
            semantic["result_meaning"] = derived
            semantic["result_meaning_source"] = "DERIVED"
    return projected


_VERDICT_PT = {
    "PROMOT": "Resultado positivo: a hipótese passou nos critérios definidos antes do teste.",
    "SUPPORTED": "Resultado positivo: os dados apoiam a hipótese dentro dos limites do teste.",
    "INCONCLUS": "Inconclusivo: os dados não bastaram para decidir a favor nem contra a hipótese.",
    "REJECT": "Hipótese rejeitada: os dados contrariam o que ela previa.",
    "NULL": "Resultado nulo: nenhum efeito além do esperado pelo modelo padrão.",
    "BLOCKED": "Teste bloqueado antes de chegar a um veredito.",
    "PASS": "Passou na verificação definida antes do teste.",
    "CONSISTENT": "Os dados são consistentes com o modelo padrão; nenhuma anomalia detectada.",
}


def _derived_meaning(entity: dict[str, Any], result: dict[str, Any], verdict: Any = None) -> str | None:
    verdict = str(verdict or result.get("verdict") or entity.get("verdict") or entity.get("scientific_verdict") or "").upper()
    base = next((text for key, text in _VERDICT_PT.items() if key in verdict), None)
    if not base and verdict:
        base = "Veredito técnico registrado: " + verdict.replace("__", " · ").replace("_", " ").lower() + "."
    summary = next((str(v).strip() for v in (result.get("summary"), result.get("resumo"), entity.get("summary"))
                    if isinstance(v, str) and v.strip() and "canonical status" not in v), None)
    if summary and len(summary) > 280:
        summary = summary[:277].rsplit(" ", 1)[0] + "…"
    parts = [p for p in (base, summary) if p]
    return " ".join(parts) or None


# Olympus is personal/client health context: its free text never reaches the
# public surface, only identity, lifecycle and meaning.
_PRIVATE_TEXT_FIELDS = ("title", "intuition", "explanation", "exercise", "mechanism", "method", "methodology", "datasets", "scientific_result", "statistics", "question", "semantic_description")


def _short_public_title(value: Any, limit: int = 104) -> str | None:
    """Compact a canonical plain-language question into a stable public label."""
    if not isinstance(value, str):
        return None
    text = re.sub(r"\\s+", " ", value).strip()
    if not text:
        return None
    if len(text) <= limit:
        return text
    shortened = text[: limit - 1].rsplit(" ", 1)[0].rstrip(" ,;:")
    return (shortened or text[: limit - 1]).rstrip() + "…"


def _private_test_title(entity_id: Any) -> str | None:
    """Safe Olympus label derived only from the technical id, never private free text."""
    raw = str(entity_id or "").upper()
    match = re.match(r"^T-(AVGPROB|OLYCAUSE|OLYPHYS|OLYPIVOT)-(.+)$", raw)
    if not match:
        return None
    prefix, suffix = match.groups()
    family = {
        "AVGPROB": "probabilidade média",
        "OLYCAUSE": "causas",
        "OLYPHYS": "física",
        "OLYPIVOT": "pivô",
    }[prefix]
    return f"Teste Olympus de {family} {suffix}"


def _with_semantics(projected: dict[str, Any], entity: dict[str, Any]) -> dict[str, Any]:
    """Normalise lifecycle and preserve safe canonical human semantics."""
    lifecycle = projected.get("status") or projected.get("state")
    if lifecycle:
        projected["status"] = lifecycle
    projected["status_group"] = status_group(lifecycle)
    semantic = resolve_semantic(entity, entity_id=str(projected.get("id") or projected.get("campaign_id") or ""))
    if is_private(semantic) and str(projected.get("domain") or "").upper() != "OLYMPUS":
        # Legacy Olympus tests were authored with domain=SCIENCE because the
        # statistical method came from science. The canonical semantic taxonomy
        # owns presentation: keep the method provenance and project the target
        # domain as OLYMPUS so lanes and the graph count the same entities.
        source_domain = projected.get("domain")
        projected["target_domain"] = "OLYMPUS"
        if source_domain:
            projected["method_domain"] = source_domain
        projected["domain"] = "OLYMPUS"
        projected["domain_projection"] = "SEMANTIC_TARGET_DOMAIN"
    canonical_semantic = entity.get("semantic") if isinstance(entity.get("semantic"), dict) else {}
    if not is_private(semantic):
        for key in ("display_name", "question_plain", "result_meaning", "why_it_matters", "verdict_plain", "confidence_plain"):
            value = canonical_semantic.get(key)
            if isinstance(value, str) and value.strip():
                semantic[key] = value.strip()
        if not projected.get("title"):
            title = _short_public_title(semantic.get("display_name") or semantic.get("question_plain"))
            if title:
                projected["title"] = title
    projected["semantic"] = semantic
    if is_private(semantic):
        for key in _PRIVATE_TEXT_FIELDS:
            projected.pop(key, None)
        # Private hypothesis links deliberately do not enter the public graph: the
        # canonical relation remains in the Tower but would otherwise dangle after
        # private hypotheses are filtered from hypotheses[].
        projected.pop("hypothesis_id", None)
        projected.pop("hypothesis_ref", None)
        safe_title = _private_test_title(projected.get("id"))
        if safe_title:
            projected["title"] = safe_title
        projected["private"] = True
    return projected

def _load_integrity(root: Path) -> dict[str, Any] | None:
    """Latest Guardião report (INTEGRITY_REPORT, or OPERATOR_INTENT carrying one) for the site's status strip."""
    folder = root / "entities" / "artifact"
    best: tuple[str, dict[str, Any], int] | None = None
    mapped_statuses = {
        "PASS_WITH_PENDING_WRITER": ("writer", False),
        "YELLOW_WRITER_LAG": ("writer", True),
        "PASS_WITH_RECOVERY_GAP": ("recovery", True),
        "PERSISTED_INBOX_PENDING_WRITER": ("inbox", True),
    }
    for path in folder.glob("*.json") if folder.is_dir() else []:
        record = _read_json(path) or {}
        payload = record.get("payload") if isinstance(record.get("payload"), dict) else {}
        raw_status = str(payload.get("status") or payload.get("overall_status") or "").upper()
        if raw_status in {"GREEN", "YELLOW", "RED"}:
            status = raw_status
        elif raw_status in {"PASS", "OK"}:
            status = "GREEN"
        elif raw_status in {"WARN", "WARNING"}:
            status = "YELLOW"
        elif raw_status in {"FAIL", "FAILED", "ERROR"}:
            status = "RED"
        elif raw_status in mapped_statuses:
            status = "YELLOW"
        else:
            continue
        raw_checks = payload.get("checks")
        if isinstance(raw_checks, list):
            checks = [check for check in raw_checks if isinstance(check, dict)]
            checks_total = len(checks)
        elif isinstance(raw_checks, dict) and raw_checks:
            # Current Guardiao reports publish keyed areas with PASS/WARN/FAIL.
            # Keep only area + aggregate boolean so private diagnostics never leak.
            checks = []
            for area, detail in raw_checks.items():
                detail_status = str(detail.get("status") or "").upper() if isinstance(detail, dict) else ""
                if detail_status in {"FAIL", "FAILED", "ERROR", "RED"}:
                    ok = False
                elif detail_status in {"PASS", "OK", "GREEN"}:
                    ok = True
                else:
                    ok = None
                checks.append({"area": str(area), "ok": ok})
            checks_total = len(raw_checks)
        elif (
            str(record.get("kind") or "").upper() == "INTEGRITY_REPORT"
            and str(record.get("source") or "").upper() in {"GUARDIAO", "GUARDIAN"}
        ):
            # A thematic Guardiao integrity report is still a valid pulse. Older
            # rounds did not always repeat the aggregate checks block, so do not
            # freeze guardian.checked_at merely because that optional summary is absent.
            checks = []
            checks_total = 0
        else:
            continue
        mapped = mapped_statuses.get(raw_status)
        if mapped and mapped[1] and not any(c.get("area") == mapped[0] and c.get("ok") is False for c in checks):
            # Named yellow statuses carry their failing area even when the checks block does not.
            checks = checks + [{"area": mapped[0], "ok": False}]
        stamp = str(payload.get("checked_at") or record.get("created_at") or payload.get("date") or "")
        if best is None or stamp > best[0]:
            best = (stamp, {"status": status, "checks": checks}, checks_total)
    if not best:
        return None
    checks = best[1]["checks"]
    failing = [str(c.get("area") or "") for c in checks if c.get("ok") is False]
    return {"status": best[1]["status"], "checked_at": best[0],
            "checks_total": best[2], "checks_failing": len(failing), "failing_areas": failing[:8]}


def _load_evolution(root: Path) -> dict[str, Any] | None:
    """Closed loop for the ATLAS: Dener's gate, charters and stop progress, review ladder, genome, diary, decoys."""
    from .evolution import evolution_status

    try:
        status = evolution_status(root, public=True)
    except Exception:  # the projection never fails because of the evolution layer
        return None
    empty = not (status["charters"] or status["genome"]["genes"] or status["thoughts"]
                     or status.get("signal_clusters") or status.get("incidents"))
    return None if empty else status


def _load_cross_domain(root: Path) -> list[dict[str, Any]]:
    """Project canonical Interdomain relations as derived Learning filaments."""
    index = _read_json(root / "indexes" / "interdomain-active.json", {}) or {}
    entity_root = root / "entities" / "interdomain"
    projected: list[dict[str, Any]] = []
    for item in index.get("items") or []:
        if not isinstance(item, dict):
            continue
        relation_id = item.get("id")
        if not relation_id:
            continue
        entity = _read_json(json_file(entity_root, str(relation_id)), {}) or {}
        source = entity if isinstance(entity, dict) and entity else item
        filament = _pick(source, INTERDOMAIN_FIELDS)
        filament["id"] = str(relation_id)
        filament["projection_label"] = "DERIVED_NOT_EVIDENCE"
        filament["via"] = (
            "LEARNING_INTERDOMAIN" if filament.get("lesson_refs") else "INTERDOMAIN"
        )
        projected.append(filament)
    return projected


def _load_hypotheses(root: Path) -> list[dict[str, Any]]:
    """Public hypotheses for the ATLAS (Ciência > Hipóteses).

    Hypothesis entities are often thin (title/status/domain); the scientific content
    lives in their frozen tests. Missing fields are derived from the linked tests:
    statement <- title/statement, model <- rival, baseline <- null,
    falsification_criterion <- kill criteria. Private (Olympus) hypotheses stay out.
    """
    folder = root / "entities" / "hypothesis"
    if not folder.is_dir():
        return []
    tests_by_hypothesis: dict[str, list[dict[str, Any]]] = {}
    test_folder = root / "entities" / "test"
    if test_folder.is_dir():
        for path in sorted(test_folder.glob("*.json")):
            test = _read_json(path)
            if isinstance(test, dict) and test.get("hypothesis_id"):
                tests_by_hypothesis.setdefault(str(test["hypothesis_id"]), []).append(test)
    first = lambda tests, *keys: next((t[k] for t in tests for k in keys if t.get(k)), None)
    projected: list[dict[str, Any]] = []
    for path in sorted(folder.glob("*.json")):
        entity = _read_json(path)
        if not isinstance(entity, dict):
            continue
        hypothesis_id = str(entity.get("id") or entity.get("hypothesis_id") or path.stem)
        tests = tests_by_hypothesis.get(hypothesis_id, [])
        declared = (entity.get("semantic") or {}).get("domain_id") if isinstance(entity.get("semantic"), dict) else None
        if "OLYMPUS" in {str(entity.get("domain") or "").upper(), str(declared or "").upper()} or hypothesis_id.startswith("HYP-OLY"):
            continue  # Olympus is private: never in the public projection
        test_ids = sorted(str(t.get("id")) for t in tests if t.get("id"))
        roadmap_ids = sorted({str(t.get("roadmap_id")) for t in tests if t.get("roadmap_id")})
        record = {
            "id": hypothesis_id,
            "entity_kind": "HYPOTHESIS",
            "title": entity.get("title"),
            "status": entity.get("status") or entity.get("state"),
            "statement": entity.get("statement") or entity.get("proposition") or entity.get("title"),
            "model": entity.get("model") or first(tests, "rival", "model"),
            "baseline": entity.get("baseline") or first(tests, "null", "baseline_model"),
            "falsification_criterion": entity.get("falsification_criterion") or first(tests, "kill_criteria", "falsification_criterion"),
            "claim_boundary": _public_text(entity.get("claim_boundary"), limit=1600),
            "created_at": _public_timestamp(entity.get("created_at")),
            "updated_at": _public_timestamp(entity.get("updated_at")),
            "test_ids": test_ids,
            "children": test_ids,
            "roadmap_ids": roadmap_ids,
            "parents": roadmap_ids,
        }
        semantic_source = {**entity, "campaign_id": entity.get("campaign_id") or first(tests, "campaign_id"),
                           "roadmap_id": first(tests, "roadmap_id"),
                           "semantic": entity.get("semantic") or first(tests, "semantic") or {}}
        projected_record = _with_semantics({k: v for k, v in record.items() if v not in (None, "", [])}, semantic_source)
        if projected_record.get("private"):
            continue
        projected.append(projected_record)
    return projected


def _load_entities(root: Path, kind: str, fields: Iterable[str]) -> dict[str, dict[str, Any]]:
    folder = root / "entities" / kind
    if not folder.is_dir():
        return {}
    loaded: dict[str, dict[str, Any]] = {}
    for path in sorted(folder.glob("*.json")):
        payload = _read_json(path)
        if not isinstance(payload, dict):
            continue
        entity_id = payload.get("id") or payload.get(f"{kind}_id")
        if not entity_id:
            continue
        loaded[str(entity_id)] = _pick(payload, fields)
    return loaded


def _campaign_source_links(payload: dict[str, Any]) -> list[dict[str, str]]:
    """Return public source links without projecting the full roadmap prior-art payload."""
    links: dict[str, dict[str, str]] = {}

    def add(url: str, label: str | None = None, kind: str = "REFERENCE") -> None:
        normalized = str(url or "").strip()
        if not normalized.startswith(("https://", "http://")):
            return
        links.setdefault(
            normalized,
            {
                "label": str(label or normalized).strip(),
                "url": normalized,
                "kind": kind,
            },
        )

    for item in payload.get("source_links") or []:
        if isinstance(item, str):
            add(item)
        elif isinstance(item, dict):
            add(
                str(item.get("url") or ""),
                str(item.get("label") or item.get("title") or item.get("url") or ""),
                str(item.get("kind") or "REFERENCE").upper(),
            )

    def walk(value: Any) -> None:
        if isinstance(value, dict):
            for nested in value.values():
                walk(nested)
            return
        if isinstance(value, list):
            for nested in value:
                walk(nested)
            return
        if not isinstance(value, str):
            return

        for url in re.findall(r"https?://[^\s\])}>\"']+", value):
            add(url.rstrip(".,;:"), value, "REFERENCE")
        for match in re.finditer(r"\barXiv\s*:\s*(\d{4}\.\d{4,5}(?:v\d+)?)", value, flags=re.IGNORECASE):
            arxiv_id = match.group(1)
            add(f"https://arxiv.org/abs/{arxiv_id}", value, "ARXIV")

    walk(payload.get("prior_art_snapshot"))
    kind_priority = {"OFFICIAL": 0, "PRIMARY": 1, "ARXIV": 2, "REFERENCE": 3}
    return sorted(
        links.values(),
        key=lambda item: (
            kind_priority.get(str(item.get("kind") or "REFERENCE").upper(), 4),
            str(item.get("url") or ""),
        ),
    )


def _load_campaigns(root: Path) -> list[dict[str, Any]]:
    """Project roadmap campaigns as first-class, public, read-only Atlas entities."""
    folder = root / "roadmaps"
    if not folder.is_dir():
        return []

    campaigns: list[dict[str, Any]] = []
    for path in sorted(folder.glob("*.json")):
        payload = _read_json(path)
        if not isinstance(payload, dict):
            continue
        campaign_id = str(payload.get("campaign_id") or "").strip()
        if not campaign_id:
            continue

        record = _pick(payload, CAMPAIGN_FIELDS)
        record["campaign_id"] = campaign_id
        atlas_projection = payload.get("atlas_projection")
        if isinstance(atlas_projection, dict):
            record["atlas_projection"] = _pick(atlas_projection, ATLAS_PROJECTION_FIELDS)
        sources = _campaign_source_links(payload)
        if sources:
            record["source_links"] = sources
        campaigns.append(_with_semantics(record, payload))

    campaigns.sort(key=lambda item: str(item.get("campaign_id") or ""))
    return campaigns


def _public_roadmaps(
    root: Path,
    tests: list[dict[str, Any]],
    hypotheses: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Project every public roadmap as a first-class navigable entity."""
    folder = root / "roadmaps"
    if not folder.is_dir():
        return []

    public_tests = [test for test in tests if not test.get("private")]
    hypothesis_ids = {str(hyp.get("id")) for hyp in hypotheses if hyp.get("id")}
    output: list[dict[str, Any]] = []

    for path in sorted(folder.glob("*.json")):
        payload = _read_json(path)
        if not isinstance(payload, dict):
            continue
        roadmap_id = str(payload.get("roadmap_id") or payload.get("id") or path.stem)
        semantic = resolve_semantic(payload, entity_id=roadmap_id)
        if (
            is_private(semantic)
            or str(payload.get("domain") or "").upper() == "OLYMPUS"
            or roadmap_id.upper().startswith(("RM-OLY", "OLY"))
        ):
            continue

        linked_tests = [
            test for test in public_tests
            if str(test.get("roadmap_id") or "") == roadmap_id
        ]
        test_ids = sorted(str(test["id"]) for test in linked_tests if test.get("id"))
        declared_hypotheses = [
            text
            for text in (
                _public_text(value, limit=260)
                for value in (payload.get("hypothesis_refs") or payload.get("hypothesis_ids") or [])
            )
            if text and text in hypothesis_ids
        ]
        linked_hypotheses = [
            str(test.get("hypothesis_id") or test.get("hypothesis_ref"))
            for test in linked_tests
            if (test.get("hypothesis_id") or test.get("hypothesis_ref"))
            and str(test.get("hypothesis_id") or test.get("hypothesis_ref")) in hypothesis_ids
        ]
        roadmap_hypotheses = sorted(set(declared_hypotheses + linked_hypotheses))
        frontier = [
            text
            for text in (
                _public_text(value, limit=260)
                for value in (payload.get("frontier_refs") or [])
            )
            if text
        ]

        reviews = [str(test.get("review_state") or "").upper() for test in linked_tests]
        statuses = [str(test.get("status") or test.get("state") or "").upper() for test in linked_tests]
        progress = {
            "total": len(linked_tests),
            "confirmed": sum(1 for value in reviews if value == "CONFIRMED"),
            "refuted": sum(1 for value in reviews if value == "REFUTED"),
            "in_review": sum(1 for value in reviews if value in {"PENDING_REVIEW", "CONTESTED", "REFEREE1_PASSED"}),
            "blocked": sum(1 for value in statuses if value.startswith("BLOCKED")),
            "ready": sum(1 for value in statuses if value == "READY"),
            "resumable": sum(1 for value in statuses if value in {"RUNNING", "CHECKPOINTED"}),
            "result": sum(1 for value in statuses if value == "RESULT"),
            "frontier": len(frontier),
        }

        charter = payload.get("charter") if isinstance(payload.get("charter"), dict) else {}
        safe_charter: dict[str, Any] = {}
        charter_status = _public_text(charter.get("status"), limit=80)
        charter_question = _public_text(charter.get("question"), limit=1800)
        objectives = _public_text_values(charter.get("objectives"), limit=1000, max_items=20)
        if charter_status:
            safe_charter["status"] = charter_status
        if charter_question:
            safe_charter["question"] = charter_question
        if objectives:
            safe_charter["objectives"] = objectives
        budget = charter.get("budget") if isinstance(charter.get("budget"), dict) else {}
        safe_budget = {
            key: budget[key]
            for key in ("max_tests", "max_days")
            if isinstance(budget.get(key), (int, float)) and not isinstance(budget.get(key), bool)
        }
        if safe_budget:
            safe_charter["budget"] = safe_budget
        stop = charter.get("stop") if isinstance(charter.get("stop"), dict) else {}
        safe_stop = {
            key: stop[key]
            for key in ("success_confirmed", "kill_consecutive_refuted")
            if isinstance(stop.get(key), (int, float)) and not isinstance(stop.get(key), bool)
        }
        if safe_stop:
            safe_charter["stop"] = safe_stop
        if isinstance(charter.get("renewable"), bool):
            safe_charter["renewable"] = charter["renewable"]
        if isinstance(charter.get("review_every_days"), (int, float)) and not isinstance(charter.get("review_every_days"), bool):
            safe_charter["review_every_days"] = charter["review_every_days"]
        for key in ("chartered_at", "closed_at"):
            stamp = _public_timestamp(charter.get(key))
            if stamp:
                safe_charter[key] = stamp
        close_reason = _public_text(charter.get("close_reason"), limit=160)
        if close_reason:
            safe_charter["close_reason"] = close_reason

        record: dict[str, Any] = {
            "id": roadmap_id,
            "roadmap_id": roadmap_id,
            "entity_kind": "ROADMAP",
            "title": _public_text(payload.get("title"), limit=500),
            "question": _public_text(payload.get("question"), limit=1800) or charter_question,
            "domain": _public_text(payload.get("domain"), limit=120),
            "subdomain": _public_text(payload.get("subdomain"), limit=240),
            "priority": _public_text(payload.get("priority"), limit=80),
            "status": _public_text(payload.get("status") or payload.get("state"), limit=80),
            "state": _public_text(payload.get("state") or payload.get("status"), limit=80),
            "claim_boundary": _public_text(payload.get("claim_boundary"), limit=1800),
            "created_at": _public_timestamp(payload.get("created_at")),
            "campaign_id": _public_text(payload.get("campaign_id"), limit=260),
            "charter": safe_charter or None,
            "test_ids": test_ids,
            "hypothesis_ids": roadmap_hypotheses,
            "frontier_test_ids": list(dict.fromkeys(frontier)),
            "children": roadmap_hypotheses + [test_id for test_id in test_ids if not any(
                test_id in (hyp.get("test_ids") or []) for hyp in hypotheses
            )],
            "progress": progress,
        }
        output.append({key: value for key, value in record.items() if value not in (None, "", [])})

    return output


_EVENT_TIME_RE = re.compile(r"^(\d{8}T\d{6})(\d{0,6})(Z|[+-]\d{4})")


def _event_time(event_id: Any) -> str | None:
    """Normalize the immutable event-id clock to ISO-8601 without using wall time."""
    text = str(event_id or "")
    match = _EVENT_TIME_RE.match(text)
    if not match:
        return None
    base, fraction, zone = match.groups()
    zone_iso = "+00:00" if zone == "Z" else f"{zone[:3]}:{zone[3:]}"
    iso = (
        f"{base[:4]}-{base[4:6]}-{base[6:8]}T"
        f"{base[9:11]}:{base[11:13]}:{base[13:15]}"
        + (f".{fraction.ljust(6, '0')}" if fraction else "")
        + zone_iso
    )
    try:
        from datetime import datetime, timezone
        parsed = datetime.fromisoformat(iso).astimezone(timezone.utc)
    except ValueError:
        return None
    return parsed.isoformat(timespec="microseconds").replace("+00:00", "Z")


def _public_event_role(event_type: str) -> str | None:
    value = event_type.upper()
    if "NEXO_THOUGHT" in value:
        return "PITIA"
    if "HYPOTHESIS" in value or "LESSON" in value:
        return "LEARNER"
    if (
        "CONTEST" in value
        or "REFEREE" in value
        or value in {"RESULT_REFUTED", "RESULT_CONFIRMED", "RESULT_CONTESTED"}
    ):
        return "REFUTADOR"
    if (
        value.startswith("TEST_")
        or value == "ROADMAP_TEST_FROZEN"
        or "DATA_BINDING" in value
        or "BATTERY" in value
    ):
        return "EXECUTOR"
    if (
        "INTEGRITY" in value
        or "FITNESS" in value
        or "DECOY" in value
        or "GENOME_ROLLBACK" in value
        or "ROADMAP_CLOSE" in value
    ):
        return "GUARDIAO"
    if "OPERATOR_INTENT" in value or "CHARTER_APPROVED" in value or "CANONIZE" in value:
        return "DENER"
    return None


def _public_activity(
    root: Path,
    public_entity_ids: set[str],
    *,
    limit: int = 240,
) -> tuple[list[dict[str, Any]], dict[str, str]]:
    """Sanitized closed-loop event stream plus earliest immutable observation per public entity."""
    events_root = root / "events"
    if not events_root.is_dir():
        return [], {}
    activity: list[dict[str, Any]] = []
    first_seen: dict[str, str] = {}
    for path in sorted(events_root.rglob("*.json")):
        event = _read_json(path)
        if not isinstance(event, dict):
            continue
        event_type = str(event.get("event_type") or "")
        role = _public_event_role(event_type)
        stamp = _event_time(event.get("event_id") or path.stem)
        if not stamp:
            continue
        entity_name = _public_text(event.get("entity_name") or event.get("entity_ref"), limit=300)
        is_public_entity = bool(entity_name and entity_name in public_entity_ids)
        if is_public_entity:
            previous = first_seen.get(entity_name)
            if previous is None or stamp < previous:
                first_seen[entity_name] = stamp
        if role is None:
            continue
        # Entity-bearing events are shown only when the target is already in the public read model.
        # System-level audit/thought events may be shown without an entity id.
        if entity_name and not is_public_entity:
            if event_type not in {"INTEGRITY_REPORT_RECORDED", "NEXO_THOUGHT_RECORDED", "NEXO_THOUGHT_NOOP_RECORDED"}:
                continue
            entity_name = None
        item: dict[str, Any] = {
            "event_type": event_type,
            "role": role,
            "at": stamp,
        }
        if entity_name:
            item["entity_id"] = entity_name
            kind = _public_text(event.get("entity_kind"), limit=80)
            if kind:
                item["entity_kind"] = kind.upper()
        activity.append(item)
    activity.sort(key=lambda item: (str(item.get("at") or ""), str(item.get("event_type") or ""), str(item.get("entity_id") or "")))
    return activity[-limit:], first_seen


def _attach_observation_times(entities: list[dict[str, Any]], first_seen: dict[str, str]) -> None:
    for entity in entities:
        entity_id = str(entity.get("id") or entity.get("roadmap_id") or "")
        observed = first_seen.get(entity_id)
        if observed:
            entity["first_observed_at"] = observed
        explicit = _public_timestamp(entity.get("created_at"))
        if explicit:
            entity["created_at_effective"] = explicit
            entity["created_at_source"] = "ENTITY"
        elif observed:
            entity["created_at_effective"] = observed
            entity["created_at_source"] = "EVENT_FIRST_OBSERVED"


def build_public_projection(
    root: str | Path,
    *,
    tower_repository: str = "byDenoso/NEXO-Obsidian-Vault",
    tower_commit: str | None = None,
    tower_revision: str | None = None,
    tower_file_id: str = LIVE_TOWER_FILE_ID,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Compile the public projection from canonical state under `root`.

    `generated_at` is recorded for humans and deliberately excluded from the
    fingerprint: two runs over identical canonical state must agree.
    """
    root = Path(root)
    control = _read_json(root / "CONTROL.json", {}) or {}
    snapshot = _read_json(root / "snapshot" / "latest.json", {}) or {}
    active_index = _read_json(root / "indexes" / "active-work.json", {}) or {}

    work_entities = _load_entities(root, "work", WORK_FIELDS)
    human_flags = _load_entities(root, "work", ("human_action_required",))
    test_entities = _load_entities(root, "test", (*TEST_FIELDS, *TEST_INPUT_FIELDS, *TEST_DETAIL_INPUT_FIELDS))
    campaigns = _load_campaigns(root)

    # Index order is priority. Existence is the entity. An index entry without an
    # entity is reported as dropped, never rendered.
    ordered_ids: list[str] = []
    dropped: list[str] = []
    for item in active_index.get("work") or []:
        if not isinstance(item, dict):
            continue
        work_id = item.get("id") or item.get("work_id")
        if not work_id:
            continue
        work_id = str(work_id)
        if work_id in work_entities:
            if work_id not in ordered_ids:
                ordered_ids.append(work_id)
        else:
            dropped.append(work_id)

    work = [
        _apply_target_domain_projection(dict(work_entities[work_id], id=work_id))
        for work_id in ordered_ids
    ]
    human_work_ids = [
        work_id for work_id in ordered_ids
        if human_flags.get(work_id, {}).get("human_action_required") is True
    ]

    cross_domain = _load_cross_domain(root)
    lessons = [
        _with_semantics(dict(lesson, id=lesson_id), lesson)
        for lesson_id, lesson in sorted(_load_entities(root, "lesson", LESSON_FIELDS).items())
    ]

    tests = [
        _apply_target_domain_projection(_public_test_entity(dict(test_entities[key], id=key)))
        for key in sorted(test_entities)
    ]
    _attach_test_children(tests)
    hypotheses = _load_hypotheses(root)
    roadmaps = _public_roadmaps(root, tests, hypotheses)
    public_entity_ids = {
        str(item.get("id"))
        for item in [*tests, *hypotheses, *roadmaps]
        if item.get("id") and not item.get("private")
    }
    activity, first_seen = _public_activity(root, public_entity_ids)
    _attach_observation_times([item for item in tests if not item.get("private")], first_seen)
    _attach_observation_times(hypotheses, first_seen)
    _attach_observation_times(roadmaps, first_seen)
    integrity = _load_integrity(root)

    capabilities_manifest = _read_json(root / "manifests" / "capabilities.json", {}) or {}
    capabilities = {
        str(capability_id): _pick(definition, CAPABILITY_FIELDS)
        for capability_id, definition in sorted((capabilities_manifest.get("capabilities") or {}).items())
        if isinstance(definition, dict)
    }

    content: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "contract": PROJECTION_CONTRACT,
        "authority_declaration": _pick(control, CONTROL_FIELDS),
        "event_cursor": snapshot.get("event_cursor"),
        "counts": {
            "active_work": len(work),
            "work_entities": len(work_entities),
            "tests": len(test_entities),
            "campaigns": len(campaigns),
            "roadmaps": len(roadmaps),
            "activity": len(activity),
            "cross_domain": len(cross_domain),
            "lessons": len(lessons),
            "hypotheses": len(hypotheses),
            "capabilities": len(capabilities),
            "index_only_dropped": len(dropped),
            "needs_dener": len(human_work_ids),
        },
        "human_gates": {"work_ids": human_work_ids, "count": len(human_work_ids)},
        "work": work,
        "tests": tests,
        "campaigns": campaigns,
        "roadmaps": roadmaps,
        "activity": activity,
        "crossDomain": cross_domain,
        "taxonomy": public_tree(),
        "lessons": lessons,
        "hypotheses": hypotheses,
        "integrity": integrity,
        "evolution": _load_evolution(root),
        "capabilities": capabilities,
        "index_only_dropped": sorted(dropped),
    }
    content = _pseudonymize_private(content, test_entities, campaigns)
    content = _fold_gpt_performance(content)

    manifest = {
        "authority": "TOWER_V06",
        "projection_only": True,
        "writeback": "FORBIDDEN",
        "tower_repository": tower_repository,
        "tower_commit": tower_commit,
        "tower_revision": tower_revision,
        "tower_file_id": tower_file_id,
        "source_storage": "GOOGLE_DRIVE_PRIVATE",
        "source_state_fingerprint": tower_revision,
        # Live Tower builds have no snapshot; the revision identifies the source state
        # (readers such as the ATLAS sync check require a non-empty id).
        "source_snapshot_id": f"LIVE_TOWER@{tower_revision}" if tower_revision else None,
        "event_cursor": snapshot.get("event_cursor"),
        "projection_fingerprint": _fingerprint(content),
        "generated_at": generated_at,
    }
    return {"manifest": manifest, **content}


def projection_bytes(projection: dict[str, Any]) -> bytes:
    """Stable serialization: same projection, same bytes, LF terminated."""
    return (_canonical_blob(projection) + "\n").encode("utf-8")


def verify_projection(projection: dict[str, Any]) -> tuple[bool, str]:
    """Recompute the fingerprint from the content and compare with the manifest."""
    manifest = dict(projection.get("manifest") or {})
    declared = str(manifest.get("projection_fingerprint") or "")
    content = {key: value for key, value in projection.items() if key != "manifest"}
    actual = _fingerprint(content)
    if declared != actual:
        return False, f"declared={declared} actual={actual}"
    if manifest.get("authority") != "TOWER_V06":
        return False, f"authority={manifest.get('authority')!r}"
    if manifest.get("projection_only") is not True:
        return False, "projection_only is not true"
    if manifest.get("writeback") != "FORBIDDEN":
        return False, f"writeback={manifest.get('writeback')!r}"
    if not manifest.get("event_cursor"):
        return False, "event_cursor is missing"
    if not manifest.get("tower_file_id"):
        return False, "tower_file_id is missing"
    if not (manifest.get("tower_revision") or manifest.get("tower_commit")):
        return False, "tower_revision/tower_commit is missing"
    return True, actual


# ── Olympus pseudonyms ─────────────────────────────────────────────────────
# Olympus work is about real people. The public surface shows a short code per
# person (subject_code, e.g. "MIQ"), never a name. Names can hide inside ids
# (CAMP-OLY-<NAME>-...), so every private campaign id is rewritten everywhere.
_OLY_TECH_TOKENS = {"COMPPHYS", "PIVOT", "CROSSCHECK", "CAUSE", "NULLS", "PHYS", "AVGPROB", "BODY", "COMP",
                    "GENETICS", "STRENGTH", "TRAINING", "NUTRITION", "HEALTH", "OLY", "OLYMPUS", "CAMP"}


def _subject_code(campaign_id: str, explicit: Any = None) -> str:
    if isinstance(explicit, str) and explicit.strip():
        return re.sub(r"[^A-Z0-9]", "", explicit.upper())[:4] or "ANON"
    parts = campaign_id.upper().split("-")
    if "OLY" in parts:
        after = parts[parts.index("OLY") + 1:]
        if after and after[0].isalpha() and len(after[0]) >= 3 and after[0] not in _OLY_TECH_TOKENS:
            return after[0][:3]
    return "GRP"


def _pseudonymize_private(content: dict[str, Any], tests: dict[str, dict], campaigns: list[dict]) -> dict[str, Any]:
    private_tests = {t["id"]: t for t in content.get("tests", []) if t.get("private")}
    explicit = {}
    for key, raw in tests.items():
        if key in private_tests and raw.get("campaign_id"):
            explicit.setdefault(str(raw["campaign_id"]), raw.get("subject_code"))
    for campaign in campaigns:
        cid = str(campaign.get("campaign_id") or "")
        if cid.upper().startswith("CAMP-OLY") or is_private(campaign.get("semantic") or {}):
            explicit.setdefault(cid, campaign.get("subject_code"))
    mapping: dict[str, str] = {}
    for cid, code_hint in explicit.items():
        code = _subject_code(cid, code_hint)
        digest = hashlib.sha256(cid.encode("utf-8")).hexdigest()[:4].upper()
        mapping[cid] = f"CAMP-OLY-{code}-{digest}"
    for test in private_tests.values():
        cid = str(test.get("campaign_id") or "")
        test["subject_code"] = mapping.get(cid, "CAMP-OLY-GRP").split("-")[2]
    if not mapping:
        return content
    pattern = re.compile("|".join(re.escape(k) for k in sorted(mapping, key=len, reverse=True)))

    def scrub(value: Any) -> Any:
        if isinstance(value, str):
            return pattern.sub(lambda m: mapping[m.group(0)], value)
        if isinstance(value, list):
            return [scrub(v) for v in value]
        if isinstance(value, dict):
            return {scrub(k): scrub(v) for k, v in value.items()}
        return value

    return scrub(content)

