"""Private preparation protocol inside the existing serialized Tower Writer.

The five roles are logical roles of one authorized owner, not independent humans.
Events are immutable canonical files; every view can be reconstructed from them.
No scheduling, scientific execution, credentials, transport or Tower publication.
"""
from __future__ import annotations
import copy
import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path
from .memory import canonical, digest, utc
from .tower_paths import fs_path, entity_path

CONTRACT = "NEXO_ENXAME_V1"
EVENT_ROOT = "evolution/enxame/events"
ROLES = {"A1", "A2", "A3", "A4", "A5"}
EVENTS = {"CLAIM", "SPEC", "OBJECAO", "RESPOSTA", "LINK", "SINAL", "ENDOSSO", "EMERGENTE", "CONFLITO", "LICAO", "FREEZE", "REGISTRO", "CANARIO", "FIM"}
ROLE_EVENTS = {
    "A1": {"CLAIM", "OBJECAO", "ENDOSSO", "SINAL", "LINK", "LICAO", "CONFLITO", "CANARIO"},
    "A2": {"SPEC", "RESPOSTA", "SINAL", "LICAO", "CONFLITO", "CANARIO"},
    "A3": {"OBJECAO", "ENDOSSO", "SINAL", "LICAO", "CONFLITO", "CANARIO"},
    "A4": {"LINK", "SINAL", "CONFLITO", "EMERGENTE", "ENDOSSO", "LICAO", "CANARIO"},
    "A5": {"FREEZE", "REGISTRO", "FIM", "SINAL", "CONFLITO", "CANARIO"},
}
ESSENTIAL = ("question", "null", "rival", "method", "dataset_and_selection", "success_criteria", "kill_criteria", "implementation")
DESIGN_FIELDS = ("observable", "likelihood", "parameters_and_priors", "statistic", "threshold", "multiplicity", "attempts", "systematics", "degeneracies", "null_expected", "dependencies", "cost")
SAFE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,199}$")

class EnxameError(ValueError):
    pass

def need(condition, code):
    if not condition:
        raise EnxameError(code)

def read_json(root, path):
    need(isinstance(path, str) and not path.startswith(("/", "\\")) and ".." not in path.split("/") and path.endswith(".json"), "SOURCE_PATH_INVALID")
    target = fs_path(root, path)
    need(target.is_file(), "SOURCE_NOT_FOUND")
    value = json.loads(target.read_text(encoding="utf-8"))
    need(isinstance(value, dict), "SOURCE_SHAPE_INVALID")
    return value

def scope_source(root, scope_id, version):
    need(isinstance(scope_id, str) and SAFE.fullmatch(scope_id), "SCOPE_ID_INVALID")
    need(type(version) is int and version > 0, "SCOPE_VERSION_INVALID")
    value = read_json(root, "roadmaps/" + scope_id + ".json")
    actual = value.get("entity_version", value.get("version", 1))
    need(actual == version, "SCOPE_VERSION_CHANGED")
    need(str(value.get("state") or value.get("status") or value.get("charter", {}).get("status") or "").upper() == "ACTIVE", "SCOPE_NOT_ACTIVE")
    return value

def source_refs(root, values):
    need(isinstance(values, list) and len(values) <= 32, "SOURCE_REFS_INVALID")
    for row in values:
        need(isinstance(row, dict) and set(row) == {"path", "sha256"}, "SOURCE_REF_INVALID")
        need(digest(read_json(root, row["path"])) == row["sha256"], "SOURCE_CONTENT_CHANGED")
    return copy.deepcopy(values)

def has_content(value):
    """Reject empty/whitespace containers without discarding a defined zero."""
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, dict):
        return any(has_content(item) for item in value.values())
    if isinstance(value, list):
        return any(has_content(item) for item in value)
    return type(value) in {int, float, bool} and math.isfinite(value)

