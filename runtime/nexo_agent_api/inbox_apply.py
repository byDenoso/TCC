"""Deterministic ChatGPT inbox -> Tower mutation requests (no LLM in the loop).

ChatGPT does the thinking (runs tests, finds gaps, writes lessons) and drops one
proposal per file in an inbox. This module turns each proposal into the governed
requests the single writer applies, so the whole loop can run in CI.

Every function is pure over a materialized Tower root; nothing here writes.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .tower_paths import entity_path, fs_path

TERMINAL_VERDICTS = {"REJECTED", "FAILED", "FALSIFIED"}


class ProposalError(ValueError):
    """The proposal cannot be applied as-is; it stays in the inbox."""


def _entity(root: Path, kind: str, entity_id: str) -> dict[str, Any] | None:
    path = entity_path(root, kind, entity_id)
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _slug(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "-", value).strip("-").upper()[:60] or "ITEM"


def _first(mapping: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if mapping.get(key) not in (None, "", [], {}):
            return mapping[key]
    return None


def _semantic(existing: dict[str, Any] | None, proposed: dict[str, Any] | None) -> dict[str, Any]:
    merged = dict((existing or {}).get("semantic") or {})
    merged.update({k: v for k, v in (proposed or {}).items() if v not in (None, "")})
    return merged


def _siblings(root: Path, roadmap_id: str | None) -> list[dict[str, Any]]:
    if not roadmap_id:
        return []
    path = fs_path(root, f"roadmaps/{roadmap_id}.json")
    if not path.is_file():
        return []
    refs = json.loads(path.read_text(encoding="utf-8")).get("frontier_refs") or []
    return [e for e in (_entity(root, "test", str(r)) for r in refs) if e]


def _complete_semantic(entity: dict[str, Any], semantic: dict[str, Any], root: Path) -> dict[str, Any]:
    """Guarantee the block the ATLAS renders: valid taxonomy ids + plain-language fields.

    Invalid or missing ids are resolved like the projection does (explicit -> campaign ->
    roadmap -> rules), then from sibling tests of the same roadmap; question_plain falls
    back to the frozen question and verdict_plain to the verdict, so no card is empty.
    """
    from .semantics import UNMAPPED, resolve

    semantic = dict(semantic)
    resolved = resolve({**entity, "semantic": semantic}, entity_id=entity.get("id"))
    if resolved.get("domain_id") == UNMAPPED:
        for sibling in _siblings(root, entity.get("roadmap_id")):
            candidate = resolve(sibling, entity_id=sibling.get("id"))
            if candidate.get("domain_id") != UNMAPPED:
                resolved = {**candidate, "basis": "ROADMAP_SIBLING"}
                break
    for key in ("domain_id", "subdomain_id", "topic_id"):
        if resolved.get(key) and resolved.get(key) != UNMAPPED:
            semantic[key] = resolved[key]
    if not semantic.get("question_plain") and (entity.get("question") or entity.get("scientific_question")):
        semantic["question_plain"] = str(entity.get("question") or entity.get("scientific_question"))
    if not semantic.get("verdict_plain") and entity.get("verdict"):
        semantic["verdict_plain"] = str(entity["verdict"]).replace("_", " ").capitalize()
    return semantic


def _result_request(item: dict[str, Any], body: dict[str, Any], root: Path) -> list[dict[str, Any]]:
    test_id = str(body.get("test_id") or "").strip()
    if not test_id:
        raise ProposalError("MUTATION_PROPOSAL without payload.test_id")
    current = _entity(root, "test", test_id)
    created: list[dict[str, Any]] = []
    if current is None:
        # A result for a test that was never registered (e.g. run straight from a chat): register it, then record.
        created = _hypothesis_requests(item, {**body, "_allow_draft": True, "_status": "RUNNING"}, root)
        current = {"id": test_id, "entity_version": 0}
    result = body.get("result") or {}
    verdict = str(_first(result, "verdict", "veredito") or body.get("verdict") or "").upper() or None
    semantic = _semantic(current, body.get("semantic"))
    if not semantic.get("result_meaning"):
        # Never reject a result for a missing plain reading: write a provisional one; the backfill replaces it.
        summary = _first(result, "summary", "resumo")
        semantic["result_meaning"] = (str(summary) if summary else
                                      f"Veredito registrado: {(verdict or 'sem veredito').lower()}. Leitura simples pendente.")
        semantic["result_meaning_source"] = "WRITER_PROVISIONAL"
    semantic = _complete_semantic({**current, "verdict": verdict}, semantic, root)
    status = ("BLOCKED_INPUT" if verdict and verdict.startswith("BLOCKED")
              else "REJECTED" if verdict in TERMINAL_VERDICTS else "DONE")
    changes = {
        "status": status,
        "state": status,
        "verdict": verdict,
        "decision": _first(result, "decision", "decisao", "decisão") or body.get("decision"),
        "result_summary": _first(result, "summary", "resumo") or semantic.get("result_meaning"),
        "statistics": _first(result, "statistics", "estatísticas", "estatisticas"),
        "limitations": body.get("limitations"),
        "reproducibility": body.get("reproducibility"),
        "executed_by": "CHATGPT_TASK_EXECUTOR",
        "executed_at": item.get("created_at"),
        "inbox_ref": item.get("_inbox_id"),
        "semantic": semantic,
    }
    version = 1 if created else int(current.get("entity_version") or 0)
    return created + [{
        "request_id": f"REQ-INBOX-RESULT-{_slug(str(item.get('_inbox_name') or test_id))}",
        "entity_kind": "test",
        "entity_name": test_id,
        "expected_version": version,
        "writer_role": "EXECUTOR",
        "event_type": "TEST_RESULT_RECORDED",
        "changes": {k: v for k, v in changes.items() if v not in (None, "", [], {})},
    }]


def _infer_roadmap(root: Path, test_id: str, semantic: dict[str, Any]) -> str | None:
    """A test asked for in a chat must not float: attach it to the ACTIVE roadmap of the same area.
    Match on subdomain first, then domain, using the semantic of each roadmap's frontier tests."""
    index = json.loads(fs_path(root, "indexes/active-roadmaps.json").read_text(encoding="utf-8"))         if fs_path(root, "indexes/active-roadmaps.json").is_file() else {"items": []}
    wanted_sub = str(semantic.get("subdomain_id") or ".".join(str(semantic.get("topic_id") or "").split(".")[:3]) or "")
    wanted_dom = str(semantic.get("domain_id") or wanted_sub.split(".")[0] or ("engineering" if test_id.upper().startswith("META-") else ""))
    by_sub, by_dom = None, None
    for item in index.get("items", []):
        if not isinstance(item, dict):
            continue
        rid, state = str(item.get("roadmap_id") or ""), str(item.get("state") or "").upper()
        subs = {str((e.get("semantic") or {}).get("subdomain_id") or "") for e in _siblings(root, rid)}
        doms = {s.split(".")[0] for s in subs if s}
        rank = 0 if state == "ACTIVE" else 1
        if wanted_sub and wanted_sub in subs and (by_sub is None or rank < by_sub[0]):
            by_sub = (rank, rid)
        if wanted_dom and wanted_dom in doms and (by_dom is None or rank < by_dom[0]):
            by_dom = (rank, rid)
    return (by_sub or by_dom or (None, None))[1]


