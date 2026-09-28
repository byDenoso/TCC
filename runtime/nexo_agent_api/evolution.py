"""Closed-loop evolution layer: roadmap charters, refutation, genome, thoughts, decoys.

The GPT tasks feed each other through the inbox; this module turns their proposals
into Tower writes. Dener only acts at two gates: approving a roadmap CHARTER and
CANONIZING a canary gene. Everything here is pure over a materialized Tower root.

Documents (all under evolution/ except charters, which live in the roadmap):
  roadmaps/<id>.json      charter {status PROPOSED|CHARTERED|CLOSED, question, budget, stop, ...}
  evolution/genome.json   {generation, genes[], lineage[], fitness[]}
  evolution/thoughts.json {entries[]}  (Pítia's diary; every entry must cite Tower ids)
  evolution/decoys.json   {planted[], revealed[]}

Result review ladder: PROMOTED -> PENDING_REVIEW -> (CONTESTED) -> REFEREE1_PASSED -> CONFIRMED, or REFUTED.
Referee 1 = GPT Refutador; Referee 2 = Claude (external model). Only CONFIRMED counts for stop criteria/fitness.
"""

from __future__ import annotations

import hashlib
import base64
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .semantics import is_private, resolve as resolve_semantic
from .tower_paths import entity_path, fs_path

MAX_CONTESTS = 1
MAX_CONTEST_DEPTH = 1
POSITIVE_VERDICTS = {"PROMOTED", "SUPPORTED"}
# The spine: never a gene, never a canary. Changes here are recommendations to Dener only.
SPINE_PREFIXES = ("contract", "writer", "frozen", "criteria", "fitness", "spine", "privacy", "gate")
GENOME_DOC = "evolution/genome.json"
THOUGHTS_DOC = "evolution/thoughts.json"
DECOYS_DOC = "evolution/decoys.json"
BATTERIES_DOC = "evolution/batteries.json"
INCIDENTS_DOC = "evolution/incidents.json"
MAX_BATTERY_TESTS = 20


def _read(root: Path, relative: str) -> dict[str, Any]:
    path = fs_path(root, relative)
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


def _entity(root: Path, kind: str, entity_id: str) -> dict[str, Any] | None:
    path = entity_path(root, kind, entity_id)
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None


def _now(item: dict[str, Any]) -> str:
    return str(item.get("created_at") or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))


def _doc(relative: str, merge: dict[str, Any], rid: str, list_merge: dict[str, str] | None = None) -> dict[str, Any]:
    request = {"request_id": rid, "document": relative, "merge": merge}
    if list_merge:
        request["list_merge"] = list_merge
    return request


def _test_update(root: Path, test_id: str, changes: dict[str, Any], rid: str, event: str) -> dict[str, Any] | None:
    current = _entity(root, "test", test_id)
    if current is None:
        return None
    return {"request_id": rid, "entity_kind": "test", "entity_name": test_id,
            "expected_version": int(current.get("entity_version") or 0),
            "writer_role": "ADVISOR", "event_type": event, "changes": changes}


def prereg_hash(test_id: str, fields: dict[str, Any]) -> str:
    """Public pre-registration fingerprint of the frozen design (committed in the inbox before any run)."""
    frozen = {k: fields.get(k) for k in ("question", "null", "rival", "method", "dataset_and_selection",
                                         "success_criteria", "kill_criteria", "claim_boundary")}
    blob = json.dumps({"test_id": test_id, **frozen}, ensure_ascii=False, sort_keys=True, default=str)
    return "sha256:" + hashlib.sha256(blob.encode("utf-8")).hexdigest()


# ── Gate 1: roadmap charters ────────────────────────────────────────────────

def charter_requests(item: dict[str, Any], body: dict[str, Any], root: Path) -> list[dict[str, Any]]:
    rid = str(body.get("roadmap_id") or "").strip()
    if not rid:
        slug = "".join(c if c.isalnum() else "-" for c in str(body.get("question") or "NOVO").upper())[:40].strip("-")
        rid = f"RM-{slug}-{_now(item)[:10].replace('-', '')}-V1"
    existing = _read(root, f"roadmaps/{rid}.json")
    if (existing.get("charter") or {}).get("status") in {"CHARTERED", "CLOSED"}:
        return []  # a signed charter is frozen like test criteria
    charter = {
        "status": "PROPOSED",
        "question": body.get("question"),
        "scope": body.get("scope"),
        "data": body.get("data"),
        "budget": body.get("budget") or {"max_tests": 40, "max_days": 21},
        "stop": body.get("stop") or {"success_confirmed": 3, "kill_consecutive_refuted": 6},
        "rationale": body.get("rationale"),
        "refs": body.get("refs") or [],
        "rival_of": body.get("rival_of"),
        "renewable": bool(body.get("renewable")),
        "review_every_days": body.get("review_every_days"),
        "objectives": body.get("objectives"),
        "priority": body.get("priority"),
        "proposed_by": body.get("proposed_by") or item.get("source") or "PITIA",
        "proposed_at": _now(item),
    }
    merge: dict[str, Any] = {"charter": {k: v for k, v in charter.items() if v not in (None, "", [])}}
    semantic = body.get("semantic")
    if isinstance(semantic, dict):
        plain_semantic = {k: v for k, v in semantic.items() if v not in (None, "", [])}
        if plain_semantic:
            merge["semantic"] = plain_semantic
    if not existing:
        merge.update({"roadmap_id": rid, "status": "PROPOSED", "frontier_refs": [],
                      "title": body.get("title") or body.get("question"), "domain": body.get("domain")})
    return [_doc(f"roadmaps/{rid}.json", merge, f"REQ-CHARTER-{rid}")]


def _gate_is_dener(item: dict[str, Any], body: dict[str, Any]) -> bool:
    # Gate authority comes from the envelope source, never from a field an
    # unattended task could self-assert inside the payload.
    return str(item.get("source") or "").upper() == "DENER"


def operator_requests(item: dict[str, Any], body: dict[str, Any], root: Path) -> list[dict[str, Any]] | None:
    """Dener's gate actions. Returns None when the intent is not a gate action (caller records it)."""
    action = str(body.get("action") or "").upper()
    if action not in {"APPROVE_CHARTER", "REJECT_CHARTER", "CANONIZE", "REJECT_CANARY"}:
        return None
    if not _gate_is_dener(item, body):
        return None  # only Dener opens the gates; anything else is just recorded
    at = _now(item)
    if action in {"APPROVE_CHARTER", "REJECT_CHARTER"}:
        rid = str(body.get("roadmap_id") or "")
        roadmap = _read(root, f"roadmaps/{rid}.json")
        if not roadmap.get("charter"):
            return None
        if action == "REJECT_CHARTER":
            return [_doc(f"roadmaps/{rid}.json", {"charter": {"status": "REJECTED", "decided_at": at}}, f"REQ-CHARTER-REJECT-{rid}")]
        charter = dict(roadmap["charter"])
        charter.update({"status": "CHARTERED", "chartered_at": at, "approved_by": "DENER"})
        frozen = {k: charter.get(k) for k in ("question", "scope", "data", "budget", "stop")}
        charter["charter_hash"] = "sha256:" + hashlib.sha256(json.dumps(frozen, sort_keys=True, default=str).encode()).hexdigest()
        return [
            _doc(f"roadmaps/{rid}.json", {"charter": charter, "status": "ACTIVE"}, f"REQ-CHARTER-APPROVE-{rid}"),
            _doc("indexes/active-roadmaps.json",
                 {"items": [{"roadmap_id": rid, "state": "ACTIVE", "priority": body.get("priority") or charter.get("priority") or "NORMAL",
                             "relative_path": f"roadmaps/{rid}.json"}]},
                 f"REQ-INDEX-ACTIVATE-{rid}", {"items": "roadmap_id"}),
        ]
    gene = str(body.get("gene") or "")
    genome = _read(root, GENOME_DOC)
    current = next((g for g in genome.get("genes") or [] if g.get("id") == gene), None)
    if not current or current.get("status") != "CANARY":
        return None
    if action == "REJECT_CANARY":
        return [_doc(GENOME_DOC, {"genes": [{"id": gene, "status": "CANONICAL", "canary": None,
                                               "incident_id": None, "canary_id": None,
                                               "last_decision": {"action": "REJECTED", "at": at,
                                                                 "incident_id": current.get("incident_id"),
                                                                 "canary_id": current.get("canary_id")}}]},
                     f"REQ-GENE-REJECT-{gene}", {"genes": "id"})]
    generation = int(genome.get("generation") or 0) + 1
    return [_doc(GENOME_DOC, {
        "generation": generation,
        "genes": [{"id": gene, "status": "CANONICAL", "canonical": current.get("canary"), "canary": None,
                   "incident_id": None, "canary_id": None,
                   "last_decision": {"action": "CANONIZED", "at": at, "generation": generation,
                                     "incident_id": current.get("incident_id"),
                                     "canary_id": current.get("canary_id")}}],
        "lineage": (genome.get("lineage") or []) + [{"generation": generation, "gene": gene, "from": current.get("canonical"),
                                                     "to": current.get("canary"), "at": at, "rationale": current.get("rationale"),
                                                     "evidence": body.get("evidence")}],
    }, f"REQ-GENE-CANONIZE-{gene}", {"genes": "id"})]


