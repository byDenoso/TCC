"""Owner-scoped memory and project events, persisted only by the existing Writer."""
from __future__ import annotations
import copy
import json
import re
from pathlib import Path
from .memory import canonical, digest, utc
from .tower_paths import entity_path
from .enxame import source_refs

CONTRACT = "NEXO_CONTINUITY_V1"
CATEGORIES = {"USER_PREFERENCE", "USER_DECISION", "PROJECT_CONTEXT", "SCIENTIFIC_EVIDENCE", "OPERATIONAL_LESSON"}
ACTIONS = {"CREATED", "PROGRESS", "BLOCKED", "DELIVERY", "DECISION_REQUIRED", "DECISION", "COMPLETED", "REOPENED"}
SCOPE = re.compile(r"^(?:SCIENCE|WORK|PERSONAL|CLIENT:[A-Za-z0-9_-]{1,80})$")
IDENTITY = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,199}$")
SOURCES = {"DENER", "CHATGPT", "ATLAS_OWNER", "LEARNER", "ENGINEER", "ADVISOR", "EXECUTOR", "REFEREE_1", "PITIA", "GUARDIAO"}

class ContinuityError(ValueError):
    pass

def need(condition, code):
    if not condition:
        raise ContinuityError(code)

def records(root):
    folder = Path(root) / "entities" / "artifact"
    rows = [json.loads(p.read_text()) for p in folder.glob("*.json")] if folder.is_dir() else []
    return [r for r in rows if r.get("kind") in {"NEXO_MEMORY_ENTRY", "NEXO_PROJECT_EVENT"} and r.get("payload", {}).get("contract") == CONTRACT]

