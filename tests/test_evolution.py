from __future__ import annotations

import hashlib
import json
from pathlib import Path

from runtime.nexo_agent_api.evolution import evolution_status
from runtime.nexo_agent_api.inbox_apply import proposal_to_requests
from runtime.nexo_agent_api.tower_apply import apply_requests
from runtime.nexo_agent_api.tower_paths import entity_path


_COUNTER = iter(range(10**6))


def _apply(root: Path, item: dict) -> list[dict]:
    item = {"_inbox_name": f"inbox-{next(_COUNTER)}.json", **item}
    requests = proposal_to_requests(item, root)
    receipts = apply_requests(root, requests)
    assert all(r.get("accepted", True) is not False for r in receipts), receipts
    return requests


def _test(root: Path, test_id: str) -> dict:
    return json.loads(entity_path(root, "test", test_id).read_text(encoding="utf-8"))


def _roadmap(root: Path, rid: str) -> dict:
    return json.loads((root / "roadmaps" / f"{rid}.json").read_text(encoding="utf-8"))


def _tower(tmp_path: Path) -> Path:
    root = tmp_path / "TOWER"
    (root / "roadmaps").mkdir(parents=True)
    (root / "indexes").mkdir()
    (root / "indexes" / "active-roadmaps.json").write_text(json.dumps({"items": []}))
    (root / "CONTROL.json").write_text("{}")
    return root


def test_charter_gate_only_dener_opens_it(tmp_path):
    root = _tower(tmp_path)
    _apply(root, {"kind": "ROADMAP_CHARTER", "source": "PITIA", "created_at": "2026-09-25T00:00:00Z",
                  "payload": {"roadmap_id": "RM-X", "question": "X existe?", "stop": {"success_confirmed": 1}}})
    assert _roadmap(root, "RM-X")["charter"]["status"] == "PROPOSED"
    # a task pretending to approve is only recorded
    _apply(root, {"kind": "OPERATOR_INTENT", "source": "LEARNER", "payload": {"action": "APPROVE_CHARTER", "roadmap_id": "RM-X"}})
    assert _roadmap(root, "RM-X")["charter"]["status"] == "PROPOSED"
    _apply(root, {"kind": "OPERATOR_INTENT", "source": "DENER", "created_at": "2026-09-25T01:00:00Z",
                  "payload": {"action": "APPROVE_CHARTER", "roadmap_id": "RM-X"}})
    roadmap = _roadmap(root, "RM-X")
    assert roadmap["status"] == "ACTIVE" and roadmap["charter"]["status"] == "CHARTERED"
    assert roadmap["charter"]["charter_hash"].startswith("sha256:")
    index = json.loads((root / "indexes" / "active-roadmaps.json").read_text())
    assert index["items"] == [{"roadmap_id": "RM-X", "state": "ACTIVE", "priority": "NORMAL", "relative_path": "roadmaps/RM-X.json"}]


def test_positive_result_needs_two_referees_and_stop_criterion_fires(tmp_path):
    root = _tower(tmp_path)
    _apply(root, {"kind": "ROADMAP_CHARTER", "payload": {"roadmap_id": "RM-X", "question": "q", "stop": {"success_confirmed": 1}}})
    _apply(root, {"kind": "OPERATOR_INTENT", "source": "DENER", "created_at": "2026-09-25T00:00:00Z",
                  "payload": {"action": "APPROVE_CHARTER", "roadmap_id": "RM-X"}})
    requests = _apply(root, {"kind": "HYPOTHESIS_PROPOSAL", "_inbox_name": "h1.json", "payload": {"display_name": "Teste de exemplo", "domain": "science", 
        "test_id": "T-1", "roadmap_id": "RM-X", "question": "q", "method": "frozen method", "data": "fixture dataset",
        "success_criteria": "s", "kill_criteria": "k", "rank_score": 0.8}})
    assert requests[0]["changes"]["prereg_hash"].startswith("sha256:")
    _apply(root, {"kind": "MUTATION_PROPOSAL", "created_at": "2026-09-25T02:00:00Z",
                  "payload": {"test_id": "T-1", "result": {"verdict": "PROMOTED"}, "prediction": {"p_promoted": 0.3}}})
    assert _test(root, "T-1")["review_state"] == "PENDING_REVIEW"
    status = evolution_status(root)
    assert status["review_queue"]["referee_1"] == ["T-1"]
    _apply(root, {"kind": "CONTEST", "payload": {"test_id": "T-1", "reason": "janela diferente",
                                                 "contest_test": {"question": "sobrevive?", "success_criteria": "a", "kill_criteria": "b"}}})
    assert _test(root, "T-1")["review_state"] == "CONTESTED"
    assert _test(root, "CONTEST-T-1-1")["contests_test_id"] == "T-1"
    _apply(root, {"kind": "VERDICT_REVIEW", "payload": {"test_id": "T-1", "referee": 1, "outcome": "SURVIVED"}})
    assert evolution_status(root)["review_queue"]["referee_2"] == ["T-1"]
    _apply(root, {"kind": "VERDICT_REVIEW", "payload": {"test_id": "T-1", "referee": "CLAUDE", "outcome": "SURVIVED"}})
    assert _test(root, "T-1")["review_state"] == "CONFIRMED"
    [progress] = evolution_status(root)["roadmaps"]
    assert progress["confirmed"] == 1 and progress["stop_reached"] == "SUCCESS"
    _apply(root, {"kind": "ROADMAP_CLOSE", "payload": {"roadmap_id": "RM-X", "reason": "SUCCESS"}})
    assert _roadmap(root, "RM-X")["charter"]["status"] == "CLOSED"