def _roadmap_index(root: Path) -> list[dict[str, Any]]:
    path = fs_path(root, "indexes/active-roadmaps.json")
    return [i for i in (json.loads(path.read_text(encoding="utf-8")).get("items") or []) if isinstance(i, dict)] if path.is_file() else []


def _roadmap_listing(root: Path, test_id: str) -> str | None:
    """The roadmap whose frontier already lists this test (the entity just lacks the field)."""
    for item in _roadmap_index(root):
        rid = str(item.get("roadmap_id") or "")
        doc = fs_path(root, f"roadmaps/{rid}.json")
        if doc.is_file() and test_id in (json.loads(doc.read_text(encoding="utf-8")).get("frontier_refs") or []):
            return rid
    return None


def _roadmap_of_campaign(root: Path, campaign_id: Any) -> str | None:
    return next((str(i["roadmap_id"]) for i in _roadmap_index(root) if campaign_id and i.get("campaign_id") == campaign_id), None)


def _attach_requests(item: dict[str, Any], body: dict[str, Any], root: Path) -> list[dict[str, Any]]:
    """ROADMAP_ATTACH: put existing roadmap-less tests on a roadmap frontier (explicit or inferred)."""
    requests: list[dict[str, Any]] = []
    merged: dict[str, list[str]] = {}
    for entry in body.get("items") or body.get("tests") or []:
        if not isinstance(entry, dict):
            continue
        test_id = str(entry.get("test_id") or entry.get("id") or "")
        current = _entity(root, "test", test_id) if test_id else None
        if current is None:
            continue
        rid = (entry.get("roadmap_id") or current.get("roadmap_id") or _roadmap_listing(root, test_id)
               or _roadmap_of_campaign(root, current.get("campaign_id")) or _infer_roadmap(root, test_id, current.get("semantic") or {}))
        path = fs_path(root, f"roadmaps/{rid}.json") if rid else None
        if not path or not path.is_file():
            continue
        refs = merged.setdefault(rid, list(json.loads(path.read_text(encoding="utf-8")).get("frontier_refs") or []))
        if test_id not in refs:
            refs.append(test_id)
        if current.get("roadmap_id") != rid:
            requests.append({"request_id": f"REQ-INBOX-ATTACH-{_slug(test_id)}", "entity_kind": "test", "entity_name": test_id,
                             "expected_version": int(current.get("entity_version") or 0), "writer_role": "ADVISOR",
                             "event_type": "TEST_ATTACHED_TO_ROADMAP", "changes": {"roadmap_id": rid}})
    for rid, refs in merged.items():
        requests.append({"request_id": f"REQ-INBOX-FRONTIER-ATTACH-{_slug(rid)}", "document": f"roadmaps/{rid}.json",
                         "merge": {"frontier_refs": refs}})
    if not requests:
        return []  # already attached: a no-op, not a failure
    return requests