def close_requests(item: dict[str, Any], body: dict[str, Any], root: Path) -> list[dict[str, Any]]:
    rid = str(body.get("roadmap_id") or "")
    roadmap = _read(root, f"roadmaps/{rid}.json")
    if not roadmap or (roadmap.get("charter") or {}).get("status") == "CLOSED":
        return []
    closed = {"status": "CLOSED", "closed_at": _now(item), "close_reason": str(body.get("reason") or "BUDGET").upper(),
              "final_report": body.get("final_report") or body.get("evidence")}
    return [
        _doc(f"roadmaps/{rid}.json", {"charter": closed, "status": "CLOSED"}, f"REQ-ROADMAP-CLOSE-{rid}"),
        _doc("indexes/active-roadmaps.json", {"items": [{"roadmap_id": rid, "state": "CLOSED"}]},
             f"REQ-INDEX-CLOSE-{rid}", {"items": "roadmap_id"}),
    ]


# ── Refutation (Referee 1 = GPT, Referee 2 = Claude, Sentinel = world) ──────

def contest_requests(item: dict[str, Any], body: dict[str, Any], root: Path, hypothesis_fn) -> list[dict[str, Any]]:
    test_id = str(body.get("test_id") or "")
    current = _entity(root, "test", test_id)
    if current is None:
        return []
    # An attack is evidence about the original test and is never itself attackable.
    if current.get("contests_test_id"):
        return []
    contests = list(current.get("contests") or [])
    if len(contests) >= MAX_CONTESTS or current.get("review_state") in {"CONFIRMED", "REFUTED"} and body.get("source") != "SENTINEL":
        return []
    requests: list[dict[str, Any]] = []
    attack = body.get("contest_test") if isinstance(body.get("contest_test"), dict) else None
    attack_id = None
    if attack:
        attack_no = len(contests) + 1
        attack_id = str(attack.get("test_id") or f"CONTEST-{test_id}-{attack_no}")
        parent_semantic = current.get("semantic") if isinstance(current.get("semantic"), dict) else {}
        attack_semantic = attack.get("semantic") if isinstance(attack.get("semantic"), dict) else {}
        parent_name = str(current.get("display_name") or parent_semantic.get("display_name") or
                          parent_semantic.get("question_plain") or current.get("question") or "Teste atacado")
        natural_name = f"Ataque {attack_no} · {' '.join(parent_name.split()[:5])}"
        domain = str(attack.get("domain") or current.get("domain") or parent_semantic.get("domain_id") or "").strip()
        requests += hypothesis_fn(item, {**attack, "test_id": attack_id, "contests_test_id": test_id,
                                         "roadmap_id": attack.get("roadmap_id") or current.get("roadmap_id"),
                                         "incident_id": current.get("incident_id"),
                                         "priority": "P0", "display_name": natural_name, "domain": domain,
                                         "semantic": {**parent_semantic, **attack_semantic,
                                                      "display_name": natural_name,
                                                      "domain_id": str(domain).lower()}}, root)
    entry = {"n": len(contests) + 1, "by": str(body.get("source") or body.get("referee") or "REFEREE_1").upper(),
             "reason": body.get("reason"), "contest_test_id": attack_id, "incident_id": current.get("incident_id"),
             "at": _now(item), "refs": body.get("refs")}
    update = _test_update(root, test_id, {"review_state": "CONTESTED", "contests": contests + [entry]},
                          f"REQ-CONTEST-{test_id}-{len(contests) + 1}", "RESULT_CONTESTED")
    return requests + ([update] if update else [])


def review_requests(item: dict[str, Any], body: dict[str, Any], root: Path) -> list[dict[str, Any]]:
    test_id = str(body.get("test_id") or "")
    current = _entity(root, "test", test_id)
    if current is None or current.get("review_state") in {"CONFIRMED", "REFUTED"}:
        return []
    referee = "2" if str(body.get("referee") or "1").strip().upper() in {"2", "REFEREE_2", "CLAUDE"} else "1"
    outcome = str(body.get("outcome") or "").upper()
    reviews = list(current.get("reviews") or []) + [{"referee": referee, "outcome": outcome, "evidence": body.get("evidence"),
                                                     "contest_test_id": body.get("contest_test_id"), "at": _now(item)}]
    passed = {r["referee"] for r in reviews if r.get("outcome") == "SURVIVED"}
    # Referee 2 (external model) is optional: surviving two independent contest tests from Referee 1 also confirms.
    survived_contests = {r.get("contest_test_id") for r in reviews
                         if r.get("referee") == "1" and r.get("outcome") == "SURVIVED" and r.get("contest_test_id")}
    if outcome == "REFUTED":
        state = "REFUTED"
    elif {"1", "2"} <= passed or len(survived_contests) >= 2:
        state = "CONFIRMED"
    elif "1" in passed:
        state = "REFEREE1_PASSED"
    else:
        state = current.get("review_state") or "PENDING_REVIEW"
    update = _test_update(root, test_id, {"review_state": state, "reviews": reviews},
                          f"REQ-REVIEW-{test_id}-R{referee}-{len(reviews)}", f"RESULT_{state}")
    return [update] if update else []


def _contest_depth(root: Path, test: dict[str, Any]) -> int:
    depth, seen, current = 0, set(), test
    while current.get("contests_test_id"):
        parent_id = str(current.get("contests_test_id") or "")
        if not parent_id or parent_id in seen:
            break
        seen.add(parent_id)
        depth += 1
        parent = _entity(root, "test", parent_id)
        if parent is None:
            break
        current = parent
    return depth


def _attack_outcome(test: dict[str, Any]) -> str | None:
    """Map the attack test's frozen criterion result onto the attacked test."""
    verdict = str(test.get("verdict") or "").upper()
    decision = str(test.get("decision") or "").upper()
    if verdict in {"REJECTED", "FAILED", "FALSIFIED"} or decision in {"REFUTED", "FAILED", "FALSIFIED"}:
        return "REFUTED"
    if verdict in POSITIVE_VERDICTS or decision in {"SURVIVED", "CONFIRMED", "PASS", "PASSED"}:
        return "CONFIRMED"
    return None


def contest_chain_reconcile_requests(root: str | Path) -> list[dict[str, Any]]:
    """Enforce depth=1 and close originals mechanically from completed attacks."""
    root = Path(root)
    tests = _tests(root)
    by_id = {str(test.get("id")): test for test in tests if test.get("id")}
    requests: list[dict[str, Any]] = []
    for test in tests:
        if _contest_depth(root, test) <= MAX_CONTEST_DEPTH:
            continue
        if str(test.get("state") or test.get("status") or "").upper() == "ARCHIVED":
            continue
        update = _test_update(root, str(test.get("id") or ""), {
            "status": "ARCHIVED", "state": "ARCHIVED", "review_state": "ARCHIVED",
            "archive_reason": "contest_depth_exceeded", "execution": None,
        }, f"REQ-CONTEST-ARCHIVE-{test.get('id')}", "CONTEST_CHAIN_ARCHIVED")
        if update:
            requests.append(update)
    candidates: dict[str, list[dict[str, Any]]] = {}
    for attack in tests:
        parent_id = str(attack.get("contests_test_id") or "")
        if not parent_id or _contest_depth(root, attack) != 1 or _attack_outcome(attack) is None:
            continue
        candidates.setdefault(parent_id, []).append(attack)
    for parent_id, attacks in sorted(candidates.items()):
        parent = by_id.get(parent_id)
        if not parent or parent.get("contests_test_id") or parent.get("review_state") in {"CONFIRMED", "REFUTED"}:
            continue
        attacks.sort(key=lambda attack: (str(attack.get("executed_at") or ""), str(attack.get("id") or "")))
        attack = attacks[0]
        outcome = _attack_outcome(attack)
        update = _test_update(root, parent_id, {
            "review_state": outcome,
            "mechanical_contest_verdict": {
                "contest_test_id": attack.get("id"), "outcome": outcome,
                "rule": "FROZEN_ATTACK_CRITERION_V1",
                "at": attack.get("executed_at") or attack.get("updated_at"),
            },
        }, f"REQ-CONTEST-MECHANICAL-{parent_id}", f"RESULT_{outcome}")
        if update:
            requests.append(update)
    return requests


