"""Read-only owner context from one verified Tower snapshot.

No new store, transport, role grant, execution trigger or implicit publication.
The caller supplies a Tower obtained through an existing authorized connection.
This is an owner-private view, never an authorization check for an HTTP endpoint.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .continuity import CONTRACT, CATEGORIES, IDENTITY, SCOPE, need
from .memory import Snapshot, clean, digest, utc
from .retrieval import BM25, tokens

MEMORY = "NEXO_MEMORY_ENTRY"
PROJECT = "NEXO_PROJECT_EVENT"
ACTIVE = {"CURRENT", "CONTESTED"}


def _citation(snapshot: Snapshot, path: str, record: dict) -> dict:
    return {"source_id": snapshot.source_id, "tower_revision": snapshot.revision,
            "path": path, "json_pointer": "", "excerpt_json_pointer": "/payload/text",
            "entity_version": record["entity_version"],
            "content_sha256": digest(record)}


def _sources(snapshot: Snapshot, refs: list) -> list[dict]:
    need(isinstance(refs, list), "SOURCE_REFS_INVALID")
    result = []
    for ref in refs:
        need(isinstance(ref, dict) and set(ref) == {"path", "sha256"}
             and isinstance(ref["path"], str) and isinstance(ref["sha256"], str), "SOURCE_REF_INVALID")
        entry = snapshot.payload["files"].get(ref["path"])
        current = (digest(entry["value"]) if isinstance(entry, dict)
                   and entry.get("encoding") == "json" and isinstance(entry.get("value"), dict)
                   else None)
        state = ("SOURCE_UNAVAILABLE_IN_SNAPSHOT" if current is None else
                 "VERIFIED_IN_SNAPSHOT" if current == ref["sha256"] else "SOURCE_CHANGED")
        result.append({**ref, "state": state, "current_sha256": current,
                       "tower_revision": snapshot.revision})
    return result


def _records(snapshot: Snapshot, scope: str) -> list[dict]:
    result, identities = [], set()
    for path, entry in snapshot.payload["files"].items():
        if not path.startswith("entities/artifact/") or entry.get("encoding") != "json":
            continue
        record = entry.get("value")
        if not isinstance(record, dict) or record.get("kind") not in {MEMORY, PROJECT}:
            continue
        body = record.get("payload")
        need(isinstance(body, dict), "CONTINUITY_RECORD_INVALID")
        if body.get("scope") != scope:
            continue
        need(body.get("contract") == CONTRACT, "CONTINUITY_CONTRACT_INVALID")
        need(record.get("private") is True and record.get("allowed_roles") == []
             and body.get("access") == "OWNER_PRIVATE", "OWNER_PRIVATE_RECORD_REQUIRED")
        need(type(record.get("entity_version")) is int and record["entity_version"] > 0,
             "CONTINUITY_VERSION_INVALID")
        need(isinstance(body.get("event_id"), str) and IDENTITY.fullmatch(body["event_id"]),
             "CONTINUITY_EVENT_ID_INVALID")
        prefix = "MEMORY-" if record["kind"] == MEMORY else "PROJECT-EVENT-"
        identity = prefix + digest([scope, body["event_id"]])[:40]
        need(record.get("id") == identity and path == "entities/artifact/" + identity + ".json"
             and identity not in identities, "CONTINUITY_IDENTITY_INVALID")
        need(isinstance(body.get("text"), str) and body["text"].strip(), "CONTINUITY_TEXT_REQUIRED")
        need(isinstance(body.get("recorded_at"), str), "CONTINUITY_TIME_REQUIRED")
        utc(body["recorded_at"])
        need(body.get("scientific_authority") is False, "SYNTHESIS_NOT_INDEPENDENT_EVIDENCE")
        identities.add(identity)
        result.append({"id": identity, "kind": record["kind"], "body": body,
                       "citation": _citation(snapshot, path, record),
                       "source_checks": _sources(snapshot, body.get("sources", []))})
    return result


def _item(row: dict, state: str) -> dict:
    body = row["body"]
    drift = any(s["state"] != "VERIFIED_IN_SNAPSHOT" for s in row["source_checks"])
    return {"requires_source_review": drift,
            "support_state": "REVALIDATION_REQUIRED" if drift else "SOURCE_MATCHES_SNAPSHOT" if row["source_checks"] else "RECORDED_STATEMENT_WITHOUT_SOURCE",
            "id": row["id"], "kind": row["kind"], "scope": body["scope"],
            "text": clean(body["text"]), "redacted": clean(body["text"]) != body["text"],
            "state": state, "recorded_at": body["recorded_at"],
            "time_basis": "DECLARED_RECORD_TIMESTAMP",
            "citation": row["citation"], "source_checks": row["source_checks"],
            "scientific_authority": False, "independence": "NOT_ESTABLISHED"}


def _memories(rows: list[dict], at: datetime) -> list[dict]:
    known = {r["id"]: r for r in rows if r["kind"] == MEMORY}
    successors: dict[str, str] = {}
    for identity, row in known.items():
        body = row["body"]
        need(body.get("category") in CATEGORIES, "MEMORY_CATEGORY_INVALID")
        target = body.get("supersedes_record_id")
        if target:
            need(target in known and target != identity, "MEMORY_SUPERSESSION_SCOPE_INVALID")
            need(known[target]["body"]["category"] == body["category"], "MEMORY_SUPERSESSION_CATEGORY_INVALID")
            need(target not in successors, "MEMORY_SUPERSESSION_FORK")
            successors[target] = identity
        need(isinstance(body.get("contradicts", []), list), "MEMORY_CONTRADICTIONS_INVALID")
        for target in body.get("contradicts", []):
            need(isinstance(target, str) and target in known and target != identity,
                 "MEMORY_CONTRADICTION_SCOPE_INVALID")
    for start in successors:
        seen, current = set(), start
        while current in successors:
            need(current not in seen, "MEMORY_SUPERSESSION_CYCLE")
            seen.add(current)
            current = successors[current]
    result = {}
    for identity, row in known.items():
        body = row["body"]
        start = utc(body.get("valid_from") or body["recorded_at"])
        end = utc(body["valid_until"]) if body.get("valid_until") else None
        need(end is None or end > start, "MEMORY_VALIDITY_INVALID")
        descendant, replaced = successors.get(identity), False
        while descendant:
            successor = known[descendant]["body"]
            replaced = replaced or utc(successor.get("valid_from") or successor["recorded_at"]) <= at
            descendant = successors.get(descendant)
        state = ("SCHEDULED" if start > at else "SUPERSEDED" if replaced else
                 "EXPIRED" if end is not None and end <= at else "CURRENT")
        result[identity] = {**_item(row, state), "category": body["category"],
                            "valid_from": start.isoformat(), "valid_until": end.isoformat() if end else None,
                            "superseded_by": successors.get(identity),
                            "supersedes_record_id": body.get("supersedes_record_id"),
                            "applicability": clean(body.get("applicability")),
                            "contradicts": list(body.get("contradicts", []))}
    for item in result.values():
        for target in item["contradicts"]:
            other = result[target]
            if item["state"] in ACTIVE and other["state"] in ACTIVE:
                item["state"] = other["state"] = "CONTESTED"
    return list(result.values())


def _projects(rows: list[dict], at: datetime) -> list[dict]:
    groups: dict[str, list[dict]] = {}
    for row in rows:
        if row["kind"] == PROJECT:
            body = row["body"]
            need(isinstance(body.get("project_id"), str) and IDENTITY.fullmatch(body["project_id"]),
                 "PROJECT_ID_INVALID")
            need(type(body.get("sequence")) is int and body["sequence"] > 0, "PROJECT_SEQUENCE_INVALID")
            groups.setdefault(body["project_id"], []).append(row)
    result = []
    for project, chain in sorted(groups.items()):
        chain.sort(key=lambda r: r["body"]["sequence"])
        previous, visible = None, []
        for sequence, row in enumerate(chain, 1):
            body = row["body"]
            need(body["sequence"] == sequence and body.get("expected_previous") ==
                 (previous["id"] if previous else None), "PROJECT_SEQUENCE_INVALID")
            action = body.get("action")
            need((not previous and action == "CREATED") or
                 (previous and action in {"PROGRESS", "BLOCKED", "DELIVERY", "DECISION_REQUIRED",
                                          "DECISION", "COMPLETED", "REOPENED"}), "PROJECT_LIFECYCLE_INVALID")
            if previous:
                completed = previous["body"]["action"] == "COMPLETED"
                need((completed and action == "REOPENED") or (not completed and action != "REOPENED"),
                     "PROJECT_LIFECYCLE_INVALID")
            if action in {"PROGRESS", "DELIVERY", "DECISION", "COMPLETED", "REOPENED"}:
                need(body.get("sources"), "MATERIAL_PROGRESS_EVIDENCE_REQUIRED")
            if utc(body["recorded_at"]) <= at:
                visible.append(row)
            previous = row
        if not visible:
            continue
        # A backdated child cannot appear before its predecessor in a historical view.
        need([r["body"]["sequence"] for r in visible] == list(range(1, len(visible) + 1)),
             "PROJECT_DECLARED_TIME_ORDER_AMBIGUOUS")
        head = visible[-1]
        body, owner, next_action, pending, deliveries = head["body"], None, None, None, []
        for row in visible:
            event = row["body"]
            owner = event.get("owner", owner)
            next_action = event.get("next_action", next_action)
            if event["action"] == "DECISION_REQUIRED":
                pending = {"record_id": row["id"], "decision": clean(event.get("decision")),
                           "citation": row["citation"]}
            elif event["action"] in {"DECISION", "COMPLETED"}:
                pending = None
            if event["action"] == "DELIVERY":
                delivery = event.get("delivery")
                need(isinstance(delivery, dict) and delivery.get("source_path") in
                     {s["path"] for s in row["source_checks"]}, "DELIVERY_CANONICAL_SOURCE_REQUIRED")
                deliveries.append({"record_id": row["id"], "delivery": clean(delivery),
                                   "citation": row["citation"], "source_checks": row["source_checks"]})
        state = {"COMPLETED": "COMPLETED", "BLOCKED": "BLOCKED"}.get(body["action"], "ACTIVE")
        if pending and state != "COMPLETED":
            state = "DECISION_REQUIRED"
        result.append({**_item(head, state), "project_id": project, "title": clean(body["title"]),
                       "sequence": body["sequence"], "last_action": body["action"],
                       "owner": clean(owner), "next_action": None if state == "COMPLETED" else clean(next_action),
                       "pending_decision": pending, "deliveries": deliveries,
                       "depends_on": clean(body.get("depends_on", [])),
                       "event_count": len(visible), "history_ids": [r["id"] for r in visible]})
    return result


def _rank(items: list[dict], query: str, limit: int, include_history: bool) -> tuple[str, list[dict]]:
    query = query.strip()
    exact = [i for i in items if query in {i["id"], "ARTIFACT::" + i["id"], i.get("project_id", "")}]
    typed = query.startswith(("MEMORY-", "PROJECT-EVENT-", "ARTIFACT::"))
    if query and (exact or typed):
        return "exact", [{**i, "scores": {"exact_identity": True}} for i in exact[:limit]]
    candidates = [i for i in items if i["kind"] == PROJECT or include_history or i["state"] in ACTIVE]
    if not query:
        candidates.sort(key=lambda i: (utc(i["recorded_at"]), i["id"]), reverse=True)
        return "recent", [{**i, "scores": {}} for i in candidates[:limit]]
    query_tokens = set(tokens(query))
    if not query_tokens:
        return "lexical", []
    texts = [i["text"] + " " + i.get("title", "") for i in candidates]
    scores = BM25(texts).score(query)
    hits = [{**candidates[n], "scores": {"bm25": score,
            "matched_terms": sorted(query_tokens & set(tokens(texts[n])))}}
            for n, score in scores.items() if score > 0]
    hits.sort(key=lambda i: (-i["scores"]["bm25"], i["id"]))
    return "lexical", hits[:limit]


def context(snapshot: Snapshot, *, scope: str, query: str = "", at: str | None = None,
            limit: int = 20, include_history: bool = False,
            expected_revision: str | None = None) -> dict[str, Any]:
    """Build private context. `at` is declared validity inside the supplied revision.

    It is not a reconstruction of what the system knew at a past wall-clock time.
    Exact IDs can return retired records with their state; free text defaults to
    current memory. Source drift suspends evidence support, not user history.
    """
    need(isinstance(snapshot, Snapshot), "VERIFIED_SNAPSHOT_REQUIRED")
    need(isinstance(scope, str) and SCOPE.fullmatch(scope), "EXPLICIT_MEMORY_SCOPE_REQUIRED")
    need(isinstance(query, str) and len(query) <= 4000, "CONTEXT_QUERY_INVALID")
    need(type(limit) is int and 1 <= limit <= 100 and type(include_history) is bool, "CONTEXT_BOUNDS_INVALID")
    need(expected_revision is None or expected_revision == snapshot.revision, "CONTEXT_REVISION_CHANGED")
    # A frozen dataclass does not freeze its nested payload. Detect mutation after read.
    fingerprint = "sha256:" + digest(snapshot.payload["files"])
    need(snapshot.revision == fingerprint == snapshot.payload.get("revision")
         == snapshot.payload.get("state_fingerprint")
         and snapshot.source_id == snapshot.payload.get("stable_file_id")
         and snapshot.observed_at == snapshot.payload.get("updated_at"), "CONTEXT_SOURCE_CHANGED_AFTER_READ")
    moment = utc(at) if at is not None else datetime.now(timezone.utc)
    rows = _records(snapshot, scope)
    memories, projects = _memories(rows, moment), _projects(rows, moment)
    mode, hits = _rank(memories + projects, query, limit, include_history)
    warnings = sorted({s["state"] for i in memories + projects for s in i["source_checks"]
                       if s["state"] != "VERIFIED_IN_SNAPSHOT"})
    return {"contract": "NEXO_OWNER_CONTEXT_V1", "access": "OWNER_PRIVATE", "scope": scope,
            "source_id": snapshot.source_id, "source_revision": snapshot.revision,
            "source_raw_sha256": snapshot.raw_sha256, "source_updated_at": snapshot.observed_at,
            "at": moment.isoformat(), "temporal_semantics": "DECLARED_VALIDITY_WITHIN_SUPPLIED_SNAPSHOT",
            "historical_knowledge_reconstructed": False, "mode": mode, "query": clean(query),
            "hits": hits, "counts": {"records": len(rows), "memories": len(memories),
            "current_memories": sum(i["state"] in ACTIVE for i in memories),
            "contested_memories": sum(i["state"] == "CONTESTED" for i in memories),
            "projects": len(projects), "decisions_required": sum(bool(i["pending_decision"]) for i in projects)},
            "source_warnings": warnings, "authority": "DERIVED_VIEW_OF_CANONICAL_TOWER",
            "scheduler_mutation": False, "scientific_execution": False, "published": False}