def test_genome_canary_rollback_and_canonization(tmp_path):
    root = _tower(tmp_path)
    # the spine never mutates
    requests = proposal_to_requests({"kind": "GENOME_MUTATION", "payload": {"gene": "writer.bridge", "value": 1}}, root)
    assert requests[0]["changes"]["kind"] == "GENOME_MUTATION_NOOP"
    _apply(root, {"kind": "GENOME_MUTATION", "payload": {"gene": "learner.cold_area_share", "value": 0.3, "current_value": 0.2}})
    status = evolution_status(root)
    assert status["gate"]["canaries_waiting"][0]["gene"] == "learner.cold_area_share"
    _apply(root, {"kind": "GENOME_ROLLBACK", "payload": {"gene": "learner.cold_area_share", "reason": "piorou"}})
    assert evolution_status(root)["gate"]["canaries_waiting"] == []
    _apply(root, {"kind": "GENOME_MUTATION", "payload": {"gene": "learner.cold_area_share", "value": 0.25}})
    _apply(root, {"kind": "OPERATOR_INTENT", "source": "DENER", "payload": {"action": "CANONIZE", "gene": "learner.cold_area_share"}})
    genome = evolution_status(root)["genome"]
    assert genome["generation"] == 1
    assert genome["genes"][0] == {"id": "learner.cold_area_share", "status": "CANONICAL", "canonical": 0.25, "canary": None}


def test_thoughts_need_refs_and_decoys_are_verified(tmp_path):
    root = _tower(tmp_path)
    _apply(root, {"kind": "NEXO_THOUGHT", "payload": {"entries": [{"text": "sem prova"}, {"text": "H0 falhou 3x em z~0.5", "refs": ["T-1"]}]}})
    thoughts = json.loads((root / "evolution" / "thoughts.json").read_text())["entries"]
    assert [t["text"] for t in thoughts] == ["H0 falhou 3x em z~0.5"]
    _apply(root, {"kind": "HYPOTHESIS_PROPOSAL", "payload": {"display_name": "Teste de exemplo", "domain": "science", "test_id": "T-D", "question": "q", "success_criteria": "s", "kill_criteria": "k"}})
    _apply(root, {"kind": "MUTATION_PROPOSAL", "payload": {"test_id": "T-D", "result": {"verdict": "PROMOTED"}}})
    commitment = hashlib.sha256(b"T-D:segredo").hexdigest()
    _apply(root, {"kind": "DECOY_PLANT", "payload": {"commitment": commitment}})
    _apply(root, {"kind": "DECOY_REVEAL", "payload": {"test_id": "T-D", "secret": "errado"}})
    assert not _test(root, "T-D").get("decoy")
    _apply(root, {"kind": "DECOY_REVEAL", "payload": {"test_id": "T-D", "secret": "segredo"}})
    test = _test(root, "T-D")
    assert test["decoy"] is True and test["decoy_caught"] is False
    assert evolution_status(root)["decoys"] == {"planted": 1, "revealed": 1, "caught": 0}


