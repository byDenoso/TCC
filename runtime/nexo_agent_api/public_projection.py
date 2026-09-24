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
)
TEST_INPUT_FIELDS = ("input_contract", "result", "statistics", "scientific_result")
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


def _apply_target_domain_projection(payload: dict[str, Any]) -> dict[str, Any]:
    """Render target-owned work/tests under the target domain without erasing provenance."""
    projected = dict(payload)
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


def _with_semantics(projected: dict[str, Any], entity: dict[str, Any]) -> dict[str, Any]:
    """Normalise lifecycle (status vs legacy state) and attach the semantic block."""
    lifecycle = projected.get("status") or projected.get("state")
    if lifecycle:
        projected["status"] = lifecycle
    projected["status_group"] = status_group(lifecycle)
    semantic = resolve_semantic(entity, entity_id=str(projected.get("id") or projected.get("campaign_id") or ""))
    projected["semantic"] = semantic
    if is_private(semantic):
        for key in _PRIVATE_TEXT_FIELDS:
            projected.pop(key, None)
        projected["private"] = True
    return projected

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
        record = {
            "id": hypothesis_id,
            "title": entity.get("title"),
            "status": entity.get("status") or entity.get("state"),
            "statement": entity.get("statement") or entity.get("proposition") or entity.get("title"),
            "model": entity.get("model") or first(tests, "rival", "model"),
            "baseline": entity.get("baseline") or first(tests, "null", "baseline_model"),
            "falsification_criterion": entity.get("falsification_criterion") or first(tests, "kill_criteria", "falsification_criterion"),
            "test_ids": sorted(str(t.get("id")) for t in tests if t.get("id")),
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
    test_entities = _load_entities(root, "test", (*TEST_FIELDS, *TEST_INPUT_FIELDS))
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

    hypotheses = _load_hypotheses(root)

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
            "cross_domain": len(cross_domain),
            "lessons": len(lessons),
            "hypotheses": len(hypotheses),
            "capabilities": len(capabilities),
            "index_only_dropped": len(dropped),
            "needs_dener": len(human_work_ids),
        },
        "human_gates": {"work_ids": human_work_ids, "count": len(human_work_ids)},
        "work": work,
        "tests": [
            _apply_target_domain_projection(_public_test_entity(dict(test_entities[key], id=key)))
            for key in sorted(test_entities)
        ],
        "campaigns": campaigns,
        "crossDomain": cross_domain,
        "taxonomy": public_tree(),
        "lessons": lessons,
        "hypotheses": hypotheses,
        "capabilities": capabilities,
        "index_only_dropped": sorted(dropped),
    }
    content = _pseudonymize_private(content, test_entities, campaigns)

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