def _hypothesis_requests(item: dict[str, Any], body: dict[str, Any], root: Path) -> list[dict[str, Any]]:
    test_id = str(body.get("test_id") or f"HYP-{_slug(str(item.get('_inbox_name') or body.get('title') or 'X'))}")
    existing_test = _entity(root, "test", test_id)
    if existing_test is not None:
        # Same test proposed again: fill what is still empty instead of rejecting (frozen fields are never replaced).
        fill = {k: v for k, v in body.items() if k in ("method", "null", "rival", "claim_boundary", "priority")
                and v and not existing_test.get(k)}
        sem = {k: v for k, v in (body.get("semantic") or {}).items() if v and not (existing_test.get("semantic") or {}).get(k)}
        if sem:
            fill["semantic"] = {**(existing_test.get("semantic") or {}), **sem}
        if not fill:
            return []
        return [{"request_id": f"REQ-INBOX-ENRICH-{_slug(test_id)}", "entity_kind": "test", "entity_name": test_id,
                 "expected_version": int(existing_test.get("entity_version") or 0), "writer_role": "ADVISOR",
                 "event_type": "TEST_ENRICHED", "changes": fill}]
    success = _first(body, "success_criteria", "criterio_sucesso", "critério_sucesso")
    kill = _first(body, "kill_criteria", "kill_criterion", "criterio_kill")
    # Missing frozen criteria never drop the idea: it is stored as DRAFT (visible, not executable) until completed.
    lifecycle = body.get("_status") or ("READY" if success and kill else "DRAFT")
    roadmap_id = body.get("roadmap_id") or _infer_roadmap(root, test_id, body.get("semantic") or {})
    siblings = _siblings(root, roadmap_id)
    inherited = {k: next((e[k] for e in siblings if e.get(k)), None) for k in ("campaign_id", "hypothesis_id", "domain")}
    question = _first(body, "question", "hypothesis", "hipotese", "hipótese")
    semantic = _complete_semantic(
        {"id": test_id, "roadmap_id": roadmap_id, "campaign_id": body.get("campaign_id") or inherited["campaign_id"], "question": question},
        body.get("semantic") or {}, root,
    )
    if not semantic.get("domain_id"):
        # Unknown area: file it under the roadmap's domain, else engineering for META, else science (UNMAPPED topic).
        fallback = (inherited.get("domain") or ("engineering" if test_id.upper().startswith("META-") else "science"))
        semantic = {**semantic, "domain_id": str(fallback).lower(), "basis": "WRITER_FALLBACK"}
    changes = {
        "kind": "TEST", "status": lifecycle, "state": lifecycle,
        "draft_reason": None if lifecycle != "DRAFT" else "faltam critérios congelados de sucesso/kill",
        "priority": body.get("priority") or "P1",
        "domain": str(semantic.get("domain_id", "science")).upper(),
        "roadmap_id": roadmap_id,
        "roadmap_test_id": test_id,
        "campaign_id": body.get("campaign_id") or inherited["campaign_id"],
        "hypothesis_id": body.get("hypothesis_id") or inherited["hypothesis_id"],
        "question": question,
        "method": body.get("method"),
        "null": body.get("null"),
        "rival": body.get("rival"),
        "dataset_and_selection": _first(body, "data", "dados_necessarios", "dados_necessários", "dataset_and_selection"),
        "success_criteria": success,
        "kill_criteria": kill,
        "claim_boundary": body.get("claim_boundary"),
        "depends_on": body.get("depends_on") or [],
        "proposed_by": "CHATGPT",
        "origin": "META" if test_id.upper().startswith("META-") else body.get("origin"),
        "linked_signal_ids": body.get("linked_signal_ids"),
        "semantic": semantic,
    }
    requests = [{
        "request_id": f"REQ-INBOX-{_slug(str(item.get('_inbox_name') or test_id))}",
        "entity_kind": "test", "entity_name": test_id, "expected_version": 0,
        "writer_role": "ADVISOR", "event_type": "ROADMAP_TEST_FROZEN",
        "changes": {k: v for k, v in changes.items() if v not in (None, "", [])},
    }]
    # The hypothesis itself (Ciência > Hipóteses): create or enrich its entity.
    block = body.get("hypothesis") if isinstance(body.get("hypothesis"), dict) else {}
    hypothesis_id = str(block.get("id") or changes.get("hypothesis_id") or f"HYP-{_slug(test_id)}")
    fields = {
        "title": block.get("title") or block.get("statement") or question,
        "statement": block.get("statement") or question,
        "model": block.get("model") or body.get("rival"),
        "baseline": block.get("baseline") or body.get("null"),
        "falsification_criterion": block.get("falsification_criterion") or kill,
        "status": block.get("status") or "OPEN",
        "domain": changes.get("domain"),
        "semantic": {k: semantic.get(k) for k in ("domain_id", "subdomain_id", "topic_id", "question_plain", "why_it_matters") if semantic.get(k)},
    }
    existing = _entity(root, "hypothesis", hypothesis_id)
    hyp_changes = {k: v for k, v in fields.items() if v not in (None, "", {}) and (existing is None or not existing.get(k))}
    if hyp_changes:
        requests.append({
            "request_id": f"REQ-INBOX-HYP-{_slug(hypothesis_id)}",
            "entity_kind": "hypothesis", "entity_name": hypothesis_id,
            "expected_version": int((existing or {}).get("entity_version") or 0),
            "writer_role": "ADVISOR", "event_type": "HYPOTHESIS_UPSERTED",
            "changes": hyp_changes,
        })
    requests[0]["changes"]["hypothesis_id"] = hypothesis_id
    if roadmap_id:
        path = fs_path(root, f"roadmaps/{roadmap_id}.json")
        if path.is_file():
            roadmap = json.loads(path.read_text(encoding="utf-8"))
            refs = list(roadmap.get("frontier_refs") or [])
            if test_id not in refs:
                requests.append({
                    "request_id": f"REQ-INBOX-FRONTIER-{_slug(test_id)}",
                    "document": f"roadmaps/{roadmap_id}.json",
                    "merge": {"frontier_refs": refs + [test_id]},
                })
    return requests


