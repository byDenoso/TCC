"""Deterministic ChatGPT inbox -> Tower mutation requests (no LLM in the loop).

ChatGPT does the thinking (runs tests, finds gaps, writes lessons) and drops one
proposal per file in an inbox. This module turns each proposal into the governed
requests the single writer applies, so the whole loop can run in CI.

Every function is pure over a materialized Tower root; nothing here writes.
"""

from __future__ import annotations

import json
import math
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from . import evolution
from .tower_paths import entity_path, fs_path

TERMINAL_VERDICTS = {"REJECTED", "FAILED", "FALSIFIED"}


class ProposalError(ValueError):
    """The proposal cannot be applied as-is; it stays in the inbox."""


def compose_board_snapshots(requests: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Carry BOARD_POST document snapshots forward inside one conversion batch.

    Document merges replace a complete list. When several envelopes were
    converted from the same root, later snapshots otherwise erased posts from
    earlier envelopes. Preserve order and let a later copy of the same id win.
    """
    order: list[str] = []
    by_id: dict[str, dict[str, Any]] = {}
    composed: list[dict[str, Any]] = []
    def signature(post: dict[str, Any]) -> tuple:
        return (post.get("from"), post.get("to"), post.get("text"), tuple(post.get("refs") or []),
                post.get("reply_to"), bool(post.get("private")))

    for request in requests:
        current = request
        if request.get("document") == evolution.BOARD_DOC:
            merge = request.get("merge") if isinstance(request.get("merge"), dict) else {}
            posts = merge.get("posts") if isinstance(merge.get("posts"), list) else []
            for post in posts:
                if not isinstance(post, dict) or not str(post.get("id") or ""):
                    continue
                post_id = str(post["id"])
                prior = by_id.get(post_id)
                prior_content = prior is not None and all(prior.get(key) is not None for key in ("from", "to", "text"))
                post_content = all(post.get(key) is not None for key in ("from", "to", "text"))
                if prior_content and post_content and signature(prior) != signature(post):
                    raise ProposalError("BOARD_ID_COLLISION")
                if prior is None:
                    order.append(post_id)
                combined = {**(prior or {}), **post}
                if prior is not None and prior.get("resolved_at") and not combined.get("resolved_at"):
                    combined["resolved_at"] = prior["resolved_at"]
                    combined["resolved_by"] = prior.get("resolved_by")
                by_id[post_id] = combined
            resolve_ids = {str(value) for value in request.get("_board_resolve_ids") or []}
            for post_id in resolve_ids:
                if post_id in by_id and not by_id[post_id].get("resolved_at"):
                    by_id[post_id] = {**by_id[post_id],
                                      "resolved_at": request.get("_board_resolved_at"),
                                      "resolved_by": request.get("_board_resolved_by")}
            current = {**request, "merge": {**merge, "posts": [by_id[post_id] for post_id in order][-300:]}}
        composed.append(current)
    return composed


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
        # Internal registration must not strand the result: a provisional name/domain is filled here
        # (a later SEMANTIC_BACKFILL can rename it); new tests proposed directly still need both.
        sem = body.get("semantic") if isinstance(body.get("semantic"), dict) else {}
        words = str(body.get("question") or test_id.replace("-", " ").title()).rstrip("?.! ").split()
        created = _hypothesis_requests(item, {
            # A result import cannot obtain a prospective receipt by briefly
            # registering a TEST before the result in the same envelope.
            **{k: v for k, v in body.items() if k != "prediction"}, "_allow_draft": True, "_status": "DRAFT",
            "display_name": body.get("display_name") or sem.get("display_name") or " ".join(words[:7]),
            "domain": body.get("domain") or sem.get("domain_id")
                      or ("engineering" if test_id.upper().startswith("META-") else "science"),
        }, root)
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
        "statistics": _first(result, "statistics", "estatísticas", "estatisticas")
                      or ({"p_value": result["p_value"]} if result.get("p_value") is not None else None),
        "limitations": body.get("limitations"),
        "reproducibility": body.get("reproducibility"),
        "executed_by": "CHATGPT_TASK_EXECUTOR",
        "executed_at": item.get("created_at"),
        "inbox_ref": item.get("_inbox_id"),
        "prediction": body.get("prediction") or result.get("prediction"),
        "arm": body.get("arm"),
        "semantic": semantic,
    }
    # A legacy/manual result may still be recorded scientifically, but it may
    # close an execution attempt only when it names the current observed
    # runner attempt. The mutation guard revalidates the completed battery and
    # every binding at apply time; these converter checks only decide whether
    # to request closure or leave the execution phase untouched.
    from . import scientific_integrity as integrity
    active_execution = (
        str(current.get("status") or current.get("state") or "").upper() == "RUNNING"
        or str(current.get("execution_phase") or "").upper() == "RUNNING"
        or test_id in integrity.active_tests(root)
    )
    if active_execution:
        reproducibility = changes.get("reproducibility")
        if not isinstance(reproducibility, dict):
            raise ProposalError("ACTIVE_EXECUTION_RESULT_PROOF_REQUIRED")
        expected = {
            "battery_id": current.get("battery_id"),
            "attempt_id": current.get("attempt_id"),
            "run_ref": current.get("run_ref"),
            "recipe_sha256": current.get("execution_recipe_sha256"),
        }
        if (str(current.get("status") or current.get("state") or "").upper() != "RUNNING"
                or str(current.get("execution_phase") or "").upper() != "RUNNING"
                or reproducibility.get("runner") != "GITHUB_ACTIONS"
                or not all(expected[key] and reproducibility.get(key) == expected[key] for key in expected)):
            raise ProposalError("ACTIVE_EXECUTION_RESULT_PROOF_REQUIRED")
        changes["execution_phase"] = "COMPLETED"
    if verdict in evolution.POSITIVE_VERDICTS and not current.get("review_state"):
        changes["review_state"] = "PENDING_REVIEW"  # a positive result must survive two referees to count
    version = 1 if created else int(current.get("entity_version") or 0)
    request_id = f"REQ-INBOX-RESULT-{_slug(str(item.get('_inbox_name') or test_id))}"
    if not created:
        from .mutations import _result_replay_receipt

        replay = _result_replay_receipt(
            current, {k: v for k, v in changes.items() if v not in (None, "", [], {})},
            request_id=request_id, expected_version=version, governance_meta={})
        if replay is not None:
            issue = replay.get("issue") if isinstance(replay.get("issue"), dict) else None
            if issue:
                raise ProposalError(str(issue.get("code") or "INBOX_RESULT_CONFLICT"))
            return []
    return created + [{
        "request_id": request_id,
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
    incident_id = evolution.resolve_incident_id(
        root,
        body.get("incident_id"),
        signal_refs=body.get("linked_signal_ids") or [],
        refs=body.get("refs") or [],
    )
    existing_test = _entity(root, "test", test_id)
    proposed_semantic = body.get("semantic") if isinstance(body.get("semantic"), dict) else {}
    proposed_display_name = str(body.get("display_name") or proposed_semantic.get("display_name") or "").strip()
    proposed_domain = str(body.get("domain") or proposed_semantic.get("domain_id") or "").strip()
    if existing_test is None and (not proposed_display_name or not proposed_domain):
        raise ProposalError("new TEST requires display_name and domain")
    if existing_test is not None:
        # Same test proposed again: fill what is still empty instead of rejecting (frozen fields are never replaced).
        fill = {k: v for k, v in body.items() if k in ("method", "null", "rival", "claim_boundary", "priority", "display_name", "domain")
                and v and not existing_test.get(k)}
        sem = {k: v for k, v in (body.get("semantic") or {}).items() if v and not (existing_test.get("semantic") or {}).get(k)}
        if sem:
            fill["semantic"] = {**(existing_test.get("semantic") or {}), **sem}
        if incident_id and not existing_test.get("incident_id"):
            fill["incident_id"] = incident_id
        if not fill:
            return []
        return [{"request_id": f"REQ-INBOX-ENRICH-{_slug(test_id)}", "entity_kind": "test", "entity_name": test_id,
                 "expected_version": int(existing_test.get("entity_version") or 0), "writer_role": "ADVISOR",
                 "event_type": "TEST_ENRICHED", "changes": fill}]
    success = _first(body, "success_criteria", "criterio_sucesso", "critério_sucesso")
    kill = _first(body, "kill_criteria", "kill_criterion", "criterio_kill")
    # Missing frozen criteria never drop the idea: it is stored as DRAFT (visible, not executable) until completed.
    data_needed = _first(body, "data", "dados_necessarios", "dados_necessários", "dataset_and_selection")
    missing = [name for name, value in (("critério de sucesso", success), ("critério de kill", kill),
                                        ("método", body.get("method")), ("dados", data_needed)) if not value]
    lifecycle = body.get("_status") or ("DRAFT" if missing else "READY")
    roadmap_id = body.get("roadmap_id") or _infer_roadmap(root, test_id, body.get("semantic") or {})
    source = str(item.get("source") or body.get("source") or "").upper()
    preparation_record = None
    if source in {"LEARNER", "SCIENTIST"}:
        active = {str(row.get("roadmap_id") or "") for row in _roadmap_index(root)
                  if str(row.get("state") or "").upper() == "ACTIVE"}
        if str(roadmap_id or "") not in active:
            raise ProposalError("SCIENTIST_ROADMAP_NOT_ACTIVE")
        preparation = body.get("preparation_evidence") if isinstance(body.get("preparation_evidence"), dict) else {}
        literature_refs = preparation.get("literature_refs")
        internal = preparation.get("internal_test_search") if isinstance(preparation.get("internal_test_search"), dict) else {}
        matches = internal.get("matched_test_ids")
        if not (isinstance(literature_refs, list) and literature_refs
                and all(isinstance(ref, str) and ref.strip() for ref in literature_refs)
                and isinstance(internal.get("query"), str) and internal["query"].strip()
                and internal.get("checked") is True and isinstance(matches, list)
                and all(isinstance(match, str) and match.strip() for match in matches)):
            raise ProposalError("SCIENTIST_LITERATURE_AND_INTERNAL_SEARCH_REQUIRED")
        if any(_entity(root, "test", str(match)) is None for match in matches):
            raise ProposalError("SCIENTIST_INTERNAL_SEARCH_REFERENCE_INVALID")
        if matches:
            replication = preparation.get("replication") if isinstance(preparation.get("replication"), dict) else {}
            compared_values = replication.get("compares_to_test_ids")
            purpose = replication.get("purpose")
            independence_axis = replication.get("independence_axis")
            if not (replication.get("justified") is True
                    and isinstance(purpose, str) and purpose.strip()
                    and isinstance(independence_axis, str) and independence_axis.strip()
                    and isinstance(compared_values, list)
                    and all(isinstance(value, str) and value.strip() for value in compared_values)):
                raise ProposalError("SCIENTIST_DUPLICATE_WITHOUT_REPLICATION_PURPOSE")
            compared = {value.strip() for value in compared_values}
            if not set(map(str, matches)).issubset(compared):
                raise ProposalError("SCIENTIST_DUPLICATE_WITHOUT_REPLICATION_PURPOSE")
            if any(_entity(root, "test", value) is None for value in compared):
                raise ProposalError("SCIENTIST_REPLICATION_REFERENCE_INVALID")
        preparation_record = {
            "literature_refs": list(literature_refs),
            "internal_test_search": {"checked": True, "query": internal["query"],
                                     "matched_test_ids": list(matches)},
        }
        if matches:
            preparation_record["replication"] = {
                "justified": True,
                "purpose": purpose.strip(),
                "independence_axis": independence_axis.strip(),
                "compares_to_test_ids": sorted(compared),
            }
    siblings = _siblings(root, roadmap_id)
    # Roadmap siblings may share campaign/domain, never the hypothesis: one roadmap holds several hypotheses.
    inherited = {k: next((e[k] for e in siblings if e.get(k)), None) for k in ("campaign_id", "domain")}
    question = _first(body, "question", "hypothesis", "hipotese", "hipótese")
    semantic = _complete_semantic(
        {"id": test_id, "roadmap_id": roadmap_id, "campaign_id": body.get("campaign_id") or inherited["campaign_id"], "question": question},
        body.get("semantic") or {}, root,
    )
    semantic = {**semantic, "domain_id": proposed_domain.lower(), "display_name": proposed_display_name}
    changes = {
        "kind": "TEST", "status": lifecycle, "state": lifecycle,
        "created_at": item.get("created_at"),
        "draft_reason": None if lifecycle != "DRAFT" else "faltam: " + ", ".join(missing or ["contrato"]),
        "family_id": body.get("family_id"), "family_cell": body.get("family_cell"),
        "recipe": body.get("recipe"), "recipe_params": body.get("recipe_params"),
        "data_binding": body.get("data_binding"), "independence": body.get("independence"),
        "independence_fingerprint": evolution.integrity.digest(body["independence"]) if isinstance(body.get("independence"), dict) else None,
        "priority": body.get("priority") or "P1",
        "display_name": proposed_display_name,
        "domain": str(proposed_domain).upper(),
        "roadmap_id": roadmap_id,
        "roadmap_test_id": test_id,
        "campaign_id": body.get("campaign_id") or inherited["campaign_id"],
        "hypothesis_id": body.get("hypothesis_id") or None,
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
        "incident_id": incident_id,
        "linked_signal_ids": body.get("linked_signal_ids"),
        "rank_score": body.get("rank_score"),
        "rank_rubric": body.get("rank_rubric"),
        "origin_kind": body.get("origin_kind"),
        "prior_art": body.get("prior_art"),
        "prediction": body.get("prediction"),
        "contests_test_id": body.get("contests_test_id"),
        "preparation_evidence": preparation_record,
        "semantic": semantic,
    }
    if lifecycle == "READY":
        changes["frozen_at"] = item.get("created_at") or evolution._now(item)
        # Public pre-registration: the frozen design's hash; the inbox commit that carried it is the timestamp.
        changes["prereg_hash"] = evolution.prereg_hash(test_id, changes)
        changes["prereg_ref"] = item.get("_inbox_name") or item.get("_inbox_id")
        check = evolution.integrity.readiness(root, dict(changes, id=test_id))
        changes["readiness"] = check
        if not check["eligible"]:
            changes.update(status="BLOCKED_INPUT", state="BLOCKED_INPUT", blocker=",".join(check["reasons"]))
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
        "incident_id": incident_id,
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
    incident_id = evolution.resolve_incident_id(
        root,
        body.get("incident_id"),
        signal_refs=body.get("linked_signal_ids") or [],
        refs=body.get("linked_test_ids") or [],
    )
    linked_incidents = list((current or {}).get("linked_incident_ids") or [])
    if incident_id and incident_id not in linked_incidents:
        linked_incidents.append(incident_id)
    changes = {
        "title": body.get("title"), "status": "ACTIVE",
        "incident_id": incident_id,
        "linked_incident_ids": linked_incidents or None,
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


def _campaign_roadmap(root: Path, campaign_id: str, roadmap_id: str | None) -> tuple[str, dict[str, Any]] | None:
    folder = root / "roadmaps"
    if not folder.is_dir():
        return None
    for path in sorted(folder.glob("*.json")):
        try:
            current = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(current, dict) or str(current.get("campaign_id") or "") != campaign_id:
            continue
        if roadmap_id and path.stem != roadmap_id and str(current.get("roadmap_id") or "") != roadmap_id:
            continue
        return f"roadmaps/{path.name}", current
    return None


def _redact_names(current: dict[str, Any], names: list[Any], code: Any) -> dict[str, Any]:
    """Privacy: replace person names by the subject code in every free-text field (titles, display_name,
    source_ref, justifications...). Ids and version fields are never touched. Returns changed top-level keys."""
    words = [str(n).strip() for n in names if len(str(n).strip()) >= 3]
    if not words:
        return {}
    code = re.sub(r"[^A-Z0-9]", "", str(code or "").upper())[:4] or "OLY"
    pattern = re.compile(r"(?<![A-Za-z])(" + "|".join(re.escape(w) for w in words) + r")(?![a-z])", re.IGNORECASE)

    def walk(value: Any, key: str) -> Any:
        if key == "id" or key.endswith("_id") or key.endswith("_ids") or key in ("entity_version", "subject_code"):
            return value
        if isinstance(value, str):
            return pattern.sub(code, value)
        if isinstance(value, list):
            return [walk(v, key) for v in value]
        if isinstance(value, dict):
            return {k: walk(v, k) for k, v in value.items()}
        return value

    return {k: new for k, v in current.items() if (new := walk(v, k)) != v}


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
        if current is None and kind == "campaign" and entity_id:
            roadmap = _campaign_roadmap(root, entity_id, str(entry.get("roadmap_id") or "").strip() or None)
            if roadmap:
                relative, current = roadmap
                old = dict(current.get("semantic") or {})
                new = {k: v for k, v in (entry.get("semantic") or {}).items() if v not in (None, "", [])}
                if not entry.get("overwrite"):
                    new = {k: v for k, v in new.items() if not old.get(k)}
                changes: dict[str, Any] = {}
                if new:
                    changes["semantic"] = {**old, **new}
                title = str(entry.get("title") or "").strip()
                if title and (entry.get("overwrite") or not current.get("title")):
                    changes["title"] = title
                for field in ("subject_code",):
                    code = re.sub(r"[^A-Z0-9]", "", str(entry.get(field) or "").upper())
                    code = code if len(code) <= 4 else code[:3]
                    if len(code) >= 2 and (entry.get("overwrite") or not current.get(field)):
                        changes[field] = code
                redacted = _redact_names(current, entry.get("redact_names") or [], entry.get("subject_code") or current.get("subject_code"))
                changes.update({k: v for k, v in redacted.items() if k not in changes})
                if changes:
                    requests.append({
                        "request_id": f"REQ-INBOX-BACKFILL-{_slug(entity_id)}-{index}",
                        "document": relative,
                        "merge": changes,
                    })
                continue
        if current is None:
            continue
        old = dict(current.get("semantic") or {})
        new = {k: v for k, v in (entry.get("semantic") or {}).items() if v not in (None, "", [])}
        if not entry.get("overwrite"):
            new = {k: v for k, v in new.items() if not old.get(k)}
        changes: dict[str, Any] = {}
        if new:
            changes["semantic"] = {**old, **new}
        title = str(entry.get("title") or "").strip()
        if title and (entry.get("overwrite") or not current.get("title")):
            changes["title"] = title
        display_name = str(entry.get("display_name") or (entry.get("semantic") or {}).get("display_name") or "").strip()
        if display_name and (entry.get("overwrite") or not current.get("display_name")):
            changes["display_name"] = display_name
        domain = str(entry.get("domain") or (entry.get("semantic") or {}).get("domain_id") or "").strip()
        if domain and (entry.get("overwrite") or not current.get("domain")):
            changes["domain"] = domain.upper()
        for field in ("subject_code",):
            code = re.sub(r"[^A-Z0-9]", "", str(entry.get(field) or "").upper())
            code = code if len(code) <= 4 else code[:3]
            if len(code) >= 2 and (entry.get("overwrite") or not current.get(field)):
                changes[field] = code  # a short code, never a name
        redacted = _redact_names(current, entry.get("redact_names") or [], entry.get("subject_code") or current.get("subject_code"))
        changes.update({k: v for k, v in redacted.items() if k not in changes})
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


def _operational_receipt_request(item: dict[str, Any], body: dict[str, Any]) -> list[dict[str, Any]]:
    """Admit one runner-bound engineering receipt without creating a TEST."""
    from .operational_prompts import EXECUTOR_PROMPT_HASHES
    receipt_id = str(body.get("receipt_id") or "")
    if (item.get("_inbox_source") != "RUNNER_OBSERVATION"
            or item.get("source") != "WRITER_ROBOT"
            or item.get("_inbox_name") != "operational-receipt-" + receipt_id
            or item.get("_inbox_id") != "runner:" + receipt_id):
        raise ProposalError("OPERATIONAL_RECEIPT_REQUIRES_RUNNER_OBSERVATION")
    required = {"contract", "receipt_id", "pipeline", "status", "scope",
                "scientific_result_eligible", "repository", "commit_sha", "run_ref",
                "run_attempt", "role_session", "input", "result", "decision",
                "result_sha256", "executed_at"}
    if set(body) != required:
        raise ProposalError("OPERATIONAL_RECEIPT_FIELDS_INVALID")
    attempt = body.get("run_attempt")
    run_ref = str(body.get("run_ref") or "")
    run_id = run_ref.removeprefix("actions/runs/")
    if (body.get("contract") != "NEXO_OPERATIONAL_RECEIPT_V1"
            or body.get("pipeline") != "DRIVE_GITHUB_ACTIONS_WRITER_TOWER_V1"
            or body.get("scope") != "ENGINEERING_OPERATIONAL_ONLY"
            or body.get("scientific_result_eligible") is not False
            or body.get("repository") != "byDenoso/Pantheon"
            or not re.fullmatch(r"[0-9a-f]{40}", str(body.get("commit_sha") or ""))
            or not re.fullmatch(r"actions/runs/[1-9][0-9]*", run_ref)
            or type(attempt) is not int or attempt < 1
            or receipt_id != f"drive-actions-{run_id}-{attempt}"
            or body.get("status") not in {"PASS", "DIVERGED"}
            or not re.fullmatch(r"[0-9a-f]{64}", str(body.get("result_sha256") or ""))):
        raise ProposalError("OPERATIONAL_RECEIPT_IDENTITY_INVALID")
    session = body.get("role_session")
    if (not isinstance(session, dict)
            or set(session) != {"contract", "session_id", "role", "work_id",
                                "mcp_endpoint", "mcp_tool", "prompt_sha256",
                                "context_sha256"}
            or session.get("contract") != "NEXO_ROLE_SESSION_V1"
            or session.get("session_id") != "drive-operational-control-v1"
            or session.get("role") != "EXECUTOR"
            or session.get("work_id") != "OPERATIONAL-CONTROL-DRIVE-SUM-V1"
            or session.get("mcp_endpoint") != "https://nexo-one-two.vercel.app/api/mcp"
            or session.get("mcp_tool") != "get_role_session"
            or session.get("prompt_sha256") not in EXECUTOR_PROMPT_HASHES
            or not re.fullmatch(r"[0-9a-f]{64}", str(session.get("context_sha256") or ""))):
        raise ProposalError("OPERATIONAL_RECEIPT_ROLE_SESSION_INVALID")
    source = body.get("input")
    if (not isinstance(source, dict)
            or set(source) != {"source_storage", "file_id", "version", "sha256", "scope"}
            or source.get("source_storage") != "GOOGLE_DRIVE_PRIVATE"
            or source.get("scope") != "DRIVE_BYTES_REVERIFIED_IN_SECRET_FREE_JOB"
            or source.get("file_id") != "1Cr7L6bbVlOqB0HUvYett0xkhRS-NWRWr"
            or source.get("version") != "0B9ZwoXbzaIA-dURSU09VT3BkanJvNlBlSDN5RjZUTUFOYnVRPQ"
            or source.get("sha256") != "3d87520f2b1bffb5c337e3d13d568ebe63d6aa09ad9cfa7dd2ed1a444d659988"):
        raise ProposalError("OPERATIONAL_RECEIPT_INPUT_INVALID")
    result = body.get("result")
    if (not isinstance(result, dict)
            or set(result) != {"count", "sum", "mean", "known_result_matched"}
            or type(result.get("count")) is not int or result["count"] < 1
            or any(isinstance(result.get(key), bool)
                   or not isinstance(result.get(key), (int, float))
                   or not math.isfinite(float(result[key])) for key in ("sum", "mean"))
            or type(result.get("known_result_matched")) is not bool):
        raise ProposalError("OPERATIONAL_RECEIPT_RESULT_INVALID")
    passed = body["status"] == "PASS"
    if ((passed != result["known_result_matched"])
            or body.get("decision") != ("OPERATIONAL_CONTROL_PASS" if passed
                                         else "OPERATIONAL_CONTROL_DIVERGED")
            or (passed and (result["count"] != 3
                            or not math.isclose(float(result["sum"]), 6.0, rel_tol=0, abs_tol=1e-12)
                            or not math.isclose(float(result["mean"]), 2.0, rel_tol=0, abs_tol=1e-12)))):
        raise ProposalError("OPERATIONAL_RECEIPT_KNOWN_RESULT_INVALID")
    try:
        executed = datetime.fromisoformat(str(body.get("executed_at") or "").replace("Z", "+00:00"))
    except ValueError as error:
        raise ProposalError("OPERATIONAL_RECEIPT_TIMESTAMP_INVALID") from error
    if executed.tzinfo is None:
        raise ProposalError("OPERATIONAL_RECEIPT_TIMESTAMP_INVALID")
    return _record_request(item, body, "OPERATIONAL_RECEIPT")


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
    "FAMILY_CHARTER": "FAMILY_CHARTER", "FAMILY": "FAMILY_CHARTER", "RECIPE_BIND": "RECIPE_BIND", "BIND_RECIPE": "RECIPE_BIND",
    "ROADMAP_CHARTER": "ROADMAP_CHARTER", "CHARTER": "ROADMAP_CHARTER", "ROADMAP_CLOSE": "ROADMAP_CLOSE",
    "CONTEST": "CONTEST", "REFUTATION": "CONTEST", "VERDICT_REVIEW": "VERDICT_REVIEW", "REVIEW": "VERDICT_REVIEW",
    "GENOME_MUTATION": "GENOME_MUTATION", "MUTATION_CANARY": "GENOME_MUTATION", "GENOME_ROLLBACK": "GENOME_ROLLBACK",
    "FITNESS_REPORT": "FITNESS_REPORT", "NEXO_THOUGHT": "NEXO_THOUGHT", "THOUGHT": "NEXO_THOUGHT",
    "DECOY_PLANT": "DECOY_PLANT", "DECOY_REVEAL": "DECOY_REVEAL", "DECOY_CALL": "DECOY_CALL", "TEST_BATTERY": "TEST_BATTERY", "BATTERY": "TEST_BATTERY", "BATTERY_STATUS": "BATTERY_STATUS",
    "BOARD_POST": "BOARD_POST", "BOARD": "BOARD_POST", "NOTE": "BOARD_POST", "MURAL": "BOARD_POST",
    "HANDOFF": "HANDOFF", "NEXO_HANDOFF": "HANDOFF", "AGENT_HANDOFF": "HANDOFF",
    "HANDOFF_TRANSITION": "HANDOFF_TRANSITION", "HANDOFF_ACK": "HANDOFF_TRANSITION",
    "HANDOFF_DONE": "HANDOFF_TRANSITION", "HANDOFF_FAILED": "HANDOFF_TRANSITION",
    "C01_CANARY": "OPERATIONAL_CANARY", "OPERATIONAL_CANARY": "OPERATIONAL_CANARY",
    "OPERATIONAL_RECEIPT": "OPERATIONAL_RECEIPT",
}
_EVOLUTION = {
    "DATA_BINDING": evolution.data_binding_requests,
    "FAMILY_CHARTER": evolution.family_charter_requests,
    "RECIPE_BIND": evolution.recipe_bind_requests,
    "ROADMAP_CHARTER": evolution.charter_requests,
    "ROADMAP_CLOSE": evolution.close_requests,
    "CONTEST": lambda item, body, root: evolution.contest_requests(item, body, root, _hypothesis_requests),
    "VERDICT_REVIEW": evolution.review_requests,
    "GENOME_MUTATION": evolution.mutation_requests,
    "GENOME_ROLLBACK": evolution.rollback_requests,
    "FITNESS_REPORT": evolution.fitness_requests,
    "NEXO_THOUGHT": evolution.thought_requests,
    "BOARD_POST": evolution.board_requests,
    "DECOY_PLANT": lambda item, body, root: evolution.decoy_requests(item, body, root, "DECOY_PLANT"),
    "DECOY_REVEAL": lambda item, body, root: evolution.decoy_requests(item, body, root, "DECOY_REVEAL"),
    "DECOY_CALL": lambda item, body, root: evolution.decoy_requests(item, body, root, "DECOY_CALL"),
    "TEST_BATTERY": evolution.battery_requests,
    "BATTERY_STATUS": lambda item, body, root: evolution.battery_status_requests(
        item, body, root, lambda i, b, r: _result_request(i, _normalize_result(b), r)),
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
    if raw_kind == "BATCH":
        # Several envelopes in one inbox file (bootstrap, multi-kind runs): each is applied on its own.
        requests = []
        for index, entry in enumerate(body.get("items") or []):
            if isinstance(entry, dict):
                parent_id = str(item.get("_inbox_id") or "").strip()
                requests.extend(proposal_to_requests({
                    **entry,
                    "_inbox_source": item.get("_inbox_source"),
                    "_inbox_name": f"{item.get('_inbox_name') or 'batch'}-{index}",
                    "_inbox_id": parent_id or None,
                    "_inbox_child_id": f"{parent_id}.batch-{index}" if parent_id else None,
                }, root))
        return compose_board_snapshots(requests)
    batch = next((body[key] for key in _BATCH_KEYS if isinstance(body.get(key), list) and body.get(key)), None)
    first = batch[0] if batch and isinstance(batch[0], dict) else {}
    kind = _KIND_ALIASES.get(raw_kind) or _infer_kind(body) or _infer_kind(first) or raw_kind or "UNCLASSIFIED"
    if kind in {"HANDOFF", "HANDOFF_TRANSITION"}:
        if str(item.get("_inbox_source") or "").upper() != "DRIVE":
            raise ProposalError("PRIVATE_HANDOFF_REQUIRES_DRIVE_INBOX")
        if kind == "HANDOFF":
            envelope = body.get("handoff") if isinstance(body.get("handoff"), dict) else body
            allowed = {
                "request_id", "from_role", "to_role", "handoff_type", "entity_ref", "thread_id",
                "summary_plain", "why_it_matters", "next_action", "objective_ref", "confidence_plain",
                "evidence_refs", "source_links", "correlation_id", "parent_handoff_id",
            }
            unknown = sorted(set(envelope) - allowed)
            if unknown:
                raise ProposalError("HANDOFF_FIELDS_UNSUPPORTED:" + ",".join(unknown))
            required = (
                "request_id", "from_role", "to_role", "handoff_type", "entity_ref", "thread_id",
                "summary_plain", "why_it_matters", "next_action",
            )
            missing = [key for key in required if not isinstance(envelope.get(key), str) or not envelope[key].strip()]
            if missing:
                raise ProposalError("HANDOFF_FIELDS_REQUIRED:" + ",".join(missing))
            return [{"nexo_operation": "HANDOFF_CREATE", "_inbox_source": "DRIVE", "handoff": dict(envelope)}]

        transition = body.get("transition") if isinstance(body.get("transition"), dict) else body
        unknown = sorted(set(transition) - {"handoff_id", "state", "writer_role"})
        if unknown:
            raise ProposalError("HANDOFF_TRANSITION_FIELDS_UNSUPPORTED:" + ",".join(unknown))
        fixed_state = {"HANDOFF_ACK": "ACK", "HANDOFF_DONE": "DONE", "HANDOFF_FAILED": "FAILED"}.get(raw_kind)
        state = str(transition.get("state") or fixed_state or "").upper()
        if fixed_state and state != fixed_state:
            raise ProposalError("HANDOFF_TRANSITION_STATE_CONFLICT")
        if state not in {"ACK", "DONE", "FAILED"}:
            raise ProposalError("HANDOFF_TRANSITION_STATE_INVALID")
        required = ("handoff_id", "writer_role")
        missing = [key for key in required if not isinstance(transition.get(key), str) or not transition[key].strip()]
        if missing:
            raise ProposalError("HANDOFF_TRANSITION_FIELDS_REQUIRED:" + ",".join(missing))
        return [{"nexo_operation": "HANDOFF_TRANSITION", "_inbox_source": "DRIVE",
                 "transition": {"handoff_id": transition["handoff_id"], "state": state,
                                "writer_role": transition["writer_role"]}}]

    if kind == "OPERATIONAL_CANARY":
        # C01 is a single scoped Tower operation. The inbox envelope's source,
        # author, and timestamp are deliberately not copied into the Writer
        # request and never authenticate the approval.
        action = str(body.get("action") or "").strip().upper()
        action_fields = {
            "INSTALL_CONFIG": {"config"},
            "START_SHADOW": {"offline_corpus_report"},
            "ACTIVATE_CANARY": {"shadow_report"},
            "PROMOTE": set(),
            "ROLLBACK": set(),
            "INTERRUPT": set(),
        }
        if action not in action_fields:
            raise ProposalError("OPERATIONAL_CANARY_ACTION_INVALID")
        allowed = {"action"} | action_fields[action]
        unknown = sorted(set(body) - allowed - {"kind"})
        if unknown:
            raise ProposalError("OPERATIONAL_CANARY_FIELDS_UNSUPPORTED:" + ",".join(unknown))
        missing = [key for key in action_fields[action]
                   if not isinstance(body.get(key), dict)]
        if missing:
            raise ProposalError("OPERATIONAL_CANARY_FIELDS_REQUIRED:" + ",".join(missing))
        return [{"nexo_operation": "OPERATIONAL_CANARY", "action": action,
                 **{key: dict(body[key]) for key in action_fields[action]}}]
    if kind == "OPERATIONAL_RECEIPT":
        return _operational_receipt_request(item, body)
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
        if kind in _EVOLUTION:
            requests = _EVOLUTION[kind](item, body, root)
            # Nothing to do (duplicate, spine gene, closed roadmap...) -> keep the proposal as a record, never fail.
            if not requests and kind == "BATTERY_STATUS":
                return []  # re-collected battery already applied: silent no-op (robot polls every 15 min)
            return requests or _record_request(item, {**body, "_noop_reason": getattr(requests, "reason", "NO_STATE_CHANGE")}, f"{kind}_NOOP")
        if kind == "OPERATOR_INTENT":
            gate = evolution.operator_requests(item, body, root)
            if gate:
                return gate + _record_request(item, body, "OPERATOR_INTENT")
    except ProposalError as exc:
        # Keep the content in the Tower (nothing is lost) and say why it was not applied.
        return _record_request(item, {**body, "_not_applied_reason": str(exc)}, f"UNAPPLIED_{kind}")
    return _record_request(item, body, kind if kind in {"LEARNING_SIGNAL", "OPERATOR_INTENT", "INTEGRITY_REPORT", "DATA_BINDING"} else "INBOX_RECORD")