def gap_names(spec):
    missing = [key for key in ESSENTIAL if not has_content(spec.get(key))]
    requirements = spec.get("requirements", {})
    if not isinstance(requirements, dict):
        return missing + ["requirements"]
    for key in DESIGN_FIELDS:
        row = requirements.get(key)
        if not isinstance(row, dict) or not (
            row.get("status") == "DEFINED" and has_content(row.get("value"))
            or row.get("status") == "NOT_APPLICABLE" and isinstance(row.get("reason"), str) and row["reason"].strip()
        ):
            missing.append(key)
    for key, row in requirements.items():
        if key not in DESIGN_FIELDS and isinstance(row, dict) and row.get("required") is True and not has_content(row.get("value")):
            missing.append(key)
    explicit = spec.get("gaps", [])
    if not isinstance(explicit, list) or any(not isinstance(x, str) or not x.strip() for x in explicit):
        return missing + ["gaps"]
    return sorted(set(missing + explicit))

def load_events(root, scope_id=None, version=None):
    folder = fs_path(root, EVENT_ROOT)
    rows = [json.loads(p.read_text(encoding="utf-8")) for p in folder.glob("*.json")] if folder.is_dir() else []
    rows = [r for r in rows if (scope_id is None or r.get("scope_id") == scope_id) and (version is None or r.get("scope_version") == version)]
    groups = {}
    for row in rows:
        groups.setdefault((row.get("scope_id"), row.get("scope_version")), []).append(row)
    for group in groups.values():
        previous = None
        ids = set()
        for seq, row in enumerate(sorted(group, key=lambda r: r["sequence"]), 1):
            need(row.get("contract") == CONTRACT and row.get("sequence") == seq and row.get("previous_hash") == previous, "BOARD_SEQUENCE_INVALID")
            need(row.get("event_id") not in ids and row.get("sha256") == digest({k: v for k, v in row.items() if k != "sha256"}), "BOARD_CONTENT_INVALID")
            previous = row["sha256"]
            ids.add(row["event_id"])
    return sorted(rows, key=lambda r: (r["scope_id"], r["scope_version"], r["sequence"]))

