"""Executable roadmap frontier over a materialized live Tower.

Reads both roadmap shapes found in the Tower:
  V1  inline frozen ``tests`` (roadmap_test_id, depends_on, ...) resolved to TEST entities by id
  V2  ``frontier_refs`` naming TEST entities directly
and returns what an executor should do next. A malformed roadmap is reported
in ``skipped_roadmaps`` instead of stopping every other lane.

Order: continue RUNNING work first; then READY tests whose dependencies are terminal;
only then revisit CHECKPOINTED work. This prevents stale checkpoints from starving
new executable tests while preserving continuity for work that is actually running.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .tower_paths import entity_path, fs_path

TERMINAL = {"DONE", "VERIFIED", "RESULT", "REJECTED", "FAILED", "INCONCLUSIVE", "SUPERSEDED", "COMPLETED", "CLOSED", "CLOSED_VERIFIED"}
RESUMABLE = {"RUNNING", "CHECKPOINTED"}
PRIORITY_RANK = {"P0": 0, "CRITICAL": 1, "HIGH": 2, "MEDIUM_HIGH": 3, "MEDIUM": 4, "NORMAL": 5, "P1": 5, "LOW": 6, "P2": 6}


def _read(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return value if isinstance(value, dict) else None


def _lifecycle(test: dict[str, Any] | None) -> str:
    if not test:
        return "MISSING"
    return str(test.get("state") or test.get("status") or "READY").upper()


def _dependency_met(dep: str, status_of) -> bool:
    dep = str(dep)
    if dep.startswith("ONE_OF:"):
        return any(status_of(option) in TERMINAL for option in dep[len("ONE_OF:"):].split("|") if option)
    return status_of(dep) in TERMINAL


def roadmap_frontier(root: str | Path, roadmap_id: str | None = None) -> dict[str, Any]:
    root = Path(root)
    index = _read(fs_path(root, "indexes/active-roadmaps.json")) or {"items": []}
    cache: dict[str, dict[str, Any] | None] = {}

    def test(test_id: str) -> dict[str, Any] | None:
        if test_id not in cache:
            cache[test_id] = _read(entity_path(root, "test", test_id))
        return cache[test_id]

    def status_of(test_id: str) -> str:
        return _lifecycle(test(test_id))

    resumable: list[dict[str, Any]] = []
    ready: list[dict[str, Any]] = []
    waiting: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    seen: set[str] = set()  # a test shared by two roadmaps is listed once, under the higher-priority one

    items = [item for item in index.get("items", []) if isinstance(item, dict)]
    items.sort(key=lambda item: (PRIORITY_RANK.get(str(item.get("priority") or "NORMAL").upper(), 9), str(item.get("roadmap_id"))))
    for item in items:
        rid = str(item.get("roadmap_id") or "")
        if roadmap_id and rid != roadmap_id:
            continue
        if str(item.get("state") or "").upper() != "ACTIVE":
            continue
        relative = str(item.get("relative_path") or f"roadmaps/{rid}.json")
        roadmap = _read(fs_path(root, relative))
        if not roadmap:
            skipped.append({"roadmap_id": rid, "reason": "ROADMAP_DOCUMENT_MISSING"})
            continue
        if isinstance(roadmap.get("frontier_refs"), list):
            refs = [str(ref) for ref in roadmap["frontier_refs"]]
        elif isinstance(roadmap.get("tests"), list):
            refs = [str(t.get("roadmap_test_id")) for t in roadmap["tests"] if isinstance(t, dict) and t.get("roadmap_test_id")]
        else:
            refs = []
        if not refs:
            skipped.append({"roadmap_id": rid, "reason": "ACTIVE_ROADMAP_WITHOUT_TESTS"})
            continue
        for ref in refs:
            if ref in seen:
                continue
            seen.add(ref)
            entity = test(ref)
            state = _lifecycle(entity)
            base = {"roadmap_id": rid, "test_id": ref, "state": state, "priority": item.get("priority")}
            if state in TERMINAL:
                continue
            if entity is None:
                skipped.append({**base, "reason": "FRONTIER_TEST_NOT_MATERIALIZED"})
                continue
            if state in RESUMABLE:
                resumable.append(base)
                continue
            if state.startswith("BLOCKED") or state in {"DRAFT", "PROPOSED", "PLANNED"}:
                # DRAFT = hypothesis still missing frozen criteria; the Learner completes it, the Executor waits.
                waiting.append({**base, "reason": state})
                continue
            deps = [str(d) for d in (entity.get("depends_on") or [])]
            unmet = [d for d in deps if not _dependency_met(d, status_of)]
            if unmet:
                waiting.append({**base, "waiting_on": unmet})
            else:
                ready.append(base)

    # Materialized TEST entities are authoritative even if a roadmap forgot to include them in frontier_refs.
    # This fallback prevents READY/RUNNING/CHECKPOINTED/BLOCKED/DRAFT work from disappearing from the Executor view.
    if not roadmap_id:
        folder = root / "entities" / "test"
        for path in sorted(folder.glob("*.json")) if folder.is_dir() else []:
            entity = _read(path)
            if not entity or not entity.get("id") or str(entity["id"]) in seen:
                continue
            state = _lifecycle(entity)
            if state in TERMINAL or not (entity.get("state") or entity.get("status")):
                continue
            ref = str(entity["id"])
            seen.add(ref)
            base = {"roadmap_id": entity.get("roadmap_id"), "test_id": ref, "state": state,
                    "priority": entity.get("priority"), "source": "ENTITY_MATERIALIZED"}
            if state in RESUMABLE:
                resumable.append(base)
                continue
            if state.startswith("BLOCKED") or state in {"DRAFT", "PROPOSED", "PLANNED"}:
                waiting.append({**base, "reason": state})
                continue
            deps = [str(d) for d in (entity.get("depends_on") or [])]
            unmet = [d for d in deps if not _dependency_met(d, status_of)]
            (waiting if unmet else ready).append({**base, "waiting_on": unmet} if unmet else base)
    # Contest tests (refutation) first, then the Learner's own rubric score, then roadmap priority.
    def _rank(t: dict[str, Any]) -> tuple:
        entity = test(t["test_id"]) or {}
        try:
            score = -float(entity.get("rank_score") or 0)
        except (TypeError, ValueError):
            score = 0.0
        return (not entity.get("contests_test_id"), t.get("source") == "ENTITY_READY", score,
                PRIORITY_RANK.get(str(t.get("priority") or "NORMAL").upper(), 9))
    ready.sort(key=_rank)

    def _round_robin_by_roadmap(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Preserve rank inside a roadmap while preventing cross-roadmap starvation."""
        lanes: dict[str, list[dict[str, Any]]] = {}
        lane_order: list[str] = []
        for entry in entries:
            lane = str(entry.get("roadmap_id") or "__UNATTACHED__")
            if lane not in lanes:
                lanes[lane] = []
                lane_order.append(lane)
            lanes[lane].append(entry)
        ordered: list[dict[str, Any]] = []
        while any(lanes[lane] for lane in lane_order):
            for lane in lane_order:
                if lanes[lane]:
                    ordered.append(lanes[lane].pop(0))
        return ordered

    # Contests remain globally first. Inside contest and ordinary READY classes,
    # rotate roadmaps so a long queue in one campaign cannot hide other ACTIVE
    # campaigns from the Executor's bounded batch.
    contest_ready = [entry for entry in ready if (test(entry["test_id"]) or {}).get("contests_test_id")]
    ordinary_ready = [entry for entry in ready if not (test(entry["test_id"]) or {}).get("contests_test_id")]
    fair_ready = _round_robin_by_roadmap(contest_ready) + _round_robin_by_roadmap(ordinary_ready)

    running = [item for item in resumable if item.get("state") == "RUNNING"]
    checkpointed = [item for item in resumable if item.get("state") == "CHECKPOINTED"]
    fair_checkpointed = _round_robin_by_roadmap(checkpointed)

    genome = _read(root / "evolution" / "genome.json") or {}
    genes = {str(g.get("id")): g.get("canonical") for g in genome.get("genes", []) if isinstance(g, dict)}
    try:
        max_batch = max(1, int(genes.get("executor.max_parallel_tests", 10)))
    except (TypeError, ValueError):
        max_batch = 10
    try:
        checkpoint_quota = max(0, int(genes.get("executor.checkpoint_reviews_per_run", 3)))
    except (TypeError, ValueError):
        checkpoint_quota = 3

    if running:
        action, pick = "RESUME_EXISTING", running[0]
    elif fair_ready:
        action, pick = "EXECUTE_READY", fair_ready[0]
    elif checkpointed:
        action, pick = "RESUME_EXISTING", checkpointed[0]
    elif waiting:
        action, pick = "WAIT_DEPENDENCY", None
    else:
        action, pick = "COMPLETE", None
    return {
        "state": action,
        "next": pick,
        "batch": (running + fair_ready + checkpointed)[:max_batch],
        "checkpoint_review": fair_checkpointed[:checkpoint_quota],
        "resumable": resumable,
        "ready": ready,
        "waiting": waiting,
        "skipped_roadmaps": skipped,
        "rule": "RUNNING_BEFORE_READY_BEFORE_CHECKPOINTED; CONTESTS_FIRST; READY_ROADMAP_ROUND_ROBIN; CHECKPOINT_REVIEW_QUOTA_FROM_GENOME; ONLY_AFFECTED_CHAIN_WAITS; INVALID_ROADMAPS_ARE_REPORTED_NOT_FATAL; ENTITY_READY_TESTS_OUTSIDE_ACTIVE_ROADMAPS_ARE_READY",
    }