def test_battery_dispatch_and_collect(tmp_path):
    root = _tower(tmp_path)
    for tid in ("T-A", "T-B"):
        _apply(root, {"kind": "HYPOTHESIS_PROPOSAL", "payload": {"display_name": "Teste de exemplo", "domain": "science", "test_id": tid, "question": "q", "success_criteria": "s", "kill_criteria": "k"}})
    _apply(root, {"kind": "TEST_BATTERY", "created_at": "2026-09-25T14:00:00Z", "payload": {"battery_id": "bat-1", "tests": [
        {"test_id": "T-A", "recipe": "seed_bounds", "params": {"n": [10]}, "prediction": {"p_promoted": 0.2}},
        {"test_id": "T-B", "recipe": "seed_bounds"}, {"test_id": "MISSING", "recipe": "seed_bounds"},
        {"test_id": "T-A", "script": "print(1)"}]}})
    from runtime.nexo_agent_api.evolution import pending_batteries
    assert [b["id"] for b in pending_batteries(root)] == ["bat-1"]
    assert _test(root, "T-A")["status"] == "RUNNING" and _test(root, "T-A")["prediction"] == {"p_promoted": 0.2}
    _apply(root, {"kind": "BATTERY_STATUS", "payload": {"battery_id": "bat-1", "status": "DISPATCHED"}})
    assert pending_batteries(root) == []
    _apply(root, {"kind": "BATTERY_STATUS", "payload": {"battery_id": "bat-1", "status": "DONE", "results": [
        {"test_id": "T-A", "ok": True, "result": {"verdict": "PROMOTED", "summary": "x"}},
        {"test_id": "T-B", "ok": False, "log_tail": "Traceback"}]}})
    assert _test(root, "T-A")["verdict"] == "PROMOTED" and _test(root, "T-A")["review_state"] == "PENDING_REVIEW"
    assert _test(root, "T-B")["status"] == "READY" and "Traceback" in _test(root, "T-B")["last_runtime_failure"]["log_tail"]
    assert evolution_status(root)["batteries"] == {"QUEUED": 0, "DISPATCHED": 0, "DONE": 1}


def _hyp(root, tid, **extra):
    _apply(root, {"kind": "HYPOTHESIS_PROPOSAL", "payload": {"display_name": f"Teste {tid}", "domain": "science",
                                                             "test_id": tid, "question": "q", "method": "frozen method",
                                                             "data": "fixture dataset", "success_criteria": "s",
                                                             "kill_criteria": "k", **extra}})


def _maintain(root, now=None):
    from datetime import datetime, timezone
    from runtime.nexo_agent_api.evolution import maintenance_reconcile_requests
    requests = maintenance_reconcile_requests(root, now or datetime(2026, 10, 30, tzinfo=timezone.utc))
    receipts = apply_requests(root, requests)
    assert all(r.get("accepted", True) is not False for r in receipts), receipts
    return requests


def test_second_runtime_failure_blocks_instead_of_recycling(tmp_path):
    root = _tower(tmp_path)
    _hyp(root, "T-F")
    for n in (1, 2):
        _apply(root, {"kind": "TEST_BATTERY", "payload": {"battery_id": f"bat-f{n}", "tests": [{"test_id": "T-F", "recipe": "seed_bounds"}]}})
        _apply(root, {"kind": "BATTERY_STATUS", "payload": {"battery_id": f"bat-f{n}", "status": "DONE",
                                                            "results": [{"test_id": "T-F", "ok": False, "log_tail": "ImportError"}]}})
        state = _test(root, "T-F")["status"]
        assert state == ("READY" if n == 1 else "BLOCKED_INPUT")
    assert "2 vezes" in _test(root, "T-F")["blocker"]


def test_maintenance_archives_stale_drafts_and_audits_prereg(tmp_path):
    root = _tower(tmp_path)
    _apply(root, {"kind": "HYPOTHESIS_PROPOSAL", "created_at": "2026-09-01T00:00:00Z",
                  "payload": {"display_name": "Rascunho velho", "domain": "science", "test_id": "T-DRAFT", "question": "q"}})
    assert _test(root, "T-DRAFT")["status"] == "DRAFT"
    _hyp(root, "T-RUN")
    _apply(root, {"kind": "MUTATION_PROPOSAL", "created_at": "2026-10-01T00:00:00Z",
                  "payload": {"test_id": "T-RUN", "result": {"verdict": "PROMOTED"}}})
    _maintain(root)
    assert _test(root, "T-DRAFT")["status"] == "ARCHIVED"
    assert _test(root, "T-RUN")["prereg_audit"]["reason"] in {"FROZEN_BEFORE_RESULT", "PREREG_TIME_UNKNOWN"}
    # idempotent: a second run changes nothing about the audit
    assert not [r for r in _maintain(root) if r.get("entity_name") == "T-RUN"]