def derive(events, now=None):
    cards, closed, head = {}, False, None
    now = now or datetime.now(timezone.utc).isoformat()
    for e in events:
        head = e["sha256"]
        kind, body, cid = e["event_type"], e["body"], e.get("card_id")
        if kind == "FIM":
            closed = True
            continue
        if not cid:
            continue
        if kind in {"CLAIM", "EMERGENTE"}:
            cards[cid] = {"id": cid, "claim": body.get("claim"), "origin": e["event_id"], "sources": e["sources"], "emergent": kind == "EMERGENTE", "classification": body.get("classification"), "legacy_test_ref": body.get("legacy_test_ref"), "spec": None, "spec_version": 0, "spec_sha256": None, "endorsements": {}, "objections": {}, "conflicts": {}, "links": [], "signals": [], "freeze": None, "registration": None, "last_material_event": e["event_id"], "last_material_at": e["applied_at"]}
        card = cards.get(cid)
        need(card is not None, "CARD_HISTORY_INVALID")
        material = False
        if kind == "SPEC":
            card.update(spec=body["spec"], spec_version=e["spec_version"], spec_sha256=digest(body["spec"]), endorsements={}, freeze=None)
            material = True
        elif kind == "OBJECAO":
            card["objections"][e["event_id"]] = {"author": e["role"], "text": body["text"], "spec_version": e["spec_version"], "response": None, "resolved": False}
            material = True
        elif kind == "RESPOSTA":
            card["objections"][body["objection_id"]]["response"] = {"event_id": e["event_id"], "text": body["text"], "spec_version": e["spec_version"], "sources": e["sources"]}
            material = True
        elif kind == "ENDOSSO":
            for oid in body.get("resolves", []):
                card["objections"][oid]["resolved"] = True
            card["endorsements"][e["role"]] = {"event_id": e["event_id"], "spec_version": e["spec_version"]}
            material = True
        elif kind == "CONFLITO":
            if body.get("resolves"):
                card["conflicts"][body["resolves"]]["resolved"] = True
            else:
                card["conflicts"][e["event_id"]] = {"author": e["role"], "text": body["text"], "resolved": False}
            material = True
        elif kind == "LINK":
            card["links"].append({"event_id": e["event_id"], **body})
            material = True
        elif kind == "SINAL":
            card["signals"].append({"event_id": e["event_id"], "at": e["applied_at"], 'sequence':e['sequence'], **body})
        elif kind == "FREEZE":
            card["freeze"] = {"event_id": e["event_id"], "spec_version": e["spec_version"], "spec_sha256": card["spec_sha256"]}
            material = True
        elif kind == "REGISTRO":
            card["registration"] = {"event_id": e["event_id"], **body}
            material = True
        if material:
            card.update(last_material_at=e["applied_at"], last_material_event=e["event_id"], last_material_sequence=e['sequence'])
    for card in cards.values():
        card["gaps"] = gap_names(card["spec"]) if card["spec"] else list(ESSENTIAL + DESIGN_FIELDS)
        card["open_objections"] = [k for k, v in card["objections"].items() if not v["resolved"]]
        card["open_conflicts"] = [k for k, v in card["conflicts"].items() if not v["resolved"]]
        roles = set(card["endorsements"])
        card["quorum"] = "A3" in roles and bool(roles & {"A1", "A4"}) and not card["open_objections"] and not card["open_conflicts"] and not card["gaps"]
        card["state"] = "REGISTRADO" if card["registration"] or card["legacy_test_ref"] else "NAO_TESTAVEL" if card["classification"] == "NAO_TESTAVEL" else "CONTESTADO" if card["open_objections"] or card["open_conflicts"] else "CONGELADO" if card["freeze"] else "ENDOSSADO" if card["quorum"] else "ESPECIFICADO" if card["spec"] else "ABERTO"
        card["pressure"] = 0.0 if card["freeze"] else sum(float(s.get("weight", 1)) * 2 ** (-max(0, (utc(now)-utc(s["at"])).total_seconds()) / 86400) for s in card["signals"])
        card["next_owner"] = "A2" if card["gaps"] else "A3" if card["open_objections"] or "A3" not in roles else "A4" if card["open_conflicts"] else "A1" if not roles & {"A1", "A4"} else "A5"
        card["charge_key"] = digest([card["id"], card["last_material_event"], card["next_owner"], card["gaps"], card["open_objections"], card["open_conflicts"]])
        card["stale"] = card["state"] not in {"REGISTRADO", "NAO_TESTAVEL"} and (utc(now)-utc(card["last_material_at"])).total_seconds() > 7200
        card['pulses_without_progress'] = sum(s['sequence']>card.get('last_material_sequence',1) and not s.get('charge_key') for s in card['signals'])
    return {"contract": CONTRACT, "access": "PRIVATE", "head": head, "closed": closed, "cards": cards, "events": events, "independent_human_reviewers": 0, "logical_roles_one_owner": True, "execution_triggered": False}