# ── Genome: canary mutations, rollback, fitness ─────────────────────────────

def _spine(gene: str) -> bool:
    return gene.lower().replace("-", "_").startswith(SPINE_PREFIXES)


def mutation_requests(item: dict[str, Any], body: dict[str, Any], root: Path) -> list[dict[str, Any]]:
    gene = str(body.get("gene") or "").strip()
    if not gene or _spine(gene):
        return []  # the spine is not evolvable; the caller records the proposal as a recommendation
    incident_id = resolve_incident_id(root, body.get("incident_id"), refs=body.get("refs") or [])
    if body.get("incident_id") and not incident_id:
        return []  # never attach a canary to an ungrounded incident id
    if incident_id and any(item.get("incident_id") == incident_id and item.get("state") == "CLOSED"
                           for item in _incident_registry(root)):
        return []  # terminal incidents never reopen through a new canary/mutation
    if incident_id and not incident_confirmed(root, incident_id):
        return []  # causal canaries require an actually CONFIRMED test, never a declared state
    genome = _read(root, GENOME_DOC)
    current = next((g for g in genome.get("genes") or [] if g.get("id") == gene), None)
    if current and current.get("status") == "CANARY":
        return []  # one canary per gene at a time
    if body.get("seed"):
        # Initial genome (generation 0): canonical values, no canary; ignored once the gene exists.
        if current:
            return []
        merge = {"genes": [{"id": gene, "status": "CANONICAL", "canonical": body.get("value"), "canary": None,
                            "rationale": body.get("rationale"), "seeded_at": _now(item)}]}
        if "generation" not in genome:
            merge["generation"] = 0
        return [_doc(GENOME_DOC, merge, f"REQ-GENE-SEED-{gene}", {"genes": "id"})]
    entry = {"id": gene, "status": "CANARY", "canary": body.get("value"), "canary_since": _now(item),
             "rationale": body.get("rationale"), "refs": body.get("refs") or [], "proposed_by": item.get("source") or body.get("proposed_by"),
             "metric": body.get("metric") or "confirmed_per_test", "scope": body.get("scope") or "GLOBAL"}
    if incident_id:
        seed = json.dumps({"gene": gene, "incident_id": incident_id, "value": body.get("value")},
                          ensure_ascii=False, sort_keys=True, default=str)
        entry["incident_id"] = incident_id
        entry["canary_id"] = "CANARY-" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:12].upper()
    if not current:
        entry["canonical"] = body.get("current_value")
    merge: dict[str, Any] = {"genes": [entry]}
    if "generation" not in genome:
        merge["generation"] = 0
    return [_doc(GENOME_DOC, merge, f"REQ-GENE-CANARY-{gene}-{_now(item)[:13]}", {"genes": "id"})]


def rollback_requests(item: dict[str, Any], body: dict[str, Any], root: Path) -> list[dict[str, Any]]:
    gene = str(body.get("gene") or "")
    genome = _read(root, GENOME_DOC)
    current = next((g for g in genome.get("genes") or [] if g.get("id") == gene), None)
    if not current or current.get("status") != "CANARY":
        return []
    history = list(current.get("rolled_back") or []) + [{"value": current.get("canary"), "at": _now(item), "reason": body.get("reason"),
                                                        "fitness": body.get("fitness"),
                                                        "incident_id": current.get("incident_id"),
                                                        "canary_id": current.get("canary_id")}]
    return [_doc(GENOME_DOC, {"genes": [{"id": gene, "status": "CANONICAL", "canary": None,
                                         "incident_id": None, "canary_id": None, "rolled_back": history}]},
                 f"REQ-GENE-ROLLBACK-{gene}-{_now(item)[:13]}", {"genes": "id"})]


def fitness_requests(item: dict[str, Any], body: dict[str, Any], root: Path) -> list[dict[str, Any]]:
    genome = _read(root, GENOME_DOC)
    genes = {str(g.get("id")): g for g in genome.get("genes") or [] if isinstance(g, dict) and g.get("id")}

    def enrich(measurement: dict[str, Any]) -> dict[str, Any]:
        row = dict(measurement, at=_now(item), generation=int(genome.get("generation") or 0))
        gene = genes.get(str(row.get("gene") or ""))
        if gene and gene.get("status") == "CANARY":
            if gene.get("incident_id"):
                row.setdefault("incident_id", gene.get("incident_id"))
            if gene.get("canary_id"):
                row.setdefault("canary_id", gene.get("canary_id"))
        return row

    rows = [enrich(m) for m in body.get("measurements") or [] if isinstance(m, dict)]
    if body.get("value") is not None:
        rows.append(enrich({"gene": body.get("gene"), "arm": body.get("arm") or "canonical",
                            "value": body.get("value"), "components": body.get("components")}))
    if not rows:
        return []
    return [_doc(GENOME_DOC, {"fitness": (genome.get("fitness") or [])[-500:] + rows}, f"REQ-FITNESS-{_now(item)[:16]}")]


# ── Pítia's diary and decoys ────────────────────────────────────────────────

def thought_requests(item: dict[str, Any], body: dict[str, Any], root: Path) -> list[dict[str, Any]]:
    raw = body.get("entries") or ([body] if body.get("text") else [])
    entries = []
    for index, entry in enumerate(raw):
        if not isinstance(entry, dict) or not entry.get("text") or not entry.get("refs"):
            continue  # a thought without Tower ids is decoration, not evidence
        entries.append({"id": entry.get("id") or f"TH-{_now(item)[:16]}-{index}", "at": _now(item),
                        "kind": str(entry.get("kind") or "SURPRISE").upper(), "text": str(entry["text"])[:600],
                        "refs": [str(r) for r in entry["refs"]][:12]})
    retire = {str(r) for r in body.get("retire") or []}
    if not entries and not retire:
        return []
    old = _read(root, THOUGHTS_DOC).get("entries") or []
    # Retired thoughts stay in the history (nothing is deleted) but leave the public diary.
    old = [dict(e, retired=True) if e.get("id") in retire else e for e in old]
    seen = {" ".join(str(e.get("text") or "").split()).lower() for e in old}
    entries = [e for e in entries if " ".join(e["text"].split()).lower() not in seen]  # a re-sent thought is not a new one
    if not entries and not retire:
        return []
    return [_doc(THOUGHTS_DOC, {"entries": (old + entries)[-300:]}, f"REQ-THOUGHT-{_now(item)[:16]}")]