def _lesson_request(item: dict[str, Any], body: dict[str, Any], root: Path) -> list[dict[str, Any]]:
    semantic = body.get("semantic") or {}
    topic = str(body.get("topic_id") or semantic.get("topic_id") or semantic.get("subdomain_id") or "").strip()
    if not topic:
        linked = [(_entity(root, "test", str(t)) or {}).get("semantic") or {} for t in body.get("linked_test_ids") or []]
        topic = next((str(x.get("topic_id") or x.get("subdomain_id")) for x in linked if x.get("topic_id") or x.get("subdomain_id")),
                     "general." + _slug(str(body.get("title") or item.get("_inbox_name") or "lesson")).lower())
    lesson_id = f"LESSON::{topic}"
    current = _entity(root, "lesson", lesson_id)
    changes = {
        "title": body.get("title"), "status": "ACTIVE",
        "semantic": _semantic(current, {**semantic, "topic_id": topic}),
        "gap_type": body.get("gap_type"),
        "intuition": _first(body, "intuition", "intuicao", "intuição"),
        "explanation": _first(body, "explanation", "explicacao", "explicação", "formal"),
        "exercise": _first(body, "exercise", "exercicio", "exercício"),
        "linked_test_ids": body.get("linked_test_ids"),
        "linked_signal_ids": body.get("linked_signal_ids"),
        "updated_at": item.get("created_at"),
    }
    return [{
        "request_id": f"REQ-INBOX-{_slug(str(item.get('_inbox_name') or lesson_id))}",
        "entity_kind": "lesson", "entity_name": lesson_id,
        "expected_version": int((current or {}).get("entity_version") or 0),
        "writer_role": "LEARNER", "event_type": "LESSON_UPSERTED",
        "changes": {k: v for k, v in changes.items() if v not in (None, "", [])},
    }]