def validate_event(root, payload, role, created_at, events):
    need(role in ROLES and isinstance(payload, dict), "LOGICAL_ROLE_INVALID")
    allowed = {"event_id", "event_type", "scope_id", "scope_version", "card_id", "spec_version", "expected_head", "body", "sources"}
    need(not set(payload) - allowed and "expected_head" in payload and "sources" in payload, "EVENT_FIELDS_INVALID")
    need(SAFE.fullmatch(str(payload.get("event_id", ""))), "EVENT_ID_INVALID")
    kind = payload.get("event_type")
    need(kind in ROLE_EVENTS[role], "EVENT_ROLE_FORBIDDEN")
    utc(created_at)
    scope_source(root, payload.get("scope_id"), payload.get("scope_version"))
    view = derive(events)
    existing = next((e for e in events if e["event_id"] == payload["event_id"]), None)
    if existing:
        original = {k: existing.get(k) for k in allowed if k in existing}
        original["expected_head"] = existing["previous_hash"]
        need(original == payload and existing["role"] == role and existing["created_at"] == created_at, "EVENT_ID_CONFLICT")
        return existing
    need(payload["expected_head"] == view["head"], "BOARD_HEAD_CHANGED")
    need(not view["closed"], "SCOPE_FINISHED")
    sources = source_refs(root, payload.get("sources", []))
    body = payload.get("body")
    need(isinstance(body, dict), "EVENT_BODY_INVALID")
    canonical(body)
    cid = payload.get("card_id")
    card = view["cards"].get(cid)
    sv = payload.get("spec_version")
    if kind not in {"CANARIO", "FIM"}:
        need(isinstance(cid, str) and SAFE.fullmatch(cid), "CARD_ID_INVALID")
    if kind in {"CLAIM", "EMERGENTE"}:
        need(not card and isinstance(body.get("claim"), str) and body["claim"].strip() and sources, "CLAIM_SOURCE_REQUIRED")
        if body.get("classification") == "NAO_TESTAVEL":
            need(body.get("reason"), "NOT_TESTABLE_REASON_REQUIRED")
        if body.get("legacy_test_ref"):
            legacy = read_json(root, body["legacy_test_ref"])
            need(legacy.get("kind") == "TEST" and legacy.get("id"), "LEGACY_REFERENCE_INVALID")
        if kind == "EMERGENTE":
            origins = body.get("origin_cards", [])
            need(origins and all(i in view["cards"] for i in origins) and body.get("risk"), "EMERGENT_ORIGIN_REQUIRED")
            signature = digest([body["claim"].strip().casefold(), sorted(origins)])
            need(not any(c.get("emergent") and digest([c["claim"].strip().casefold(), sorted(next(e["body"].get("origin_cards", []) for e in events if e["event_id"] == c["origin"]) )]) == signature for c in view["cards"].values()), "EMERGENT_DUPLICATE")
    elif kind == "FIM":
        need(view["cards"] and all(c["state"] in {"REGISTRADO", "NAO_TESTAVEL"} and not c["open_objections"] and not c["open_conflicts"] for c in view["cards"].values()), "SCOPE_WORK_REMAINS")
    elif kind != "CANARIO":
        need(card is not None, "CARD_NOT_FOUND")
        need(not card["legacy_test_ref"], "LEGACY_REFERENCE_IMMUTABLE")
        if kind == "SPEC":
            need(not card["registration"] and sv == card["spec_version"] + 1 and type(sv) is int and isinstance(body.get("spec"), dict), "SPEC_VERSION_INVALID")
            need(isinstance(body["spec"].get("question"), str) and body["spec"]["question"].strip(), "SPEC_QUESTION_REQUIRED")
            need(digest(body['spec']) != card['spec_sha256'], 'SPEC_UNCHANGED')
        elif kind in {"OBJECAO", "RESPOSTA", "ENDOSSO", "FREEZE", "REGISTRO"}:
            need(card["spec"] is not None and type(sv) is int and sv == card["spec_version"], "SPEC_VERSION_CHANGED")
        if kind in {"OBJECAO", "RESPOSTA", "CONFLITO", "LICAO"}:
            need(isinstance(body.get("text"), str) and body["text"].strip(), "MATERIAL_TEXT_REQUIRED")
        if kind == "RESPOSTA":
            need(body.get("objection_id") in card["objections"] and sources, "OBJECTION_RESPONSE_SOURCE_REQUIRED")
        if kind == "ENDOSSO":
            need(body.get("rationale"), "ENDORSEMENT_REASON_REQUIRED")
            need(isinstance(body.get('resolves', []), list), 'ENDORSEMENT_RESOLUTION_INVALID')
            need(role not in card['endorsements'] or body.get('resolves'), 'ENDORSEMENT_ALREADY_CURRENT')
            for oid in body.get("resolves", []):
                objection = card["objections"].get(oid)
                need(objection and objection["author"] == role and not objection["resolved"] and objection["response"] and objection["response"]["spec_version"] == sv, "OBJECTION_AUTHOR_ACCEPTANCE_REQUIRED")
        if kind == "CONFLITO" and body.get("resolves"):
            conflict = card["conflicts"].get(body["resolves"])
            need(conflict and conflict["author"] == role and not conflict["resolved"] and sources, "CONFLICT_AUTHOR_REQUIRED")
        if kind == "LINK":
            need(body.get("target_card") in view["cards"] and body["target_card"] != cid and body.get("relation") and body.get("reason") and sources, "LINK_EVIDENCE_REQUIRED")
        if kind == "SINAL":
            weight = body.get("weight", 1)
            need(type(weight) in {float, int} and 0 <= weight <= 100, "SIGNAL_WEIGHT_INVALID")
            if body.get("charge_key"):
                need(card["stale"] and card['pulses_without_progress']>=2 and body["charge_key"] == card["charge_key"] and all(body.get(k) for k in ("pending", "owner", "last_evidence", "next_action")), "CHARGE_EVIDENCE_REQUIRED")
                need(body["owner"] == card["next_owner"] and not any(s.get("charge_key") == body["charge_key"] for s in card["signals"]), "CHARGE_DUPLICATE")
        if kind == "FREEZE":
            need(card["quorum"] and body.get("spec_sha256") == card["spec_sha256"], "FREEZE_QUORUM_OR_HASH_INVALID")
            need(not card['freeze'], 'SPEC_ALREADY_FROZEN')
        if kind == "REGISTRO":
            # A freeze is historical evidence, not permission to ignore a later
            # objection. Re-check the current review before confirming readback.
            need(card["quorum"], "REGISTRATION_CURRENT_QUORUM_REQUIRED")
            need(card["freeze"] and body.get("test_id") == registration_id(payload, card), "REGISTRATION_ID_INVALID")
            test = read_json(root, "entities/test/" + body["test_id"] + ".json")
            readback = body.get("readback", {})
            need(isinstance(readback, dict), "CANONICAL_REGISTRATION_READBACK_REQUIRED")
            from .live_tower import LIVE_TOWER_NAME, verify_live_tower
            revision = verify_live_tower(json.loads((root / LIVE_TOWER_NAME).read_bytes()))
            need(readback.get("source_revision") == revision and readback.get("entity_version") == test.get("entity_version") and readback.get("content_sha256") == digest(test), "CANONICAL_REGISTRATION_READBACK_REQUIRED")
            need(test.get("enxame", {}).get("spec_sha256") == card["spec_sha256"] and test.get("scientific_evidence") == [] and not test.get("verdict"), "REGISTRATION_CONTENT_INVALID")
    return {**copy.deepcopy(payload), "sources": sources, "role": role, "created_at": created_at}

