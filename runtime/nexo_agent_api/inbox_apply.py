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


def _result_request(item: dict[str, Any], body: dict[str, Any], root: Path) -> list[dict[str, Any]]:
    test_id = str(body.get("test_id") or "").strip()
    if not test_id:
        raise ProposalError("MUTATION_PROPOSAL without payload.test_id")
    current = _entity(root, "test", test_id)
    if current is None:
        raise ProposalError(f"test {test_id} does not exist in the Tower")
    result = body.get("result") or {}
    verdict = str(_first(result, "verdict", "veredito") or body.get("verdict") or "").upper() or None
    semantic = _semantic(current, body.get("semantic"))
    if not semantic.get("result_meaning"):
        raise ProposalError(f"{test_id}: result without semantic.result_meaning")
    status = "REJECTED" if verdict in TERMINAL_VERDICTS else "DONE"
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
    return [{
        "request_id": f"REQ-INBOX-{_slug(str(item.get('_inbox_name') or test_id))}",
        "entity_kind": "test",
        "entity_name": test_id,
        "expected_version": int(current.get("entity_version") or 0),
        "writer_role": "EXECUTOR",
        "event_type": "TEST_RESULT_RECORDED",
        "changes": {k: v for k, v in changes.items() if v not in (None, "", [], {})},
    }]


def _hypothesis_requests(item: dict[str, Any], body: dict[str, Any], root: Path) -> list[dict[str, Any]]:
    test_id = str(body.get("test_id") or f"HYP-{_slug(str(item.get('_inbox_name') or body.get('title') or 'X'))}")
    if _entity(root, "test", test_id) is not None:
        raise ProposalError(f"test {test_id} already exists")
    success = _first(body, "success_criteria", "criterio_sucesso", "critério_sucesso")
    kill = _first(body, "kill_criteria", "kill_criterion", "criterio_kill")
    if not success or not kill:
        raise ProposalError(f"{test_id}: hypothesis without frozen success and kill criteria")
    semantic = body.get("semantic") or {}
    if not semantic.get("domain_id"):
        raise ProposalError(f"{test_id}: hypothesis without semantic.domain_id")
    roadmap_id = body.get("roadmap_id")
    changes = {
        "kind": "TEST", "status": "READY", "state": "READY",
        "priority": body.get("priority") or "P1",
        "domain": str(semantic.get("domain_id", "science")).upper(),
        "roadmap_id": roadmap_id,
        "question": _first(body, "question", "hypothesis", "hipotese", "hipótese"),
        "method": body.get("method"),
        "null": body.get("null"),
        "rival": body.get("rival"),
        "dataset_and_selection": _first(body, "data", "dados_necessarios", "dados_necessários", "dataset_and_selection"),
        "success_criteria": success,
        "kill_criteria": kill,
        "claim_boundary": body.get("claim_boundary"),
        "depends_on": body.get("depends_on") or [],
        "proposed_by": "CHATGPT",
        "semantic": semantic,
    }
    requests = [{
        "request_id": f"REQ-INBOX-{_slug(str(item.get('_inbox_name') or test_id))}",
        "entity_kind": "test", "entity_name": test_id, "expected_version": 0,
        "writer_role": "ADVISOR", "event_type": "ROADMAP_TEST_FROZEN",
        "changes": {k: v for k, v in changes.items() if v not in (None, "")},
    }]
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
    topic = str(body.get("topic_id") or semantic.get("topic_id") or "").strip()
    if not topic:
        raise ProposalError("LESSON_PROPOSAL without topic_id")
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
        "updated_at": item.get("created_at"),
    }
    return [{
        "request_id": f"REQ-INBOX-{_slug(str(item.get('_inbox_name') or lesson_id))}",
        "entity_kind": "lesson", "entity_name": lesson_id,
        "expected_version": int((current or {}).get("entity_version") or 0),
        "writer_role": "LEARNER", "event_type": "LESSON_UPSERTED",
        "changes": {k: v for k, v in changes.items() if v not in (None, "", [])},
    }]


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


def proposal_to_requests(item: dict[str, Any], root: str | Path) -> list[dict[str, Any]]:
    """``item`` is the proposal envelope ({kind, source, payload, created_at}) plus _inbox_id/_inbox_name."""
    root = Path(root)
    if not isinstance(item, dict):
        raise ProposalError("proposal is not a JSON object")
    kind = str(item.get("kind") or "").upper()
    body = item.get("payload") if isinstance(item.get("payload"), dict) else {}
    if kind == "MUTATION_PROPOSAL":
        # One proposal may carry several results: {"tests": [{test_id, result, semantic, ...}, ...]}.
        batch = body.get("tests") if isinstance(body.get("tests"), list) else [body]
        requests = []
        for index, entry in enumerate(batch):
            named = dict(item, _inbox_name=f"{item.get('_inbox_name') or 'item'}-{index}") if len(batch) > 1 else item
            requests.extend(_result_request(named, entry if isinstance(entry, dict) else {}, root))
        return requests
    if kind == "HYPOTHESIS_PROPOSAL":
        return _hypothesis_requests(item, body, root)
    if kind == "LESSON_PROPOSAL":
        return _lesson_request(item, body, root)
    if kind in {"LEARNING_SIGNAL", "OPERATOR_INTENT"}:
        return _record_request(item, body, kind)
    raise ProposalError(f"unknown kind {kind!r}")