_BACKFILL_FIELDS = ("title", "subject_code", "question_plain")


def _backfill_requests(item: dict[str, Any], body: dict[str, Any], root: Path) -> list[dict[str, Any]]:
    """SEMANTIC_BACKFILL: fill plain-language fields on EXISTING tests/hypotheses/lessons.
    Only empty semantic keys are filled unless the entry says overwrite=true; nothing else changes."""
    entries = body.get("items") or body.get("tests") or body.get("entries") or ([body] if body.get("id") or body.get("test_id") else [])
    requests: list[dict[str, Any]] = []
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            continue
        entity_id = str(entry.get("id") or entry.get("test_id") or entry.get("hypothesis_id") or "").strip()
        kind = str(entry.get("entity_kind") or ("hypothesis" if entity_id.startswith("HYP") else "lesson" if entity_id.startswith("LESSON::") else "test"))
        current = _entity(root, kind, entity_id) if entity_id else None
        if current is None:
            continue
        old = dict(current.get("semantic") or {})
        new = {k: v for k, v in (entry.get("semantic") or {}).items() if v not in (None, "", [])}
        if not entry.get("overwrite"):
            new = {k: v for k, v in new.items() if not old.get(k)}
        changes: dict[str, Any] = {}
        if new:
            changes["semantic"] = {**old, **new}
        for field in ("subject_code",):
            code = re.sub(r"[^A-Z0-9]", "", str(entry.get(field) or "").upper())
            code = code if len(code) <= 4 else code[:3]
            if len(code) >= 2 and (entry.get("overwrite") or not current.get(field)):
                changes[field] = code  # a short code, never a name
        if changes:
            requests.append({
                "request_id": f"REQ-INBOX-BACKFILL-{_slug(entity_id)}-{index}",
                "entity_kind": kind, "entity_name": entity_id,
                "expected_version": int(current.get("entity_version") or 0),
                "writer_role": "ADVISOR", "event_type": "SEMANTIC_BACKFILLED",
                "changes": changes,
            })
    if not requests:
        return []  # nothing left to fill: a no-op, not a failure
    return requests