def apply(root, request):
    kind, body, role = request["nexo_operation"], copy.deepcopy(request["payload"]), request["role"]
    need(role in SOURCES and isinstance(body, dict), "CONTINUITY_AUTHOR_INVALID")
    common = {"event_id", "scope", "sources", "text", "supersedes_record_id", "valid_from", "valid_until"}
    allowed = common | ({"category", "contradicts", "applicability"} if kind == "NEXO_MEMORY_ENTRY" else {"project_id", "title", "action", "next_action", "owner", "depends_on", "delivery", "expected_previous", "decision"})
    need(not set(body)-allowed and SCOPE.fullmatch(str(body.get("scope", ""))) and IDENTITY.fullmatch(str(body.get("event_id", ""))), "CONTINUITY_FIELDS_INVALID")
    need(isinstance(body.get("text"), str) and body["text"].strip() and len(body["text"]) <= 12000, "CONTINUITY_TEXT_REQUIRED")
    utc(request["created_at"])
    for field in ("valid_from", "valid_until"):
        if body.get(field):
            utc(body[field])
    if body.get("valid_from") and body.get("valid_until"):
        need(utc(body["valid_until"]) > utc(body["valid_from"]), "MEMORY_VALIDITY_INVALID")
    body["sources"] = source_refs(root, body.get("sources", []))
    if kind == "NEXO_MEMORY_ENTRY":
        need(body.get("category") in CATEGORIES, "MEMORY_CATEGORY_INVALID")
        need(isinstance(body.get('contradicts', []), list) and all(isinstance(i, str) for i in body.get('contradicts', [])), 'MEMORY_CONTRADICTIONS_INVALID')
        if body["category"] in {"SCIENTIFIC_EVIDENCE", "OPERATIONAL_LESSON"}:
            need(body["sources"] and body.get("applicability"), "MEMORY_EVIDENCE_AND_LIMITS_REQUIRED")
    else:
        need(IDENTITY.fullmatch(str(body.get("project_id", ""))) and body.get("action") in ACTIONS and isinstance(body.get("title"), str) and body["title"].strip(), "PROJECT_ID_OR_ACTION_INVALID")
        need("expected_previous" in body, "PROJECT_PREDECESSOR_REQUIRED")
        if body["action"] in {"PROGRESS", "DELIVERY", "COMPLETED", "DECISION"}:
            need(body["sources"], "MATERIAL_PROGRESS_EVIDENCE_REQUIRED")
        if body["action"] == "BLOCKED":
            need(body.get("next_action") and body.get("owner") and body.get("depends_on"), "PROJECT_BLOCKER_OWNER_REQUIRED")
        if body["action"] == "DECISION_REQUIRED":
            need(body.get("decision") and body.get("next_action"), "PROJECT_DECISION_REQUIRED")
        if body["action"] == "DELIVERY":
            delivery = body.get("delivery")
            need(isinstance(delivery, dict) and delivery.get("source_path") in {r["path"] for r in body["sources"]}, "DELIVERY_CANONICAL_SOURCE_REQUIRED")
    ident = ("MEMORY-" if kind == "NEXO_MEMORY_ENTRY" else "PROJECT-EVENT-") + digest([body["scope"], body["event_id"]])[:40]
    path = entity_path(root, "artifact", ident)
    existing = records(root)
    if kind == 'NEXO_MEMORY_ENTRY':
        for target in body.get('contradicts', []):
            need(any(r['id'] == target and r['kind'] == kind and r['payload']['scope'] == body['scope'] for r in existing), 'MEMORY_CONTRADICTION_SCOPE_INVALID')
    value = {"contract": CONTRACT, **body, "author": role, "recorded_at": request["created_at"], "scientific_authority": False, "independence": "NOT_ESTABLISHED", "access": "OWNER_PRIVATE"}
    if path.is_file():
        current = json.loads(path.read_bytes())
        replay = {k: v for k, v in current.get("payload", {}).items() if k != "sequence"}
        need(replay == value and current.get("kind") == kind, "CONTINUITY_ID_CONFLICT")
        return {"accepted": True, "status": "NO_OP", "readback": "PASS", "record_id": ident}
    if body.get("supersedes_record_id"):
        old = next((r for r in existing if r["id"] == body["supersedes_record_id"]), None)
        need(old and old["kind"] == kind and old["payload"]["scope"] == body["scope"], "MEMORY_SUPERSESSION_SCOPE_INVALID")
        need(not any(r["payload"].get("supersedes_record_id") == old["id"] for r in existing), "MEMORY_ALREADY_SUPERSEDED")
        if kind == "NEXO_MEMORY_ENTRY":
            need(old["payload"].get("category") == body["category"], "MEMORY_SUPERSESSION_CATEGORY_INVALID")
    if kind == "NEXO_PROJECT_EVENT":
        chain = [r for r in existing if r["kind"] == kind and r["payload"].get("project_id") == body["project_id"] and r["payload"]["scope"] == body["scope"]]
        chain.sort(key=lambda r: r["payload"].get("sequence", 0))
        prior = chain[-1] if chain else None
        need(body["expected_previous"] == (prior["id"] if prior else None), "PROJECT_VERSION_CHANGED")
        need((not prior and body["action"] == "CREATED") or (prior and body["action"] != "CREATED"), "PROJECT_LIFECYCLE_INVALID")
        if prior and prior["payload"]["action"] == "COMPLETED":
            need(body["action"] == "REOPENED" and body["sources"], "PROJECT_REOPEN_EVIDENCE_REQUIRED")
        value["sequence"] = len(chain)+1
        # Previous/sequence are derived, never accepted as caller authority.
        if path.is_file():
            raise ContinuityError("CONTINUITY_ID_CONFLICT")
    changes = {"id": ident, "kind": kind, "status": "RECORDED", "source": role, "created_at": request["created_at"], "payload": value, "private": True, "allowed_roles": []}
    from .tower_apply import apply_requests
    receipt = apply_requests(root, [{"request_id": "REQ-"+ident, "entity_kind": "artifact", "entity_name": ident, "expected_version": 0, "writer_role": "DAILY", "event_type": kind+"_RECORDED", "changes": changes}])[0]
    need(receipt.get("accepted", True) and not receipt.get("issue"), "CONTINUITY_WRITER_REJECTED")
    need(json.loads(path.read_bytes()).get("payload") == value, "CONTINUITY_READBACK_FAILED")
    return {**receipt, "record_id": ident, "scientific_execution": False}
