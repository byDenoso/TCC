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
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .tower_paths import entity_path, fs_path

MAX_CONTESTS = 2
POSITIVE_VERDICTS = {"PROMOTED", "SUPPORTED"}
# The spine: never a gene, never a canary. Changes here are recommendations to Dener only.
SPINE_PREFIXES = ("contract", "writer", "frozen", "criteria", "fitness", "spine", "privacy", "gate")
GENOME_DOC = "evolution/genome.json"
THOUGHTS_DOC = "evolution/thoughts.json"
DECOYS_DOC = "evolution/decoys.json"


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
    if not existing:
        merge.update({"roadmap_id": rid, "status": "PROPOSED", "frontier_refs": [],
                      "title": body.get("title") or body.get("question"), "domain": body.get("domain")})
    return [_doc(f"roadmaps/{rid}.json", merge, f"REQ-CHARTER-{rid}")]


def _gate_is_dener(item: dict[str, Any], body: dict[str, Any]) -> bool:
    return "DENER" in {str(item.get("source") or "").upper(), str(body.get("approved_by") or "").upper()}


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
        return [_doc(GENOME_DOC, {"genes": [{"id": gene, "status": "CANONICAL", "canary": None, "last_decision": {"action": "REJECTED", "at": at}}]},
                     f"REQ-GENE-REJECT-{gene}", {"genes": "id"})]
    generation = int(genome.get("generation") or 0) + 1
    return [_doc(GENOME_DOC, {
        "generation": generation,
        "genes": [{"id": gene, "status": "CANONICAL", "canonical": current.get("canary"), "canary": None,
                   "last_decision": {"action": "CANONIZED", "at": at, "generation": generation}}],
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
    contests = list(current.get("contests") or [])
    if len(contests) >= MAX_CONTESTS or current.get("review_state") in {"CONFIRMED", "REFUTED"} and body.get("source") != "SENTINEL":
        return []
    requests: list[dict[str, Any]] = []
    attack = body.get("contest_test") if isinstance(body.get("contest_test"), dict) else None
    attack_id = None
    if attack:
        attack_id = str(attack.get("test_id") or f"CONTEST-{test_id}-{len(contests) + 1}")
        requests += hypothesis_fn(item, {**attack, "test_id": attack_id, "contests_test_id": test_id,
                                         "roadmap_id": attack.get("roadmap_id") or current.get("roadmap_id"),
                                         "priority": "P0"}, root)
    entry = {"n": len(contests) + 1, "by": str(body.get("source") or body.get("referee") or "REFEREE_1").upper(),
             "reason": body.get("reason"), "contest_test_id": attack_id, "at": _now(item), "refs": body.get("refs")}
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


# ── Genome: canary mutations, rollback, fitness ─────────────────────────────

def _spine(gene: str) -> bool:
    return gene.lower().replace("-", "_").startswith(SPINE_PREFIXES)


def mutation_requests(item: dict[str, Any], body: dict[str, Any], root: Path) -> list[dict[str, Any]]:
    gene = str(body.get("gene") or "").strip()
    if not gene or _spine(gene):
        return []  # the spine is not evolvable; the caller records the proposal as a recommendation
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
                                                        "fitness": body.get("fitness")}]
    return [_doc(GENOME_DOC, {"genes": [{"id": gene, "status": "CANONICAL", "canary": None, "rolled_back": history}]},
                 f"REQ-GENE-ROLLBACK-{gene}-{_now(item)[:13]}", {"genes": "id"})]


def fitness_requests(item: dict[str, Any], body: dict[str, Any], root: Path) -> list[dict[str, Any]]:
    genome = _read(root, GENOME_DOC)
    rows = [dict(m, at=_now(item), generation=int(genome.get("generation") or 0))
            for m in body.get("measurements") or [] if isinstance(m, dict)]
    if body.get("value") is not None:
        rows.append({"arm": body.get("arm") or "canonical", "value": body.get("value"), "components": body.get("components"),
                     "at": _now(item), "generation": int(genome.get("generation") or 0)})
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
    caught = test.get("review_state") in {"CONTESTED", "REFUTED"} or str(test.get("verdict") or "").upper() not in POSITIVE_VERDICTS
    requests = [_doc(DECOYS_DOC, {"revealed": (decoys.get("revealed") or []) + [{"test_id": test_id, "caught": caught, "at": _now(item),
                                                                                 "commitment": digest}]}, f"REQ-DECOY-REVEAL-{test_id}")]
    update = _test_update(root, test_id, {"decoy": True, "review_state": "REFUTED", "decoy_caught": caught},
                          f"REQ-DECOY-MARK-{test_id}", "DECOY_REVEALED")
    return requests + ([update] if update else [])


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
    return {"roadmap_id": rid, "charter_status": charter.get("status"), "confirmed": confirmed,
            "success_target": stop.get("success_confirmed"), "tests_used": len(executed), "max_tests": budget.get("max_tests"),
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
        "roadmaps": [roadmap_progress(root, r, tests, clock=not public) for r in roadmaps
                     if (r.get("charter") or {}).get("status") == "CHARTERED"],
        "genome": {"generation": int(genome.get("generation") or 0),
                   "genes": [{k: g.get(k) for k in ("id", "status", "canonical", "canary")} for g in genome.get("genes") or []]},
        "decoys": {"planted": len(decoys.get("planted") or []), "revealed": len(revealed),
                   "caught": sum(1 for d in revealed if d.get("caught"))},
    }
    if not public:
        status["emergence"] = _emergence(root, tests, genome, now)
    if public:
        status.pop("arm_for_this_run")
        status["charters"] = [{"roadmap_id": r["roadmap_id"], **{k: (r.get("charter") or {}).get(k) for k in (
            "status", "question", "budget", "stop", "chartered_at", "closed_at", "close_reason", "rival_of")}}
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
