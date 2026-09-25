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
    requests = _apply(root, {"kind": "HYPOTHESIS_PROPOSAL", "_inbox_name": "h1.json", "payload": {
        "test_id": "T-1", "roadmap_id": "RM-X", "question": "q", "success_criteria": "s", "kill_criteria": "k", "rank_score": 0.8}})
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
    _apply(root, {"kind": "HYPOTHESIS_PROPOSAL", "payload": {"test_id": "T-D", "question": "q", "success_criteria": "s", "kill_criteria": "k"}})
    _apply(root, {"kind": "MUTATION_PROPOSAL", "payload": {"test_id": "T-D", "result": {"verdict": "PROMOTED"}}})
    commitment = hashlib.sha256(b"T-D:segredo").hexdigest()
    _apply(root, {"kind": "DECOY_PLANT", "payload": {"commitment": commitment}})
    _apply(root, {"kind": "DECOY_REVEAL", "payload": {"test_id": "T-D", "secret": "errado"}})
    assert not _test(root, "T-D").get("decoy")
    _apply(root, {"kind": "DECOY_REVEAL", "payload": {"test_id": "T-D", "secret": "segredo"}})
    test = _test(root, "T-D")
    assert test["decoy"] is True and test["decoy_caught"] is False
    assert evolution_status(root)["decoys"] == {"planted": 1, "revealed": 1, "caught": 0}