def decoy_requests(item: dict[str, Any], body: dict[str, Any], root: Path, kind: str) -> list[dict[str, Any]]:
    decoys = _read(root, DECOYS_DOC)
    if kind == "DECOY_CALL":
        # Any task that suspects a result is a planted decoy says so publicly; it counts as caught at reveal.
        test_id = str(body.get("test_id") or "")
        if not test_id:
            return []
        calls = (decoys.get("calls") or []) + [{"test_id": test_id, "by": item.get("source") or body.get("by"),
                                                "reason": body.get("reason"), "at": _now(item)}]
        return [_doc(DECOYS_DOC, {"calls": calls[-200:]}, f"REQ-DECOY-CALL-{test_id}-{_now(item)[:16]}")]
    if kind == "DECOY_PLANT":
        commitment = str(body.get("commitment") or "").lower().removeprefix("sha256:")
        if len(commitment) != 64:
            return []
        return [_doc(DECOYS_DOC, {"planted": (decoys.get("planted") or []) + [{"commitment": commitment, "at": _now(item)}]},
                     f"REQ-DECOY-PLANT-{commitment[:12]}")]
    test_id, secret = str(body.get("test_id") or ""), str(body.get("secret") or "")
    digest = hashlib.sha256(f"{test_id}:{secret}".encode("utf-8")).hexdigest()
    planted = {d.get("commitment") for d in decoys.get("planted") or []}
    test = _entity(root, "test", test_id)
    if digest not in planted or test is None:
        return []
    called = any(c.get("test_id") == test_id for c in decoys.get("calls") or [])
    caught = called or test.get("review_state") in {"CONTESTED", "REFUTED"} or str(test.get("verdict") or "").upper() not in POSITIVE_VERDICTS
    requests = [_doc(DECOYS_DOC, {"revealed": (decoys.get("revealed") or []) + [{"test_id": test_id, "caught": caught, "at": _now(item),
                                                                                 "commitment": digest}]}, f"REQ-DECOY-REVEAL-{test_id}")]
    update = _test_update(root, test_id, {"decoy": True, "review_state": "REFUTED", "decoy_caught": caught},
                          f"REQ-DECOY-MARK-{test_id}", "DECOY_REVEALED")
    return requests + ([update] if update else [])


# ── Test batteries: the Executor dispatches, GitHub Actions computes (public, free, parallel) ──

def battery_requests(item: dict[str, Any], body: dict[str, Any], root: Path) -> list[dict[str, Any]]:
    """TEST_BATTERY uses only reviewed recipe+params; inline code is forbidden."""
    doc = _read(root, BATTERIES_DOC)
    batteries = list(doc.get("batteries") or [])
    bid = str(body.get("battery_id") or f"bat-{_now(item)[:19].replace(':', '').replace('-', '')}").lower()
    bid = "".join(c if c.isalnum() or c == "-" else "-" for c in bid)[:48]
    if any(b.get("id") == bid for b in batteries):
        return []
    tests, requests = [], []
    for spec in (body.get("tests") or [])[:MAX_BATTERY_TESTS]:
        test_id = str(spec.get("test_id") or "")
        current = _entity(root, "test", test_id) if test_id else None
        recipe = str(spec.get("recipe") or "").strip()
        if current is None or spec.get("script") or not re.fullmatch(r"[a-z0-9_]{2,40}", recipe):
            continue
        if str(current.get("domain") or "").upper() == "OLYMPUS" or current.get("private"):
            continue
        params = spec.get("params") if isinstance(spec.get("params"), dict) else {}
        tests.append({"test_id": test_id, "recipe": recipe, "params": params,
                      "timeout_min": max(1, min(int(spec.get("timeout_min") or 30), 340)),
                      "prediction": spec.get("prediction")})
        changes = {"status": "RUNNING", "state": "RUNNING", "execution": "GITHUB_ACTIONS_BATTERY",
                   "battery_id": bid, "execution_recipe": recipe}
        if spec.get("prediction") and not current.get("prediction"):
            changes["prediction"] = spec["prediction"]
        update = _test_update(root, test_id, changes, f"REQ-BATTERY-{bid}-{test_id}", "TEST_DISPATCHED")
        if update:
            requests.append(update)
    if not tests:
        return []
    batteries.append({"id": bid, "status": "QUEUED", "created_at": _now(item), "source": item.get("source"), "tests": tests})
    return [_doc(BATTERIES_DOC, {"batteries": batteries[-200:]}, f"REQ-BATTERY-{bid}")] + requests

def battery_status_requests(item: dict[str, Any], body: dict[str, Any], root: Path, result_fn) -> list[dict[str, Any]]:
    """BATTERY_STATUS {battery_id, status DISPATCHED|DONE, run_id?, results:[{test_id, ok, result, semantic, log_tail}]}."""
    doc = _read(root, BATTERIES_DOC)
    batteries = list(doc.get("batteries") or [])
    bid, status = str(body.get("battery_id") or ""), str(body.get("status") or "").upper()
    index = next((i for i, b in enumerate(batteries) if b.get("id") == bid), None)
    if index is None or batteries[index].get("status") == "DONE" or status not in {"DISPATCHED", "DONE", "QUEUED"}:
        return []
    battery = dict(batteries[index], status=status)
    requests: list[dict[str, Any]] = []
    if status == "DISPATCHED":
        battery.update({"dispatched_at": _now(item), "run_ref": body.get("run_ref")})
    if status == "DONE":
        ok = bad = 0
        for entry in body.get("results") or []:
            test_id = str(entry.get("test_id") or "")
            if entry.get("ok") and isinstance(entry.get("result"), dict):
                ok += 1
                requests += result_fn(dict(item, _inbox_name=f"{item.get('_inbox_name') or bid}-{test_id}"),
                                      {"test_id": test_id, "result": entry["result"], "semantic": entry.get("semantic") or {},
                                       "reproducibility": {"runner": "GITHUB_ACTIONS", "battery_id": bid, "run_ref": body.get("run_ref"),
                                                           "log_tail": str(entry.get("log_tail") or "")[-1500:]},
                                       "arm": entry.get("arm")}, root)
            else:
                bad += 1  # a crash is never a scientific result: the test goes back to READY
                update = _test_update(root, test_id, {"status": "READY", "state": "READY", "execution": None,
                                                      "last_runtime_failure": {"battery_id": bid, "at": _now(item),
                                                                               "log_tail": str(entry.get("log_tail") or "")[-800:]}},
                                      f"REQ-BATTERY-FAIL-{bid}-{test_id}", "TEST_RUNTIME_FAILURE")
                if update:
                    requests.append(update)
        battery.update({"completed_at": _now(item), "run_ref": body.get("run_ref") or battery.get("run_ref"), "ok": ok, "failed": bad})
    batteries[index] = battery
    return [_doc(BATTERIES_DOC, {"batteries": batteries}, f"REQ-BATTERY-{status}-{bid}")] + requests


def pending_batteries(root: Path, stale_hours: float = 8.0) -> list[dict[str, Any]]:
    """QUEUED batteries, plus DISPATCHED ones that never reported back (lost dispatch): re-dispatched."""
    now = datetime.now(timezone.utc)
    out = []
    for battery in _read(root, BATTERIES_DOC).get("batteries") or []:
        if battery.get("status") == "QUEUED":
            out.append(battery)
        elif battery.get("status") == "DISPATCHED" and battery.get("dispatched_at"):
            try:
                at = datetime.fromisoformat(str(battery["dispatched_at"]).replace("Z", "+00:00"))
            except ValueError:
                continue
            if (now - at).total_seconds() > stale_hours * 3600:
                out.append(battery)
    return out


# ── Read side: what each task needs to know (writer CLI `status`) ───────────

def _tests(root: Path) -> list[dict[str, Any]]:
    folder = root / "entities" / "test"
    out = []
    for path in sorted(folder.glob("*.json")) if folder.is_dir() else []:
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except ValueError:
            continue
        if isinstance(value, dict):
            out.append(value)
    return out


_CONVERSATION_SIGNAL_SOURCES = {"CHATGPT", "CHATGPT_CONVERSATION", "CONVERSATION", "DENER_CONVERSATION"}
_AUTOMATION_SIGNAL_SOURCES = {
    "CHATGPT_TASK_EXECUTOR", "CHATGPT_TASK_GUARDIAN", "CHATGPT_GUARDIAN", "EXECUTOR", "GUARDIAO",
    "PITIA", "LEARNER", "REFUTADOR",
}