def _record_request(item: dict[str, Any], body: dict[str, Any], kind: str) -> list[dict[str, Any]]:
    """Learning signals and operator intents are kept as artifacts the GPT Learner reads back."""
    name = str(item.get("_inbox_name") or "item")
    return [{
        "request_id": f"REQ-INBOX-{_slug(name)}",
        "entity_kind": "artifact", "entity_name": f"{kind}::{_slug(name)}",
        "expected_version": 0, "writer_role": "LEARNER", "event_type": f"{kind}_RECORDED",
        "changes": {"kind": kind, "status": "RECORDED", "source": item.get("source") or "CHATGPT",
                    "created_at": item.get("created_at"), "payload": body},
    }]


_KIND_ALIASES = {
    "MUTATION_PROPOSAL": "MUTATION_PROPOSAL", "RESULT": "MUTATION_PROPOSAL", "TEST_RESULT": "MUTATION_PROPOSAL",
    "RESULT_PROPOSAL": "MUTATION_PROPOSAL", "EXECUTION_RESULT": "MUTATION_PROPOSAL",
    "HYPOTHESIS_PROPOSAL": "HYPOTHESIS_PROPOSAL", "HYPOTHESIS": "HYPOTHESIS_PROPOSAL", "TEST_PROPOSAL": "HYPOTHESIS_PROPOSAL",
    "LESSON_PROPOSAL": "LESSON_PROPOSAL", "LESSON": "LESSON_PROPOSAL",
    "LEARNING_SIGNAL": "LEARNING_SIGNAL", "SIGNAL": "LEARNING_SIGNAL", "KNOWLEDGE_GAP": "LEARNING_SIGNAL", "GAP": "LEARNING_SIGNAL",
    "OPERATOR_INTENT": "OPERATOR_INTENT", "INTENT": "OPERATOR_INTENT",
    "ROADMAP_ATTACH": "ROADMAP_ATTACH", "ATTACH": "ROADMAP_ATTACH",
    "SEMANTIC_BACKFILL": "SEMANTIC_BACKFILL", "BACKFILL": "SEMANTIC_BACKFILL", "MEANING_BACKFILL": "SEMANTIC_BACKFILL",
    "DATA_BINDING": "DATA_BINDING", "BINDING": "DATA_BINDING",
    "INTEGRITY_REPORT": "INTEGRITY_REPORT", "INTEGRITY": "INTEGRITY_REPORT", "AUDIT": "INTEGRITY_REPORT",
}
_BATCH_KEYS = ("tests", "results", "items", "proposals", "entries", "lessons", "hypotheses")