def registration_id(payload, card):
    return "T-ENX-" + digest([payload["scope_id"], payload["scope_version"], payload["card_id"], card["spec_version"], card["spec_sha256"]])[:32]

def append_event(root, payload, role, created_at):
    events = load_events(root, payload.get("scope_id"), payload.get("scope_version"))
    row = validate_event(root, payload, role, created_at, events)
    if "sequence" in row:
        return {"accepted": True, "status": "NO_OP", "readback": "PASS", "event_id": row["event_id"], "event_sha256": row["sha256"]}
    row.pop("expected_head", None)
    row.update(contract=CONTRACT, sequence=len(events)+1, previous_hash=events[-1]["sha256"] if events else None, applied_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"), private=True, allowed_roles=[])
    row["sha256"] = digest(row)
    path = fs_path(root, EVENT_ROOT + "/" + digest([row["scope_id"], row["scope_version"], row["event_id"]]) + ".json")
    need(not path.exists(), "EVENT_FILE_CONFLICT")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical(row))
    need(json.loads(path.read_bytes()) == row, "EVENT_READBACK_FAILED")
    return {"accepted": True, "readback": "PASS", "event_id": row["event_id"], "sequence": row["sequence"], "event_sha256": row["sha256"], "scientific_execution": False}

def register_test(root, payload, role):
    need(role == "A5", "REGISTRAR_ROLE_REQUIRED")
    need(set(payload) <= {"scope_id", "scope_version", "card_id", "spec_version", "spec_sha256", "expected_head", "proposed_test_id"}, "REGISTER_FIELDS_INVALID")
    scope = scope_source(root, payload.get("scope_id"), payload.get("scope_version"))
    view = derive(load_events(root, payload.get("scope_id"), payload.get("scope_version")))
    card = view["cards"].get(payload.get("card_id"))
    need(card and not view["closed"] and card["freeze"] and card["quorum"] and payload.get("spec_version") == card["spec_version"] and payload.get("spec_sha256") == card["spec_sha256"], "REGISTER_FROZEN_SPEC_REQUIRED")
    tid = registration_id(payload, card)
    path = entity_path(root, "test", tid)
    if path.is_file():
        current = json.loads(path.read_bytes())
        need(current.get("enxame", {}).get("spec_sha256") == card["spec_sha256"] and current.get("enxame", {}).get("card_id") == card["id"], "REGISTRY_ID_CONFLICT")
        return {"accepted": True, "status": "NO_OP", "readback": "PASS", "test_id": tid, "scientific_execution": False}
    need(payload.get("expected_head") == view["head"], "BOARD_HEAD_CHANGED")
    spec = card["spec"]
    changes = {"id": tid, "kind": "TEST", "status": "DRAFT", "display_name": spec["question"], "question": spec["question"], "domain": "COSMOLOGY", "roadmap_id": payload["scope_id"], "scientific_evidence": [], "recipe": None, "blocker": "EXECUTABLE_RECIPE_AND_DATA_BINDING_REQUIRED", "next_owner": "ADVISOR", "private": True, "allowed_roles": sorted({"LEARNER", "ENGINEER", "ADVISOR", "EXECUTOR", "REFEREE_1", "PITIA", "GUARDIAO"}), "enxame": {"contract": CONTRACT, "scope_id": payload["scope_id"], "scope_version": payload["scope_version"], "card_id": card["id"], "spec_version": card["spec_version"], "spec_sha256": card["spec_sha256"], "freeze_event": card["freeze"]["event_id"], "spec": spec, "execution_authorization": "SEPARATE_EXISTING_WRITER_RESERVATION"}}
    changes.update({key: spec[key] for key in ("null", "rival", "method", "dataset_and_selection", "success_criteria", "kill_criteria")})
    from . import evolution, scientific_integrity
    changes['domain'] = str(scope.get('domain') or 'COSMOLOGY').upper()
    freeze = next(e for e in load_events(root, payload['scope_id'], payload['scope_version']) if e['event_id'] == card['freeze']['event_id'])
    changes.update(frozen_at=freeze['applied_at'], prereg_ref=EVENT_ROOT+'/'+digest([freeze['scope_id'],freeze['scope_version'],freeze['event_id']])+'.json', claim_boundary=spec.get('claim_boundary') or 'Teste preparado; nenhum resultado científico registrado.')
    changes['prereg_hash'] = evolution.prereg_hash(tid, changes)
    changes['readiness'] = scientific_integrity.readiness(root, changes)
    changes['preparation'] = {'contract':CONTRACT,'phase':'SPEC_FROZEN_RECIPE_PENDING','recipe_exists':False,'inputs_bound':False,'implementation':spec['implementation'],'missing':changes['readiness']['reasons'],'next_owner':'ADVISOR','next_action':'Ligar receita executável, versões e inputs; validar a política de execução e reservar separadamente.','execution_policy':'EXISTING_PUBLIC_RECIPE_ONLY; PRIVATE_PREPARATION_REQUIRES_EXPLICIT_AUTHORIZED_SCOPE_REVIEW'}
    from .tower_apply import apply_requests
    receipt = apply_requests(root, [{"request_id": "REQ-" + tid, "entity_kind": "test", "entity_name": tid, "writer_role": "LEARNER", "expected_version": 0, "event_type": "TEST_PREPARED", "changes": changes}])[0]
    need(receipt.get("accepted", True) and not receipt.get("issue"), "REGISTRY_WRITER_REJECTED:" + str(receipt.get("issue", {}).get("code", "")))
    current = json.loads(path.read_bytes())
    need(current.get("status") == "DRAFT" and current.get("scientific_evidence") == [], "PREPARATION_READBACK_FAILED")
    return {**receipt, "test_id": tid, "spec_sha256": card["spec_sha256"], "scientific_execution": False, "registry_path": "entities/test/" + tid + ".json", "entity_content_sha256": digest(current)}

def apply(root, request):
    if request["nexo_operation"] == "ENXAME_REGISTER_TEST":
        return register_test(root, request["payload"], request["role"])
    return append_event(root, request["payload"], request["role"], request["created_at"])