def test_roadmap_fdr_annotation_and_watchdog(tmp_path):
    root = _tower(tmp_path)
    for tid, p in (("T-1", 0.001), ("T-2", 0.04), ("T-3", 0.2)):
        _hyp(root, tid, roadmap_id="RM-F")
        _apply(root, {"kind": "MUTATION_PROPOSAL", "payload": {"test_id": tid, "result": {"verdict": "PROMOTED", "p_value": p}}})
    _maintain(root)
    fdr = {tid: _test(root, tid).get("fdr") for tid in ("T-1", "T-2", "T-3")}
    assert fdr["T-1"]["survives"] is True and fdr["T-3"]["survives"] is False and fdr["T-1"]["n"] == 3
    watchdog = evolution_status(root, public=True)["watchdog"]
    assert watchdog["checked_at"] and any(q["role"] == "PITIA" for q in watchdog["quiet"])


def test_board_posts_are_addressed_expire_and_hide_private(tmp_path):
    from datetime import datetime, timezone
    root = _tower(tmp_path)
    _apply(root, {"kind": "BOARD_POST", "source": "REFUTADOR", "created_at": "2026-09-28T10:00:00Z",
                  "payload": {"entries": [
                      {"to": "learner", "text": "Derrubei o teste X; pense numa rival.", "refs": ["T-X"], "id": "BP-1"},
                      {"to": "EXECUTOR", "text": "Precisa de prior do CMB.", "ttl_h": 2},
                      {"to": "ALL", "text": "nota privada", "refs": ["OLY-ABC"]}]}})
    task = evolution_status(root, now=datetime(2026, 9, 28, 13, tzinfo=timezone.utc))["board"]
    assert [p["to"] for p in task] == ["LEARNER", "ALL"]          # the 2 h note expired
    public = evolution_status(root, public=True)["board"]
    assert all("privada" not in p["text"] for p in public) and len(public) == 2
    _apply(root, {"kind": "BOARD_POST", "source": "LEARNER", "payload": {"resolve": ["BP-1"]}})
    task = evolution_status(root, now=datetime(2026, 9, 28, 13, tzinfo=timezone.utc))["board"]
    assert [p["to"] for p in task] == ["ALL"]


def test_referee_queue_holds_only_reviewable_originals_oldest_first(tmp_path):
    """Attacks are evidence, never attackable: queueing them starved real originals (2026-09-29:
    17 of 30 referee_1 entries were CONTEST-* attacks, sorted ahead of the originals)."""
    root = _tower(tmp_path)
    for test_id, when in (("T-NEW", "2026-09-25T05:00:00Z"), ("T-OLD", "2026-09-25T02:00:00Z")):
        _apply(root, {"kind": "HYPOTHESIS_PROPOSAL", "_inbox_name": f"{test_id}.json", "payload": {
            "display_name": test_id, "domain": "science", "test_id": test_id, "question": "q",
            "success_criteria": "s", "kill_criteria": "k", "rank_score": 0.5}})
        _apply(root, {"kind": "MUTATION_PROPOSAL", "created_at": when,
                      "payload": {"test_id": test_id, "result": {"verdict": "PROMOTED"}}})
    _apply(root, {"kind": "CONTEST", "payload": {"test_id": "T-OLD", "reason": "r",
                                                 "contest_test": {"question": "sobrevive?", "success_criteria": "a", "kill_criteria": "b"}}})
    _apply(root, {"kind": "MUTATION_PROPOSAL", "created_at": "2026-09-25T06:00:00Z",
                  "payload": {"test_id": "CONTEST-T-OLD-1", "result": {"verdict": "PROMOTED"}}})
    assert _test(root, "CONTEST-T-OLD-1")["contests_test_id"] == "T-OLD"
    queue = evolution_status(root)["review_queue"]
    assert "CONTEST-T-OLD-1" not in queue["referee_1"] + queue["referee_2"]
    # The older original already has an attack occupying its slot. Preserve it
    # as pending completion, without offering a duplicate attack to Referee 1.
    assert [t for t in queue["referee_1"] if t in {"T-OLD", "T-NEW"}] == ["T-NEW"]
    assert "T-OLD" in queue["waiting_on_existing_contest"]