def _infer_kind(body: dict[str, Any]) -> str | None:
    if body.get("test_id") and (body.get("result") or body.get("verdict") or body.get("veredito")):
        return "MUTATION_PROPOSAL"
    if _first(body, "success_criteria", "criterio_sucesso", "critério_sucesso") and _first(body, "kill_criteria", "kill_criterion", "criterio_kill"):
        return "HYPOTHESIS_PROPOSAL"
    if (body.get("topic_id") or (body.get("semantic") or {}).get("topic_id")) and _first(body, "intuition", "intuicao", "intuição", "exercise", "exercicio", "exercício"):
        return "LESSON_PROPOSAL"
    if body.get("checks") and body.get("status") in {"GREEN", "YELLOW", "RED"}:
        return "INTEGRITY_REPORT"
    if body.get("signals") or body.get("gap_type"):
        return "LEARNING_SIGNAL"
    return None


def _normalize_result(body: dict[str, Any]) -> dict[str, Any]:
    """Pull verdict/meaning from wherever the GPT put them, so format drift never blocks a result."""
    body = dict(body)
    result = dict(body.get("result") or {})
    for key in ("verdict", "veredito", "decision", "decisão", "statistics", "estatísticas", "summary", "resumo"):
        if key in body and key not in result:
            result[key] = body[key]
    body["result"] = result
    semantic = dict(body.get("semantic") or {})
    if not semantic.get("result_meaning"):
        meaning = _first(semantic, "verdict_plain", "summary_plain") or _first(body, "result_meaning", "meaning", "significado")             or _first(result, "summary", "resumo", "interpretation", "interpretação")
        if meaning:
            semantic["result_meaning"] = str(meaning)
    body["semantic"] = semantic
    return body


def proposal_to_requests(item: dict[str, Any], root: str | Path) -> list[dict[str, Any]]:
    """Any ChatGPT proposal -> writer requests. Tolerant by design: known shapes become
    governed mutations; anything else is recorded as an artifact instead of blocking the inbox.

    ``item`` is the envelope ({kind, source, payload, created_at}) plus _inbox_id/_inbox_name;
    a bare payload (no envelope) is accepted too.
    """
    root = Path(root)
    if not isinstance(item, dict):
        raise ProposalError("proposal is not a JSON object")
    body = item.get("payload") if isinstance(item.get("payload"), dict) else {k: v for k, v in item.items() if not k.startswith("_")}
    raw_kind = str(item.get("kind") or body.get("kind") or "").upper().replace("-", "_").replace(" ", "_")
    batch = next((body[key] for key in _BATCH_KEYS if isinstance(body.get(key), list) and body.get(key)), None)
    first = batch[0] if batch and isinstance(batch[0], dict) else {}
    kind = _KIND_ALIASES.get(raw_kind) or _infer_kind(body) or _infer_kind(first) or raw_kind or "UNCLASSIFIED"
    if batch is not None and kind in {"MUTATION_PROPOSAL", "HYPOTHESIS_PROPOSAL", "LESSON_PROPOSAL"}:
        requests: list[dict[str, Any]] = []
        for index, entry in enumerate(batch):
            if not isinstance(entry, dict):
                continue
            named = dict(item, kind=kind, payload=entry, _inbox_name=f"{item.get('_inbox_name') or 'item'}-{index}")
            requests.extend(proposal_to_requests(named, root))
        return requests

    try:
        if kind == "MUTATION_PROPOSAL":
            return _result_request(item, _normalize_result(body), root)
        if kind == "HYPOTHESIS_PROPOSAL":
            return _hypothesis_requests(item, body, root)
        if kind == "LESSON_PROPOSAL":
            return _lesson_request(item, body, root)
        if kind == "SEMANTIC_BACKFILL":
            return _backfill_requests(item, body, root)
        if kind == "ROADMAP_ATTACH":
            return _attach_requests(item, body, root)
    except ProposalError as exc:
        # Keep the content in the Tower (nothing is lost) and say why it was not applied.
        return _record_request(item, {**body, "_not_applied_reason": str(exc)}, f"UNAPPLIED_{kind}")
    return _record_request(item, body, kind if kind in {"LEARNING_SIGNAL", "OPERATOR_INTENT", "INTEGRITY_REPORT", "DATA_BINDING"} else "INBOX_RECORD")