_INCIDENT_PUBLIC_COPY_PT = {
    "WRITER_LAG_PATTERN": "O sistema detectou atrasos repetidos para registrar e confirmar mudanças.",
    "EMPTY_FRONTIER_ACTIVE_ROADMAP": "Uma área de trabalho ativa ficou repetidamente sem um próximo teste pronto para executar.",
}
_INCIDENT_PUBLIC_FALLBACK_PT = "O sistema detectou o mesmo problema operacional mais de uma vez e abriu uma investigação para entender a causa."
_INCIDENT_DETAIL_PT = {
    "INDEPENDENT_EVALUATORS_UNAVAILABLE": ("A verificação exigiu avaliadores independentes, mas o runtime não produziu avaliações independentes elegíveis.", "duas avaliações independentes persistidas sobre a mesma amostra congelada"),
    "RUNNER_ARTIFACT_EXECUTOR_UNAVAILABLE": ("A execução pública terminou sem um artifact científico utilizável e rastreável pelo Executor.", "um artifact válido do runner com proveniência e read-back"),
    "PRE_RESULT_TEMPORAL_ORDER_UNRESOLVED": ("A proveniência não demonstra que a condição pré-registrada ocorreu antes do resultado observado.", "evidência temporal canônica que fixe a ordem entre pré-registro e resultado"),
    "CHECKPOINT_SEQUENCE_OBSERVABILITY_INCOMPLETE": ("A sequência posterior ao checkpoint não está observável por inteiro, então não dá para classificar estagnação com segurança.", "uma sequência posterior completa sem lacunas materiais"),
    "TEST_CREATION_ORDER_UNRESOLVED": ("A ordem canônica de criação dos testes não pode ser reconstruída com a evidência atual.", "proveniência temporal suficiente para ordenar a criação dos testes"),
    "CAMB_RUNTIME_POLICY_DRIFT": ("Um resultado que exige CAMB foi produzido fora do runtime portado exigido para ciência de produção.", "reexecução da mesma definição científica no CAMB portado do runner público"),
}


