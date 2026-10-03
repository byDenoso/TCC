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


def test_positive_result_needs_independent_attack_and_stop_criterion_fires(tmp_path):
    root = _tower(tmp_path)
    _apply(root, {"kind": "ROADMAP_CHARTER", "payload": {"roadmap_id": "RM-X", "question": "q", "stop": {"success_confirmed": 1}}})
    _apply(root, {"kind": "OPERATOR_INTENT", "source": "DENER", "created_at": "2026-09-25T00:00:00Z",
                  "payload": {"action": "APPROVE_CHARTER", "roadmap_id": "RM-X"}})
    requests = _apply(root, {"kind": "HYPOTHESIS_PROPOSAL", "_inbox_name": "h1.json", "payload": {"display_name": "Teste de exemplo", "domain": "science", 
        "test_id": "T-1", "roadmap_id": "RM-X", "question": "q", "method": "frozen method", "data": "fixture dataset",
        "success_criteria": "s", "kill_criteria": "k", "null": "n", "rival": "r", "rank_score": 0.8}})
    assert requests[0]["changes"]["prereg_hash"].startswith("sha256:")
    _apply(root, {"kind": "MUTATION_PROPOSAL", "created_at": "2026-09-25T02:00:00Z",
                  "payload": {"test_id": "T-1", "result": {"verdict": "PROMOTED"}, "prediction": {"p_promoted": 0.3}}})
    assert _test(root, "T-1")["review_state"] == "PENDING_REVIEW"
    status = evolution_status(root)
    assert status["review_queue"]["referee_1"] == ["T-1"]
    evidence = root / "entities/evidence/independent-fixture.json"
    evidence.parent.mkdir(parents=True, exist_ok=True)
    evidence.write_text(json.dumps({"source": "independent fixture B"}))
    _apply(root, {"kind": "CONTEST", "created_at": "2026-09-25T03:00:00Z", "payload": {"test_id": "T-1", "reason": "janela diferente",
                 "contest_test": {"question": "sobrevive?", "null": "n", "rival": "r", "method": "frozen method",
                                  "dataset_and_selection": "independent fixture B", "success_criteria": "a", "kill_criteria": "b",
                                  "independence": {"axis": "data", "evidence_refs": ["entities/evidence/independent-fixture.json"],
                                                   "frozen_at": "2026-09-25T03:00:00Z", "on_pass": "CONFIRMED", "on_fail": "REFUTED"}}}})
    assert _test(root, "T-1")["review_state"] == "CONTESTED"
    assert _test(root, "CONTEST-T-1-1")["contests_test_id"] == "T-1"
    _apply(root, {"kind": "VERDICT_REVIEW", "payload": {"test_id": "T-1", "referee": 1, "outcome": "SURVIVED"}})
    assert _test(root, "T-1")["review_state"] == "CONTESTED"  # an unbacked review cannot confirm
    _apply(root, {"kind": "MUTATION_PROPOSAL", "created_at": "2026-09-25T04:00:00Z",
                  "payload": {"test_id": "CONTEST-T-1-1", "result": {"verdict": "PROMOTED"}}})
    # A legacy terminal result can retain RUNNING as its historical phase.
    # A later evidence-backed review must not be mistaken for a new terminal write.
    parent = _test(root, "T-1")
    parent["execution_phase"] = "RUNNING"
    entity_path(root, "test", "T-1").write_text(json.dumps(parent, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    _apply(root, {"kind": "VERDICT_REVIEW", "payload": {"test_id": "T-1", "contest_test_id": "CONTEST-T-1-1"}})
    assert _test(root, "T-1")["review_state"] == "CONFIRMED"
    assert _test(root, "T-1")["execution_phase"] == "RUNNING"
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


def test_battery_dispatch_and_collect(tmp_path, monkeypatch):
    from tests.test_scientific_integrity import install_fixture_catalog, store_fixture_test, NOW, END
    from runtime.nexo_agent_api import scientific_integrity as integrity
    root = _tower(tmp_path)
    install_fixture_catalog(tmp_path / 'recipes', monkeypatch, 'seed_bounds')
    for tid in ("T-A", "T-B"):
        store_fixture_test(root, tid, 'seed_bounds', {'seed': 17})
    _apply(root, {"kind": "TEST_BATTERY", "created_at": "2026-09-25T14:00:00Z", "payload": {"battery_id": "bat-1", "tests": [
        {"test_id": "T-A", "recipe": "seed_bounds", "params": {"n": [10]}, "prediction": {"p_promoted": 0.2}},
        {"test_id": "T-B", "recipe": "seed_bounds"}, {"test_id": "MISSING", "recipe": "seed_bounds"},
        {"test_id": "T-A", "script": "print(1)"}]}})
    from runtime.nexo_agent_api.evolution import pending_batteries
    assert pending_batteries(root) == []  # invalid/duplicate/inline-code members reject the whole envelope
    _apply(root, {"kind": "TEST_BATTERY", "created_at": NOW, "payload": {"battery_id": "bat-valid", "tests": [
        {"test_id": tid, "recipe": "seed_bounds", "params": {"seed": 17}} for tid in ('T-A', 'T-B')]}})
    assert [b['id'] for b in pending_batteries(root)] == ['bat-valid']
    assert _test(root, "T-A")["status"] == "QUEUED"
    specs = {x['test_id']: x for x in integrity.batteries(root)[0]['tests']}
    _apply(root, {"kind": "BATTERY_STATUS", "_inbox_source": "RUNNER_OBSERVATION", "payload": {
        "battery_id": "bat-valid", "status": "RUNNING", "run_ref": "actions/runs/123", "started_tests": {'T-A': NOW, 'T-B': NOW}}})
    assert pending_batteries(root) == []
    _apply(root, {"kind": "BATTERY_STATUS", "_inbox_source": "RUNNER_OBSERVATION", "payload": {"battery_id": "bat-valid", "status": "DONE",
        "run_ref": "actions/runs/123", "completed_at": END, "conclusion": "success", "results": [
        {"test_id": "T-A", "ok": True, "attempt_id": specs['T-A']['attempt_id'], "recipe_sha256": specs['T-A']['recipe_sha256'], "result": {"verdict": "PROMOTED", "summary": "x"}},
        {"test_id": "T-B", "ok": False, "log_tail": "Traceback"}]}})
    assert _test(root, "T-A")["verdict"] == "PROMOTED" and _test(root, "T-A")["review_state"] == "PENDING_REVIEW"
    assert _test(root, "T-B")["status"] == "READY" and "Traceback" in _test(root, "T-B")["last_runtime_failure"]["log_tail"]
    assert evolution_status(root)["batteries"] == {"QUEUED": 0, "DISPATCH_PENDING": 0, "DISPATCHED": 0, "RUNNING": 0, "DONE": 1}


def _hyp(root, tid, *, created_at=None, **extra):
    _apply(root, {"kind": "HYPOTHESIS_PROPOSAL", "created_at": created_at, "payload": {"display_name": f"Teste {tid}", "domain": "science",
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


def test_second_runtime_failure_blocks_instead_of_recycling(tmp_path, monkeypatch):
    from tests.test_scientific_integrity import install_fixture_catalog, store_fixture_test, END
    root = _tower(tmp_path)
    install_fixture_catalog(tmp_path / 'recipes', monkeypatch, 'seed_bounds')
    store_fixture_test(root, 'T-F', 'seed_bounds', {'seed': 17})
    for n in (1, 2):
        _apply(root, {"kind": "TEST_BATTERY", "payload": {"battery_id": f"bat-f{n}", "tests": [{"test_id": "T-F", "recipe": "seed_bounds", "params": {'seed': 17}}]}})
        _apply(root, {"kind": "BATTERY_STATUS", "_inbox_source": "RUNNER_OBSERVATION", "payload": {"battery_id": f"bat-f{n}", "status": "DONE", "run_ref": f"actions/runs/{123+n}", "completed_at": END,
                                                            "results": [{"test_id": "T-F", "ok": False, "log_tail": "ImportError"}]}})
        state = _test(root, "T-F")["status"]
        assert state == ("READY" if n == 1 else "BLOCKED_INPUT")
    assert "2 vezes" in _test(root, "T-F")["blocker"]


def test_maintenance_archives_stale_drafts_and_audits_prereg(tmp_path):
    from datetime import datetime, timezone
    root = _tower(tmp_path)
    _apply(root, {"kind": "HYPOTHESIS_PROPOSAL", "created_at": "2026-09-01T00:00:00Z",
                  "payload": {"display_name": "Rascunho velho", "domain": "science", "test_id": "T-DRAFT", "question": "q"}})
    assert _test(root, "T-DRAFT")["status"] == "DRAFT"
    _hyp(root, "T-RUN", created_at="2026-09-30T00:00:00Z")
    _apply(root, {"kind": "MUTATION_PROPOSAL", "created_at": "2026-10-01T00:00:00Z",
                  "payload": {"test_id": "T-RUN", "result": {"verdict": "PROMOTED"}}})
    now = datetime.now(timezone.utc)
    _maintain(root, now)
    assert _test(root, "T-DRAFT")["status"] == "ARCHIVED"
    assert _test(root, "T-RUN")["prereg_audit"]["reason"] in {"FROZEN_BEFORE_RESULT", "PREREG_TIME_UNKNOWN"}
    # idempotent: a second run changes nothing about the audit
    assert not [r for r in _maintain(root, now) if r.get("entity_name") == "T-RUN"]


def test_stale_draft_archive_cannot_claim_a_future_writer_time(tmp_path):
    from datetime import datetime, timedelta, timezone
    root = _tower(tmp_path)
    now = datetime.now(timezone.utc)
    _apply(root, {
        "kind": "HYPOTHESIS_PROPOSAL",
        "created_at": (now - timedelta(days=30)).isoformat(),
        "payload": {
            "display_name": "Stale draft fixture",
            "domain": "science",
            "test_id": "T-FUTURE-ARCHIVE",
            "question": "q",
        },
    })
    current = _test(root, "T-FUTURE-ARCHIVE")
    assert current["status"] == "DRAFT"
    receipt = apply_requests(root, [{
        "request_id": "REQ-FUTURE-STALE-DRAFT-ARCHIVE",
        "entity_kind": "test",
        "entity_name": "T-FUTURE-ARCHIVE",
        "expected_version": current["entity_version"],
        "writer_role": "ADVISOR",
        "event_type": "TEST_ARCHIVED",
        "changes": {
            "status": "ARCHIVED",
            "state": "ARCHIVED",
            "archive_reason": "stale_draft",
            "archived_at": (now + timedelta(days=1)).isoformat(),
        },
    }])[0]
    assert not receipt["accepted"]
    assert receipt["issue"]["code"] == "TERMINAL_STATUS_REQUIRES_RESULT_EVENT"
    assert _test(root, "T-FUTURE-ARCHIVE") == current


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


def test_board_generated_ids_are_stable_unique_and_resolve_only_the_target(tmp_path):
    from datetime import datetime, timezone

    root = _tower(tmp_path)
    created_at = "2026-10-03T00:02:44Z"
    first = {"kind": "BOARD_POST", "source": "ENGINEER", "created_at": created_at,
             "_inbox_name": "engineer-backlog.json",
             "payload": {"to": "GUARDIAO", "text": "Backlog relido.", "refs": ["WORK-A"]}}
    second = {"kind": "BOARD_POST", "source": "ENGINEER", "created_at": created_at,
              "_inbox_name": "engineer-terminal.json",
              "payload": {"to": "GUARDIAO", "text": "Fase terminal relida.", "refs": ["WORK-B"]}}

    first_request = proposal_to_requests(first, root)[0]
    replay_request = proposal_to_requests(first, root)[0]
    first_id = first_request["merge"]["posts"][-1]["id"]
    replay_id = replay_request["merge"]["posts"][-1]["id"]
    [first_receipt] = apply_requests(root, [first_request])
    assert first_receipt.get("accepted", True) is not False, first_receipt

    # The Writer converts/applies envelopes serially, so the second conversion
    # sees the first post in the canonical board document.
    second_request = proposal_to_requests(second, root)[0]
    second_id = second_request["merge"]["posts"][-1]["id"]
    assert first_id == replay_id
    assert first_request["request_id"] == replay_request["request_id"]
    assert first_id != second_id
    assert first_request["request_id"] != second_request["request_id"]

    [second_receipt] = apply_requests(root, [second_request])
    assert second_receipt.get("accepted", True) is not False, second_receipt
    posts = evolution_status(root, now=datetime(2026, 10, 3, 1, tzinfo=timezone.utc))["board"]
    assert {post["id"] for post in posts} == {first_id, second_id}

    _apply(root, {"kind": "BOARD_POST", "source": "GUARDIAO", "created_at": created_at,
                  "payload": {"resolve": [first_id]}})
    remaining = evolution_status(root, now=datetime(2026, 10, 3, 1, tzinfo=timezone.utc))["board"]
    assert [post["id"] for post in remaining] == [second_id]


def test_board_id_fallback_and_legacy_explicit_linkage_are_preserved(tmp_path):
    root = _tower(tmp_path)
    first = {"kind": "BOARD_POST", "source": "ENGINEER", "created_at": "2026-10-03T00:02:44Z",
             "payload": {"to": "GUARDIAO", "text": "Primeiro corpo."}}
    second = {"kind": "BOARD_POST", "source": "ENGINEER", "created_at": "2026-10-03T00:02:44Z",
              "payload": {"to": "GUARDIAO", "text": "Segundo corpo."}}
    first_request = proposal_to_requests(first, root)[0]
    second_request = proposal_to_requests(second, root)[0]
    first_id = first_request["merge"]["posts"][-1]["id"]
    second_id = second_request["merge"]["posts"][-1]["id"]
    assert first_id != second_id
    assert proposal_to_requests(first, root)[0]["merge"]["posts"][-1]["id"] == first_id

    undated = {"kind": "BOARD_POST", "source": "ENGINEER",
               "payload": {"to": "GUARDIAO", "text": "Envelope legado sem data."}}
    undated_id = proposal_to_requests(undated, root)[0]["merge"]["posts"][-1]["id"]
    assert undated_id.startswith("BP-UNDATED-ENGINEER-")
    assert proposal_to_requests(undated, root)[0]["merge"]["posts"][-1]["id"] == undated_id

    explicit = {"kind": "BOARD_POST", "source": "GUARDIAO", "created_at": "2026-10-03T00:03:00Z",
                "payload": {"to": "ENGINEER", "text": "Resposta legada.",
                            "id": "BP-LEGACY-EXPLICIT", "reply_to": first_id}}
    explicit_post = proposal_to_requests(explicit, root)[0]["merge"]["posts"][-1]
    assert explicit_post["id"] == "BP-LEGACY-EXPLICIT"
    assert explicit_post["reply_to"] == first_id


def test_board_explicit_id_replay_is_noop_and_incompatible_reuse_is_rejected(tmp_path):
    from runtime.nexo_agent_api.inbox_apply import ProposalError

    root = _tower(tmp_path)
    original = {"kind": "BOARD_POST", "source": "ENGINEER", "created_at": "2026-10-03T00:03:00Z",
                "payload": {"to": "GUARDIAO", "text": "Identidade explícita.", "id": "BP-SAME"}}
    _apply(root, original)
    [replay] = proposal_to_requests(original, root)
    assert replay["changes"]["kind"] == "BOARD_POST_NOOP"
    assert replay["changes"]["payload"]["_noop_reason"] == "BOARD_MESSAGE_ALREADY_RECORDED"

    incompatible = {"kind": "BOARD_POST", "source": "ENGINEER", "created_at": "2026-10-03T00:03:00Z",
                    "payload": {"to": "GUARDIAO", "text": "Outro conteúdo.", "id": "BP-SAME"}}
    [rejected] = proposal_to_requests(incompatible, root)
    assert rejected["changes"]["kind"] == "UNAPPLIED_BOARD_POST"
    assert rejected["changes"]["payload"]["_not_applied_reason"] == "BOARD_ID_COLLISION"

    posts = json.loads((root / "evolution" / "board.json").read_text(encoding="utf-8"))["posts"]
    assert [(post["id"], post["text"]) for post in posts] == [("BP-SAME", "Identidade explícita.")]

    batch = {"kind": "BATCH", "source": "ENGINEER", "created_at": "2026-10-03T00:03:00Z",
             "payload": {"items": [original, incompatible]}}
    empty_root = _tower(tmp_path / "batch")
    try:
        proposal_to_requests(batch, empty_root)
    except ProposalError as exc:
        assert str(exc) == "BOARD_ID_COLLISION"
    else:
        raise AssertionError("generic BATCH silently overwrote an incompatible BOARD_POST id")


def test_writer_keeps_same_minute_board_envelopes_distinct_and_replay_idempotent(tmp_path):
    from runtime.nexo_agent_api.gpt_writer import apply_to_tower
    from runtime.nexo_agent_api.live_tower import build_live_tower_payload, materialize_live_tower

    root = _tower(tmp_path)
    created_at = "2026-10-03T00:02:44Z"
    items = [
        {"kind": "BOARD_POST", "source": "ENGINEER", "created_at": created_at,
         "_inbox_name": "engineer-backlog.json",
         "payload": {"to": "GUARDIAO", "text": "Backlog relido.", "refs": ["WORK-A"]}},
        {"kind": "BOARD_POST", "source": "ENGINEER", "created_at": created_at,
         "_inbox_name": "engineer-terminal.json",
         "payload": {"to": "GUARDIAO", "text": "Fase terminal relida.", "refs": ["WORK-B"]}},
    ]
    (root / "CONTROL.json").write_text(
        json.dumps({"truth_owner": "TOWER_V06@GOOGLE_DRIVE_PRIVATE"}), encoding="utf-8")
    raw = json.dumps(build_live_tower_payload(root), ensure_ascii=False).encode("utf-8")
    changed, report = apply_to_tower(raw, items)
    assert changed is not None, report

    readback, _ = materialize_live_tower(changed, tmp_path / "readback")
    posts = evolution_status(readback)["board"]
    assert len(posts) == 2
    ids = [post["id"] for post in posts]
    assert len(set(ids)) == 2

    replayed, replay_report = apply_to_tower(changed, items)
    assert not replay_report["rejected"], replay_report
    replay_bundle = replayed or changed
    replay_root, _ = materialize_live_tower(replay_bundle, tmp_path / "replay")
    replay_posts = evolution_status(replay_root)["board"]
    assert [post["id"] for post in replay_posts] == ids

    resolved, resolve_report = apply_to_tower(replay_bundle, [{
        "kind": "BOARD_POST", "source": "GUARDIAO", "created_at": "2026-10-03T00:04:00Z",
        "_inbox_name": "resolve-first.json", "payload": {"resolve": [ids[0]]},
    }])
    assert resolved is not None, resolve_report
    resolved_root, _ = materialize_live_tower(resolved, tmp_path / "resolved")
    assert [post["id"] for post in evolution_status(resolved_root)["board"]] == [ids[1]]


def test_writer_batch_children_get_distinct_board_and_request_identities(tmp_path):
    from runtime.nexo_agent_api.gpt_writer import apply_to_tower
    from runtime.nexo_agent_api.gpt_writer import _gateway_results
    from runtime.nexo_agent_api.live_tower import build_live_tower_payload, materialize_live_tower

    root = _tower(tmp_path)
    (root / "CONTROL.json").write_text(
        json.dumps({"truth_owner": "TOWER_V06@GOOGLE_DRIVE_PRIVATE"}), encoding="utf-8")
    created_at = "2026-10-03T00:02:44Z"
    batch = {
        "kind": "BATCH", "source": "ENGINEER", "created_at": created_at,
        "_inbox_source": "GATEWAY", "_inbox_id": "gateway:shared-parent",
        "_inbox_name": "gw-shared-parent",
        "payload": {"items": [
            {"kind": "BOARD_POST", "source": "ENGINEER", "created_at": created_at,
             "payload": {"to": "GUARDIAO", "text": "Primeiro filho."}},
            {"kind": "BOARD_POST", "source": "ENGINEER", "created_at": created_at,
             "payload": {"to": "GUARDIAO", "text": "Segundo filho."}},
        ]},
    }
    raw = json.dumps(build_live_tower_payload(root), ensure_ascii=False).encode("utf-8")
    changed, report = apply_to_tower(raw, [batch])
    assert changed is not None, report
    assert not report["rejected"], report
    payload, reported, resolved = _gateway_results(report, ["shared-parent"])
    assert reported == resolved == ["shared-parent"]
    assert payload["items"][0]["outcome"] == "APPLIED"
    assert len(payload["items"][0]["receipts"]) == 2

    readback, _ = materialize_live_tower(changed, tmp_path / "batch-readback")
    posts = evolution_status(readback)["board"]
    assert [post["text"] for post in posts] == ["Primeiro filho.", "Segundo filho."]
    assert len({post["id"] for post in posts}) == 2


def test_generic_batch_board_requests_compose_without_overwrite(tmp_path):
    root = _tower(tmp_path)
    created_at = "2026-10-03T00:02:44Z"
    batch = {
        "kind": "BATCH", "source": "ENGINEER", "created_at": created_at,
        "_inbox_id": "generic-parent", "_inbox_name": "generic-parent",
        "payload": {"items": [
            {"kind": "BOARD_POST", "source": "ENGINEER", "created_at": created_at,
             "payload": {"to": "GUARDIAO", "text": "Primeiro genérico."}},
            {"kind": "BOARD_POST", "source": "ENGINEER", "created_at": created_at,
             "payload": {"to": "GUARDIAO", "text": "Segundo genérico."}},
        ]},
    }
    requests = proposal_to_requests(batch, root)
    assert len(requests) == 2
    assert len(requests[0]["merge"]["posts"]) == 1
    assert len(requests[1]["merge"]["posts"]) == 2
    receipts = apply_requests(root, requests)
    assert all(receipt.get("accepted", True) is not False for receipt in receipts), receipts
    posts = evolution_status(root)["board"]
    assert [post["text"] for post in posts] == ["Primeiro genérico.", "Segundo genérico."]


def test_generic_batch_can_resolve_a_post_created_by_an_earlier_child(tmp_path):
    root = _tower(tmp_path)
    created_at = "2026-10-03T00:02:44Z"
    batch = {"kind": "BATCH", "source": "ENGINEER", "created_at": created_at,
             "payload": {"items": [
                 {"kind": "BOARD_POST", "source": "ENGINEER", "created_at": created_at,
                  "payload": {"to": "GUARDIAO", "text": "Criado e fechado.", "id": "BP-X"}},
                 {"kind": "BOARD_POST", "source": "GUARDIAO", "created_at": created_at,
                  "payload": {"resolve": ["BP-X"]}},
             ]}}
    requests = proposal_to_requests(batch, root)
    assert len(requests) == 2
    resolved = next(post for post in requests[1]["merge"]["posts"] if post["id"] == "BP-X")
    assert resolved["resolved_at"] == created_at
    receipts = apply_requests(root, requests)
    assert all(receipt.get("accepted", True) is not False for receipt in receipts), receipts
    posts = json.loads((root / "evolution" / "board.json").read_text(encoding="utf-8"))["posts"]
    assert posts[0]["id"] == "BP-X" and posts[0]["resolved_at"] == created_at
    assert evolution_status(root)["board"] == []


def test_composed_board_snapshots_never_reopen_a_resolved_post(tmp_path):
    from runtime.nexo_agent_api.inbox_apply import compose_board_snapshots

    root = _tower(tmp_path)
    created_at = "2026-10-03T00:02:44Z"
    _apply(root, {"kind": "BOARD_POST", "source": "ENGINEER", "created_at": created_at,
                  "payload": {"to": "GUARDIAO", "text": "Fechar depois.", "id": "BP-1"}})
    resolve = proposal_to_requests({"kind": "BOARD_POST", "source": "GUARDIAO", "created_at": created_at,
                                    "payload": {"resolve": ["BP-1"]}}, root)[0]
    add = proposal_to_requests({"kind": "BOARD_POST", "source": "ENGINEER", "created_at": created_at,
                                "payload": {"to": "GUARDIAO", "text": "Novo recado."}}, root)[0]
    [resolved_request, add_request] = compose_board_snapshots([resolve, add])
    assert resolved_request["merge"]["posts"][0]["resolved_at"] == created_at
    assert add_request["merge"]["posts"][0]["resolved_at"] == created_at
    receipts = apply_requests(root, [resolved_request, add_request])
    assert all(receipt.get("accepted", True) is not False for receipt in receipts), receipts
    visible = evolution_status(root)["board"]
    assert [post["text"] for post in visible] == ["Novo recado."]


def test_stale_board_request_merges_with_concurrent_post_instead_of_losing_it(tmp_path):
    root = _tower(tmp_path)
    created_at = "2026-10-03T00:02:44Z"
    stale_request = proposal_to_requests({
        "kind": "BOARD_POST", "source": "ENGINEER", "created_at": created_at,
        "_inbox_name": "stale.json",
        "payload": {"to": "GUARDIAO", "text": "Planejado no snapshot A."},
    }, root)[0]
    assert stale_request["list_merge"] == {"posts": "id"}

    _apply(root, {"kind": "BOARD_POST", "source": "GUARDIAO", "created_at": created_at,
                  "payload": {"to": "ENGINEER", "text": "Concorrente no snapshot B."}})
    [receipt] = apply_requests(root, [stale_request])
    assert receipt.get("accepted", True) is not False, receipt
    posts = json.loads((root / "evolution" / "board.json").read_text(encoding="utf-8"))["posts"]
    assert {post["text"] for post in posts} == {
        "Planejado no snapshot A.", "Concorrente no snapshot B.",
    }


def test_stale_explicit_board_id_cannot_overwrite_concurrent_content(tmp_path):
    root = _tower(tmp_path)
    created_at = "2026-10-03T00:02:44Z"
    stale = proposal_to_requests({
        "kind": "BOARD_POST", "source": "ENGINEER", "created_at": created_at,
        "payload": {"to": "GUARDIAO", "text": "Snapshot A.", "id": "BP-SAME"},
    }, root)[0]
    _apply(root, {"kind": "BOARD_POST", "source": "ENGINEER", "created_at": created_at,
                  "payload": {"to": "GUARDIAO", "text": "Snapshot B.", "id": "BP-SAME"}})

    [receipt] = apply_requests(root, [stale])
    assert receipt["accepted"] is False
    assert receipt["issue"]["code"] == "BOARD_ID_COLLISION"
    posts = json.loads((root / "evolution" / "board.json").read_text(encoding="utf-8"))["posts"]
    assert [(post["id"], post["text"]) for post in posts] == [("BP-SAME", "Snapshot B.")]


def test_board_list_merge_keeps_legacy_ids_privacy_and_300_post_bound(tmp_path):
    root = _tower(tmp_path)
    requests = []
    for index in range(305):
        requests.extend(proposal_to_requests({
            "kind": "BOARD_POST", "source": "ENGINEER", "created_at": "2026-10-03T00:02:44Z",
            "_inbox_name": f"bounded-{index}.json",
            "payload": {"to": "GUARDIAO", "text": f"Post {index}", "id": f"BP-LEGACY-{index}",
                        "private": index == 304},
        }, root))
    receipts = apply_requests(root, requests)
    assert all(receipt.get("accepted", True) is not False for receipt in receipts), receipts
    stored = json.loads((root / "evolution" / "board.json").read_text(encoding="utf-8"))["posts"]
    assert len(stored) == 300
    assert stored[0]["id"] == "BP-LEGACY-5"
    assert stored[-1]["id"] == "BP-LEGACY-304" and stored[-1]["private"] is True
    assert all(post["id"] != "BP-LEGACY-304" for post in evolution_status(root, public=True)["board"])


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