def _signal_clusters(root: Path, tests: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Read-only shadow groups for repeated stable signal codes; never projects free-text causes."""
    test_by_id = {str(test.get("id")): test for test in tests if test.get("id")}
    private_test_ids = {
        test_id for test_id, test in test_by_id.items()
        if test.get("private") or is_private(resolve_semantic(test, entity_id=test_id))
    }
    groups: dict[str, dict[str, Any]] = {}
    folder = root / "entities" / "artifact"
    for path in sorted(folder.glob("*.json")) if folder.is_dir() else []:
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(record, dict) or str(record.get("kind") or "").upper() != "LEARNING_SIGNAL":
            continue
        if record.get("private") or is_private(record.get("semantic") if isinstance(record.get("semantic"), dict) else {}):
            continue
        source = str(record.get("source") or "").strip().upper()
        if source in _CONVERSATION_SIGNAL_SOURCES:
            source_family = "CONVERSATION"
        elif source in _AUTOMATION_SIGNAL_SOURCES:
            source_family = "AUTOMATION"
        else:
            continue
        payload = record.get("payload") if isinstance(record.get("payload"), dict) else {}
        signals = payload.get("signals") if isinstance(payload.get("signals"), list) else []
        artifact_id = str(record.get("id") or path.stem)
        stamp = str(record.get("created_at") or payload.get("created_at") or "")
        try:
            parsed = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
            parsed = parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
            stamp = parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
        except ValueError:
            stamp = ""
        for signal in signals:
            if not isinstance(signal, dict):
                continue
            raw_code = signal.get("code") or signal.get("signal_code")
            if not isinstance(raw_code, str):
                continue
            code = raw_code.strip().upper()
            if not 3 <= len(code) <= 80 or any(char not in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_" for char in code):
                continue
            semantic = signal.get("semantic") if isinstance(signal.get("semantic"), dict) else {}
            topic_id = signal.get("topic_id") or semantic.get("topic_id")
            signal_semantic = dict(semantic)
            if topic_id:
                signal_semantic["topic_id"] = topic_id
            resolved_semantic = resolve_semantic({"semantic": signal_semantic}, entity_id=artifact_id)
            if is_private(signal_semantic) or is_private(resolved_semantic):
                continue
            resolved_topic = resolved_semantic.get("topic_id")
            test_refs: list[str] = []
            single_test = signal.get("test_id")
            if single_test:
                test_refs.append(str(single_test))
            many_tests = signal.get("test_ids")
            if isinstance(many_tests, list):
                test_refs.extend(str(test_id) for test_id in many_tests if test_id)
            if test_refs and any(test_id not in test_by_id or test_id in private_test_ids for test_id in test_refs):
                continue
            group = groups.setdefault(code, {
                "cluster_id": "SIG-" + hashlib.sha256(code.encode("utf-8")).hexdigest()[:12],
                "code": code, "artifacts": set(), "sources": set(), "topic_ids": set(), "test_ids": set(),
                "timestamps": set(),
            })
            group["artifacts"].add(artifact_id)
            group["sources"].add(source_family)
            if resolved_topic:
                group["topic_ids"].add(resolved_topic)
            group["test_ids"].update(test_refs)
            if stamp:
                group["timestamps"].add(stamp)
    result = []
    for group in groups.values():
        occurrences = len(group["artifacts"])
        if occurrences < 2:
            continue
        timestamps = sorted(group["timestamps"])
        result.append({
            "cluster_id": group["cluster_id"],
            "code": group["code"],
            "occurrences": occurrences,
            "sources": sorted(group["sources"]),
            "topic_ids": sorted(group["topic_ids"])[:8],
            "test_ids": sorted(group["test_ids"])[:12],
            "first_seen": timestamps[0] if timestamps else None,
            "last_seen": timestamps[-1] if timestamps else None,
        })
    return sorted(result, key=lambda cluster: (-cluster["occurrences"], cluster["code"]))[:20]



def _incident_candidates(root: Path, tests: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    """Repeated automation LEARNING_SIGNALs -> deterministic private incident candidates.

    A first incident opens only from >=2 distinct automation artifacts with the
    same normalized stable code and explicit topic_id. Once an incident is
    CLOSED its evidence is frozen: >=2 later, previously unassociated eligible
    artifacts open one deterministic child linked by parent_incident_id.
    Clock/stale pressure and conversation-only evidence are never inputs here.
    """
    tests = tests or _tests(root)
    registry = _incident_registry(root)
    groups: dict[tuple[str, str], dict[str, dict[str, Any]]] = {}
    folder = root / "entities" / "artifact"
    for path in sorted(folder.glob("*.json")) if folder.is_dir() else []:
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(record, dict) or str(record.get("kind") or "").upper() != "LEARNING_SIGNAL":
            continue
        source = str(record.get("source") or "").strip().upper()
        if source not in _AUTOMATION_SIGNAL_SOURCES:
            continue
        payload = record.get("payload") if isinstance(record.get("payload"), dict) else {}
        signals = payload.get("signals") if isinstance(payload.get("signals"), list) else []
        artifact_id = str(record.get("id") or path.stem)
        stamp = str(record.get("created_at") or payload.get("created_at") or "")
        try:
            parsed = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
            parsed = parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
            stamp = parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
        except ValueError:
            stamp = ""
        seen_here: set[tuple[str, str]] = set()
        for signal in signals:
            if not isinstance(signal, dict):
                continue
            raw_code = signal.get("code") or signal.get("signal_code")
            semantic = signal.get("semantic") if isinstance(signal.get("semantic"), dict) else {}
            raw_topic = signal.get("topic_id") or semantic.get("topic_id")
            if not isinstance(raw_code, str) or not isinstance(raw_topic, str):
                continue
            code = raw_code.strip().upper()
            topic_id = raw_topic.strip().lower()
            if not 3 <= len(code) <= 80 or any(char not in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_" for char in code):
                continue
            if not 3 <= len(topic_id) <= 160 or any(char not in "abcdefghijklmnopqrstuvwxyz0123456789_.:-" for char in topic_id):
                continue
            key = (code, topic_id)
            if key in seen_here:
                continue  # one artifact is one independent observation at most
            seen_here.add(key)

            test_ids: set[str] = set()
            if signal.get("test_id"):
                test_ids.add(str(signal["test_id"]))
            if isinstance(signal.get("test_ids"), list):
                test_ids.update(str(test_id) for test_id in signal["test_ids"] if test_id)
            resolved = resolve_semantic({"semantic": {**semantic, "topic_id": raw_topic}}, entity_id=artifact_id)
            groups.setdefault(key, {})[artifact_id] = {
                "artifact_id": artifact_id,
                "source": source,
                "timestamp": stamp,
                "test_ids": test_ids,
                "private": bool(record.get("private") or signal.get("private")
                                or is_private(semantic) or is_private(resolved)),
            }

    def compose(code: str, topic_id: str, incident_id: str, observations: list[dict[str, Any]],
                *, current: dict[str, Any] | None = None, parent_incident_id: str | None = None) -> dict[str, Any]:
        current = current or {}
        evidence = set(str(ref) for ref in current.get("evidence_refs") or [])
        source_roles = set(str(role) for role in current.get("source_roles") or [])
        signal_test_ids = set(str(test_id) for test_id in current.get("signal_test_ids") or [])
        stamps = {str(stamp) for stamp in (current.get("first_seen"), current.get("last_seen")) if stamp}
        private = bool(current.get("private"))
        for observation in observations:
            evidence.add(observation["artifact_id"])
            source_roles.add(observation["source"])
            signal_test_ids.update(observation["test_ids"])
            if observation["timestamp"]:
                stamps.add(observation["timestamp"])
            private = private or observation["private"]
        ordered_stamps = sorted(stamps)
        what_broke, missing = _INCIDENT_DETAIL_PT.get(code, (
            f"A verificação operacional {code.replace('_', ' ').lower()} falhou repetidamente.",
            f"evidência suficiente para encerrar {code.replace('_', ' ').lower()}",
        ))
        first_seen = ordered_stamps[0] if ordered_stamps else current.get("first_seen")
        return {
            "incident_id": incident_id,
            "parent_incident_id": parent_incident_id or current.get("parent_incident_id"),
            "signal_code": code,
            "summary": f"Quebrou: {what_broke} Desde: {first_seen or 'momento inicial não registrado'}. Falta: {missing}.",
            "what_broke": what_broke,
            "since_when": first_seen,
            "what_is_missing": missing,
            "topic_id": topic_id,
            "evidence_count": len(evidence),
            "evidence_refs": sorted(evidence),
            "source_roles": sorted(source_roles),
            "signal_test_ids": sorted(signal_test_ids),
            "first_seen": first_seen,
            "last_seen": ordered_stamps[-1] if ordered_stamps else current.get("last_seen"),
            "private": private,
        }

    candidates: list[dict[str, Any]] = []
    all_keys = set(groups)
    all_keys.update(
        (str(item.get("signal_code") or ""), str(item.get("topic_id") or ""))
        for item in registry if item.get("signal_code") and item.get("topic_id")
    )
    for code, topic_id in sorted(all_keys):
        observations = groups.get((code, topic_id), {})
        existing = [item for item in registry
                    if item.get("signal_code") == code and item.get("topic_id") == topic_id and item.get("incident_id")]
        associated = {str(ref) for item in existing for ref in item.get("evidence_refs") or []}
        unassociated = [obs for artifact_id, obs in observations.items() if artifact_id not in associated]
        unassociated.sort(key=lambda obs: (obs.get("timestamp") or "", obs["artifact_id"]))

        open_items = [item for item in existing if item.get("state") != "CLOSED"]
        for item in existing:
            if item.get("state") == "CLOSED" or (open_items and item is not open_items[-1]):
                # Existing terminal/legacy siblings remain visible to resolution
                # but reconciliation never mutates their frozen evidence below.
                candidates.append(dict(item))

        if open_items:
            active = open_items[-1]
            candidates.append(compose(code, topic_id, str(active["incident_id"]), unassociated, current=active))
            continue

        if not existing:
            if len(unassociated) < 2:
                continue
            base_id = "INC-" + hashlib.sha256((code + "\n" + topic_id).encode("utf-8")).hexdigest()[:16].upper()
            candidates.append(compose(code, topic_id, base_id, unassociated))
            continue

        closed = [item for item in existing if item.get("state") == "CLOSED"]
        if not closed:
            continue
        parent = max(closed, key=lambda item: str(item.get("closed_at") or item.get("last_seen") or ""))
        anchor = str(parent.get("closed_at") or parent.get("last_seen") or "")
        later = [obs for obs in unassociated if obs.get("timestamp") and (not anchor or obs["timestamp"] > anchor)]
        if len(later) < 2:
            continue
        recurrence_seed = "\n".join([
            code,
            topic_id,
            str(parent["incident_id"]),
            later[0]["artifact_id"],
            later[1]["artifact_id"],
        ])
        child_id = "INC-" + hashlib.sha256(recurrence_seed.encode("utf-8")).hexdigest()[:16].upper()
        candidates.append(compose(
            code, topic_id, child_id, later, parent_incident_id=str(parent["incident_id"])
        ))

    by_id: dict[str, dict[str, Any]] = {}
    for candidate in candidates:
        incident_id = str(candidate.get("incident_id") or "")
        if incident_id:
            by_id[incident_id] = candidate
    return [by_id[key] for key in sorted(by_id)]

def _incident_registry(root: Path) -> list[dict[str, Any]]:
    return [item for item in _read(root, INCIDENTS_DOC).get("incidents") or [] if isinstance(item, dict)]


def resolve_incident_id(root: Path, declared: Any = None, *, signal_refs: list[Any] | None = None,
                        refs: list[Any] | None = None) -> str | None:
    """Resolve an incident only from recurrent evidence or already-linked canonical entities."""
    candidates = _incident_candidates(root)
    known = {str(item.get("incident_id")) for item in candidates}
    known.update(str(item.get("incident_id")) for item in _incident_registry(root) if item.get("incident_id"))
    declared_id = str(declared or "").strip()
    if declared_id:
        return declared_id if declared_id in known else None

    wanted_signals = {str(ref) for ref in signal_refs or [] if ref}
    if wanted_signals:
        matches = [item["incident_id"] for item in candidates if wanted_signals.intersection(item["evidence_refs"])]
        if len(set(matches)) == 1:
            return matches[0]

    matches: set[str] = set()
    for ref in refs or []:
        ref_id = str(ref or "")
        if ref_id in known:
            matches.add(ref_id)
            continue
        for kind in ("test", "hypothesis", "lesson"):
            entity = _entity(root, kind, ref_id)
            if entity and entity.get("incident_id") in known:
                matches.add(str(entity["incident_id"]))
        for candidate in candidates:
            if ref_id in candidate["evidence_refs"]:
                matches.add(candidate["incident_id"])
    return next(iter(matches)) if len(matches) == 1 else None


def incident_confirmed(root: Path, incident_id: str) -> bool:
    return any(test.get("incident_id") == incident_id and not test.get("contests_test_id")
               and test.get("review_state") == "CONFIRMED" for test in _tests(root))


def _entities(root: Path, kind: str) -> list[dict[str, Any]]:
    folder = root / "entities" / kind
    out: list[dict[str, Any]] = []
    for path in sorted(folder.glob("*.json")) if folder.is_dir() else []:
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(value, dict):
            out.append(value)
    return out


def _derived_incident(root: Path, candidate: dict[str, Any], tests: list[dict[str, Any]],
                      genome: dict[str, Any]) -> dict[str, Any]:
    incident_id = candidate["incident_id"]
    related = [test for test in tests if test.get("incident_id") == incident_id]
    primary = [test for test in related if not test.get("contests_test_id")]
    contest_ids = sorted(str(test.get("id")) for test in related if test.get("contests_test_id") and test.get("id"))

    hypothesis_ids = {str(test.get("hypothesis_id")) for test in related if test.get("hypothesis_id")}
    for hypothesis in _entities(root, "hypothesis"):
        if hypothesis.get("incident_id") == incident_id and hypothesis.get("id"):
            hypothesis_ids.add(str(hypothesis["id"]))

    test_ids = sorted(str(test.get("id")) for test in primary if test.get("id"))
    related_test_ids = {str(test.get("id")) for test in related if test.get("id")}
    lesson_ids: set[str] = set()
    for lesson in _entities(root, "lesson"):
        linked_incidents = {str(value) for value in lesson.get("linked_incident_ids") or []}
        linked_tests = {str(value) for value in lesson.get("linked_test_ids") or []}
        if (lesson.get("incident_id") == incident_id or incident_id in linked_incidents
                or bool(related_test_ids.intersection(linked_tests))):
            if lesson.get("id"):
                lesson_ids.add(str(lesson["id"]))

    canaries = [gene for gene in genome.get("genes") or []
                if isinstance(gene, dict) and gene.get("status") == "CANARY" and gene.get("incident_id") == incident_id]
    rolled_back = []
    manual_decisions = []
    for gene in genome.get("genes") or []:
        if not isinstance(gene, dict):
            continue
        for event in gene.get("rolled_back") or []:
            if isinstance(event, dict) and event.get("incident_id") == incident_id:
                rolled_back.append(event)
        decision = gene.get("last_decision") if isinstance(gene.get("last_decision"), dict) else {}
        if decision.get("incident_id") == incident_id and decision.get("action") in {"CANONIZED", "REJECTED"}:
            manual_decisions.append(decision)

    review_states = {str(test.get("review_state") or "") for test in primary}
    verdicts = {str(test.get("verdict") or "").upper() for test in primary}
    if lesson_ids and (rolled_back or "REFUTED" in review_states or manual_decisions):
        state = "CLOSED"
    elif rolled_back:
        state = "ROLLED_BACK"
    elif canaries:
        state = "CANARY"
    elif "CONFIRMED" in review_states or manual_decisions:
        state = "CONFIRMED"
    elif "REFUTED" in review_states or bool(verdicts.intersection({"REJECTED", "FAILED", "FALSIFIED"})):
        state = "REFUTED"
    elif review_states.intersection({"PENDING_REVIEW", "CONTESTED", "REFEREE1_PASSED"}) or verdicts.intersection(POSITIVE_VERDICTS):
        state = "REVIEWING"
    elif any(test.get("prereg_hash") for test in primary):
        state = "PREREGISTERED"
    else:
        state = "OBSERVED"

    next_owner = {
        "OBSERVED": "LEARNER",
        "PREREGISTERED": "EXECUTOR",
        "REVIEWING": "REFUTADOR",
        "CONFIRMED": "LEARNER",
        "REFUTED": "LEARNER",
        "CANARY": "GUARDIAO",
        "ROLLED_BACK": "LEARNER",
        "CLOSED": "NONE",
    }[state]
    canary_ids = sorted(str(gene.get("canary_id")) for gene in canaries if gene.get("canary_id"))
    rollback_ids = sorted(str(event.get("canary_id")) for event in rolled_back if event.get("canary_id"))
    closed_at = None
    if state == "CLOSED":
        stamps = [str(event.get("at")) for event in rolled_back + manual_decisions if event.get("at")]
        stamps += [str(lesson.get("updated_at")) for lesson in _entities(root, "lesson")
                   if lesson.get("id") in lesson_ids and lesson.get("updated_at")]
        closed_at = max(stamps) if stamps else candidate.get("last_seen")

    return {
        **candidate,
        "state": state,
        "next_owner": next_owner,
        "hypothesis_ids": sorted(hypothesis_ids),
        "test_ids": test_ids,
        "contest_test_ids": contest_ids,
        "lesson_ids": sorted(lesson_ids),
        "canary_ids": sorted(set(canary_ids + rollback_ids)),
        "closed_at": closed_at,
    }


def incident_reconcile_requests(root: str | Path) -> list[dict[str, Any]]:
    """Materialize deterministic incident lifecycle state inside the private Tower."""
    root = Path(root)
    tests = _tests(root)
    genome = _read(root, GENOME_DOC)
    current = {str(item.get("incident_id")): item for item in _incident_registry(root) if item.get("incident_id")}
    desired = []
    for candidate in _incident_candidates(root, tests):
        existing = current.get(str(candidate.get("incident_id") or ""))
        if existing and existing.get("state") == "CLOSED":
            continue  # terminal lifecycle and evidence are immutable
        desired.append(_derived_incident(root, candidate, tests, genome))
    updates = [item for item in desired if current.get(item["incident_id"]) != item]
    if not updates:
        return []
    fingerprint = hashlib.sha256(json.dumps(updates, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")).hexdigest()[:16]
    return [_doc(INCIDENTS_DOC, {"incidents": updates}, "REQ-INCIDENT-RECONCILE-" + fingerprint,
                 {"incidents": "incident_id"})]


def _public_entity_ids(root: Path, kind: str, ids: list[Any]) -> list[str]:
    safe = []
    for raw_id in ids:
        entity_id = str(raw_id or "")
        entity = _entity(root, kind, entity_id)
        if not entity or entity.get("private"):
            continue
        semantic = entity.get("semantic") if isinstance(entity.get("semantic"), dict) else {}
        if is_private(semantic) or is_private(resolve_semantic(entity, entity_id=entity_id)):
            continue
        safe.append(entity_id)
    return sorted(set(safe))


def _public_incidents(root: Path, incidents: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Public incidents must say what broke, since when, and what is still missing."""
    out = []
    for incident in incidents:
        if incident.get("private"):
            continue
        code = str(incident.get("signal_code") or "").upper()
        since = str(incident.get("first_seen") or "").strip()
        detail = _INCIDENT_DETAIL_PT.get(code)
        if detail:
            fact, missing = detail
        else:
            fact = _INCIDENT_PUBLIC_COPY_PT.get(code)
            if not fact:
                # Unreviewed internal codes never reach public text: neutral copy until a reviewed one exists.
                fact = ("O sistema detectou o mesmo problema operacional mais de uma vez "
                        "e abriu uma investigação para entender a causa.")
            missing = "evidência específica que identifique a causa material e a condição objetiva de encerramento"
        when = f" Observado desde {since}." if since else " O início ainda não está registrado."
        summary_pt = f"{fact}{when} Falta {missing}."
        out.append({
            "incident_id": incident.get("incident_id"),
            "state": incident.get("state"),
            "evidence_count": int(incident.get("evidence_count") or 0),
            "summary_pt": summary_pt,
            "since": since or None,
            "missing": missing,
            "public_ids": {
                "tests": _public_entity_ids(root, "test", incident.get("test_ids") or [])
                         + _public_entity_ids(root, "test", incident.get("contest_test_ids") or []),
                "hypotheses": _public_entity_ids(root, "hypothesis", incident.get("hypothesis_ids") or []),
                "lessons": _public_entity_ids(root, "lesson", incident.get("lesson_ids") or []),
            },
            "next_owner": incident.get("next_owner"),
        })
    return sorted(out, key=lambda item: str(item.get("incident_id") or ""))


def roadmap_progress(root: Path, roadmap: dict[str, Any], tests: list[dict[str, Any]], clock: bool = True) -> dict[str, Any]:
    rid = str(roadmap.get("roadmap_id") or roadmap.get("id") or "")
    charter = roadmap.get("charter") or {}
    since = str(charter.get("chartered_at") or "")
    mine = [t for t in tests if t.get("roadmap_id") == rid and not t.get("decoy")]
    counted = [t for t in mine if not since or str(t.get("executed_at") or "") >= since]
    executed = sorted([t for t in counted if t.get("verdict")], key=lambda t: str(t.get("executed_at") or ""))
    confirmed = sum(1 for t in counted if t.get("review_state") == "CONFIRMED")
    streak = 0
    for t in reversed(executed):
        if t.get("review_state") == "REFUTED" or str(t.get("verdict") or "").upper() in {"REJECTED", "FALSIFIED"}:
            streak += 1
        else:
            break
    budget, stop = charter.get("budget") or {}, charter.get("stop") or {}
    days = None
    if since and clock:
        try:
            days = (datetime.now(timezone.utc) - datetime.fromisoformat(since.replace("Z", "+00:00"))).days
        except ValueError:
            days = None
    reason = None
    if charter.get("status") == "CHARTERED":
        if stop.get("success_confirmed") and confirmed >= int(stop["success_confirmed"]):
            reason = "SUCCESS"
        elif stop.get("kill_consecutive_refuted") and streak >= int(stop["kill_consecutive_refuted"]):
            reason = "KILL"
        elif not charter.get("renewable") and (
                (budget.get("max_tests") and len(executed) >= int(budget["max_tests"])) or (
                budget.get("max_days") and days is not None and days >= int(budget["max_days"]))):
            reason = "BUDGET"
    review_due = None
    if charter.get("renewable") and charter.get("review_every_days") and days is not None:
        # Semi-permanent campaign: never closes on budget; asks Dener for a course review every N days.
        review_due = days >= int(charter["review_every_days"]) and days % int(charter["review_every_days"]) < 1
    lifecycle = [str(t.get("state") or t.get("status") or "").upper() for t in mine]
    frontier_refs = roadmap.get("frontier_refs") if isinstance(roadmap.get("frontier_refs"), list) else []
    return {"roadmap_id": rid, "campaign_id": roadmap.get("campaign_id"),
            "state": roadmap.get("state") or roadmap.get("status"),
            "charter_status": charter.get("status"), "confirmed": confirmed,
            "success_target": stop.get("success_confirmed"), "tests_used": len(executed), "max_tests": budget.get("max_tests"),
            "tests_total": len(mine), "frontier_count": len(frontier_refs),
            "ready": sum(1 for s in lifecycle if s == "READY"),
            "resumable": sum(1 for s in lifecycle if s in {"RUNNING", "CHECKPOINTED"}),
            "days": days, "max_days": budget.get("max_days"), "refuted_streak": streak,
            "kill_streak": stop.get("kill_consecutive_refuted"), "stop_reached": reason,
            "renewable": bool(charter.get("renewable")), "review_due": review_due}


def _hours_since(stamps: list[str], now: datetime) -> float | None:
    parsed = []
    for stamp in stamps:
        try:
            parsed.append(datetime.fromisoformat(str(stamp).replace("Z", "+00:00")))
        except ValueError:
            continue
    if not parsed:
        return None
    latest = max(p if p.tzinfo else p.replace(tzinfo=timezone.utc) for p in parsed)
    return round((now - latest).total_seconds() / 3600, 1)


def _emergence(root: Path, tests: list[dict[str, Any]], genome: dict[str, Any], now: datetime) -> dict[str, Any]:
    """Anti-stagnation pressure: which loop is quiet and what each task must do about it this run."""
    thoughts = _read(root, THOUGHTS_DOC).get("entries") or []
    since = {
        "thought": _hours_since([t.get("at") for t in thoughts], now),
        "dream": _hours_since([t.get("at") for t in thoughts if t.get("kind") == "DREAM"], now),
        "genome_mutation": _hours_since([g.get("canary_since") for g in genome.get("genes") or []]
                                        + [l.get("at") for l in genome.get("lineage") or []], now),
        "fitness": _hours_since([f.get("at") for f in genome.get("fitness") or []], now),
        "new_hypothesis": _hours_since([t.get("created_at") or t.get("frozen_at") for t in tests
                                        if t.get("proposed_by") == "CHATGPT"], now),
        "result": _hours_since([t.get("executed_at") for t in tests if t.get("verdict")], now),
        "contest": _hours_since([c.get("at") for t in tests for c in t.get("contests") or []], now),
        "decoy": _hours_since([d.get("at") for d in _read(root, DECOYS_DOC).get("planted") or []], now),
    }
    limits = {"thought": 6, "dream": 24, "genome_mutation": 48, "fitness": 12, "new_hypothesis": 6,
              "result": 3, "contest": 12, "decoy": 168}
    owners = {"thought": "PITIA", "dream": "PITIA", "genome_mutation": "PITIA/LEARNER", "fitness": "GUARDIAO",
              "new_hypothesis": "LEARNER", "result": "EXECUTOR", "contest": "REFUTADOR", "decoy": "GUARDIAO"}
    stale = [{"loop": k, "hours": v, "owner": owners[k]} for k, v in since.items() if v is None or v > limits[k]]
    return {"hours_since": since, "limits_h": limits, "stale": stale,
            "rule": "The owner of every stale loop MUST produce at least one item of that loop this run "
                    "(a thought with refs, a dream, a canary proposal, a fitness report, a hypothesis, a contest or a decoy)."}


def evolution_status(root: str | Path, now: datetime | None = None, public: bool = False) -> dict[str, Any]:
    """Task view (default) or public ATLAS view (public=True: deterministic, no clock, adds diary/lineage)."""
    root = Path(root)
    now = now or datetime.now(timezone.utc)
    tests = _tests(root)
    roadmaps = []
    folder = root / "roadmaps"
    for path in sorted(folder.glob("*.json")) if folder.is_dir() else []:
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except ValueError:
            continue
        if isinstance(doc, dict):
            doc.setdefault("roadmap_id", path.stem)
            roadmaps.append(doc)
    genome = _read(root, GENOME_DOC)
    decoys = _read(root, DECOYS_DOC)
    revealed = decoys.get("revealed") or []
    positive = [t for t in tests if str(t.get("verdict") or "").upper() in POSITIVE_VERDICTS and not t.get("decoy")]
    incidents = _incident_registry(root)
    status = {
        "arm_for_this_run": "canary" if now.hour % 2 else "canonical",
        "gate": {
            "charters_waiting": [{"roadmap_id": r["roadmap_id"], "question": (r.get("charter") or {}).get("question"),
                                  "objectives": (r.get("charter") or {}).get("objectives"),
                                  "renewable": bool((r.get("charter") or {}).get("renewable"))}
                                 for r in roadmaps if (r.get("charter") or {}).get("status") == "PROPOSED"],
            "canaries_waiting": [{"gene": g.get("id"), "canary": g.get("canary"), "since": g.get("canary_since")}
                                 for g in genome.get("genes") or [] if g.get("status") == "CANARY"],
        },
        "review_queue": {
            "referee_1": [t["id"] for t in positive if t.get("review_state") in (None, "PENDING_REVIEW", "CONTESTED")
                          or (t.get("review_state") == "REFEREE1_PASSED" and len(t.get("contests") or []) < MAX_CONTESTS)],
            "referee_2": [t["id"] for t in positive if t.get("review_state") == "REFEREE1_PASSED"],
        },
        # Visibility is not a gate: every non-closed roadmap in the Tower is shown to tasks.
        # charter_status remains explicit so gate semantics stay separate from execution visibility.
        "roadmaps": [roadmap_progress(root, r, tests, clock=not public) for r in roadmaps
                     if str((r.get("charter") or {}).get("status") or "").upper() != "CLOSED"
                     and str(r.get("state") or r.get("status") or "").upper() != "CLOSED"],
        "genome": {"generation": int(genome.get("generation") or 0),
                   "genes": [{k: g.get(k) for k in ("id", "status", "canonical", "canary")} for g in genome.get("genes") or []]},
        "batteries": {s: sum(1 for x in _read(root, BATTERIES_DOC).get("batteries") or [] if x.get("status") == s)
                      for s in ("QUEUED", "DISPATCHED", "DONE")},
        "decoys": {"planted": len(decoys.get("planted") or []), "revealed": len(revealed),
                   "caught": sum(1 for d in revealed if d.get("caught"))},
        "signal_clusters": _signal_clusters(root, tests),
        "incidents": incidents,
    }
    if not public:
        status["emergence"] = _emergence(root, tests, genome, now)
    if public:
        status.pop("arm_for_this_run")
        status.pop("signal_clusters", None)  # raw codes/topics remain private; incidents expose reviewed copy only
        status["incidents"] = _public_incidents(root, incidents)
        # Only allowlisted inner keys: budget/stop dicts may carry private fields.
        def _pick(d, keys):
            return {k: d.get(k) for k in keys if isinstance(d, dict) and k in d}
        status["charters"] = [{"roadmap_id": r["roadmap_id"], **{k: (r.get("charter") or {}).get(k) for k in (
            "status", "question", "chartered_at", "closed_at", "close_reason", "rival_of")},
            "budget": _pick((r.get("charter") or {}).get("budget"), ("max_tests", "max_days")),
            "stop": _pick((r.get("charter") or {}).get("stop"), ("success_confirmed", "kill_consecutive_refuted"))}
            for r in roadmaps if r.get("charter")]
        shown, texts = [], set()
        for e in _read(root, THOUGHTS_DOC).get("entries") or []:
            key = " ".join(str(e.get("text") or "").split()).lower()
            if not e.get("retired") and key not in texts:
                texts.add(key)
                shown.append(e)
        status["thoughts"] = shown[-40:]
        status["genome"]["lineage"] = genome.get("lineage") or []
        status["genome"]["fitness"] = (genome.get("fitness") or [])[-120:]
        status["reviews"] = {s: sum(1 for t in positive if (t.get("review_state") or "PENDING_REVIEW") == s)
                             for s in ("PENDING_REVIEW", "CONTESTED", "REFEREE1_PASSED", "CONFIRMED", "REFUTED")}
    return status
