"""Private bridge commitments and policy checks using synthetic Tower records."""
import copy
import hashlib
import json

from runtime.nexo_agent_api import autonomy as a, evolution as e, public_campaigns as p, scientific_integrity as s
from runtime.nexo_agent_api.tower_apply import apply_requests
from tests.test_autonomy_prepared import root, approval, apply_approval, charter_body, public_test, STAMP
from tests.test_scientific_integrity import save, store_fixture_test


def bilingual(pt="Pergunta pública?", en="Public question?"):
    return {"pt-BR": pt, "en": en}


def campaign(root):
    apply_approval(root, approval())
    body = charter_body()
    body["public_presentation"] = {"question": bilingual(), "updatedAt": STAMP, "references": []}
    assert all(row["accepted"] for row in apply_requests(root, e.charter_requests({"created_at": STAMP}, body, root)))
    return body


def test_dormant_writer_never_creates_public_approvals(root):
    assert p.publication_requests(root) == []
    assert apply_requests(root, [{"document": p.REGISTRY, "merge": {"approvals": []}}])[0]["accepted"] is False


def test_policy_marks_pending_and_does_not_invent_missing_bindings(root):
    body = campaign(root)
    private = dict(body, roadmap_id="RM-PRIVATE", question_id="QUESTION-PRIVATE", visibility="PRIVATE")
    save(root, "roadmaps/RM-PRIVATE.json", private)
    requests = p.publication_requests(root)
    assert len(requests) == 1
    assert requests[0]["merge"]["delivery"]["status"] == "PENDING_PUBLICATION"
    assert all(row["accepted"] for row in apply_requests(root, requests))
    assert p.publication_requests(root) == []
    value = p.export(root)
    assert [row["sourceId"] for row in value["approvals"]] == [body["roadmap_id"]]
    assert "RM-PRIVATE" not in json.dumps(value)
    record = value["records"]["roadmaps"][0]
    saved = value["source_commitments"][record["id"]]
    assert json.loads(saved["json"]) == record
    assert hashlib.sha256(saved["json"].encode()).hexdigest() == saved["sha256"]


def test_stale_byte_bound_approval_cannot_be_renewed_by_export(root):
    body = campaign(root)
    apply_requests(root, p.publication_requests(root))
    roadmap = a.read(root, "roadmaps/RM-Q.json")
    roadmap["status"] = "PAUSED"
    save(root, "roadmaps/RM-Q.json", roadmap)
    assert p.export(root)["approvals"] == []
    # The Writer may approve the new state and preserve the previous delivery.
    registry = a.read(root, p.REGISTRY)
    registry["delivery"]["last_verified_at"] = STAMP
    save(root, p.REGISTRY, registry)
    update = p.publication_requests(root)[0]
    assert update["merge"]["delivery"]["last_verified_at"] == STAMP


def test_unreviewed_result_is_withheld_and_progress_has_actual_runner_facts(root):
    campaign(root)
    source = public_test(root)
    source.update(roadmap_id="RM-Q", question_id="QUESTION-EXPLICIT", execution_phase="RUNNING", status="RUNNING",
                  run_ref="actions/runs/123", started_at=STAMP, execution_observation="GITHUB_JOB_STEP",
                  public_presentation={"question": bilingual(), "stage": "REVIEWED", "updatedAt": STAMP,
                                       "result": {"verdict": "SUPPORTS", "summary": bilingual("Resultado alegado", "Claimed result")}})
    source["private_note"] = "SECRET-RAW-SOURCE"
    save(root, "entities/test/TEST-A.json", source)
    apply_requests(root, p.publication_requests(root))
    value = p.export(root)
    approval_entry = next(row for row in value["approvals"] if row["kind"] == "TEST")
    assert "result" not in approval_entry["presentation"]
    assert "independence" not in approval_entry
    record = value["records"]["tests"][0]
    assert record["question_id"] == "QUESTION-EXPLICIT"
    assert record["started_at"] == STAMP and record["execution_observation"] == "GITHUB_JOB_STEP"
    assert "SECRET-RAW-SOURCE" not in json.dumps(value)


def test_independence_proof_is_fresh_and_binds_exact_normalized_bytes(root):
    campaign(root)
    source = public_test(root)
    source.update(roadmap_id="RM-Q", question_id="QUESTION-EXPLICIT", status="DONE", state="DONE", verdict="PROMOTED",
                  executed_at=STAMP, review_state="CONFIRMED", reviews=[{
                      "referee": "REFEREE_1", "outcome": "SURVIVED", "contest_test_id": "ATTACK-A", "at": STAMP}],
                  public_presentation={"question": bilingual(), "stage": "REVIEWED", "updatedAt": STAMP,
                                       "result": {"verdict": "SUPPORTS", "summary": bilingual("Resultado sintético", "Synthetic result")}})
    attack = store_fixture_test(root, "ATTACK-A", visibility="PUBLIC", question_id="QUESTION-EXPLICIT", roadmap_id="RM-Q",
                                dataset_and_selection="Independent synthetic sample B", contests_test_id="TEST-A",
                                executed_at=STAMP, verdict="PROMOTED", state="DONE", status="DONE")
    declaration = {"axis": "data", "frozen_at": attack["frozen_at"], "on_pass": "CONFIRMED", "on_fail": "REFUTED",
                   "evidence_refs": ["entities/evidence/input-b.json"]}
    attack.update(independence=declaration, independence_fingerprint=s.digest(declaration))
    save(root, "entities/evidence/input-b.json", {"id": "input-b", "source": "synthetic_fixture"})
    save(root, "entities/test/ATTACK-A.json", attack)
    save(root, "entities/test/TEST-A.json", source)
    assert s.independence(source, attack, root)["eligible"]
    apply_requests(root, p.publication_requests(root))
    value = p.export(root)
    entry = next(row for row in value["approvals"] if row["sourceId"] == "TEST-A")
    assert entry["independence"]["writerParentSha256"] == value["source_commitments"]["TEST-A"]["sha256"]
    assert entry["independence"]["writerAttackSha256"] == value["source_commitments"]["ATTACK-A"]["sha256"]
    assert "result" in entry["presentation"]
    # Evidence cannot be renewed merely because an old review was approved.
    attack["dataset_and_selection"] = source["dataset_and_selection"]
    save(root, "entities/test/ATTACK-A.json", attack)
    fresh = next(row for row in p.export(root)["approvals"] if row["sourceId"] == "TEST-A")
    assert "independence" not in fresh and "result" not in fresh["presentation"]


def test_operational_closure_never_infers_scientific_outcome(root):
    campaign(root)
    forged = {"document": "roadmaps/RM-Q.json", "merge": {"closure": {"outcome": "SUPPORTS"}}}
    assert apply_requests(root, [forged])[0]["accepted"] is False
    requests = e.close_requests({"created_at": STAMP}, {"roadmap_id": "RM-Q", "reason": "SUCCESS", "outcome": "SUPPORTS"}, root)
    assert all(row["accepted"] for row in apply_requests(root, requests))
    source = a.read(root, "roadmaps/RM-Q.json")
    assert source["closure"]["outcome"] is None and source["closure"]["reason"] == "SUCCESS"
    assert source["public_presentation"]["closure"]["receiptId"] == source["closure"]["receipt_id"]
    apply_requests(root, p.publication_requests(root))
    closure = p.export(root)["approvals"][0]["presentation"]["closure"]
    assert closure["outcome"] is None and closure["summary"]["pt-BR"] == "Campanha encerrada."
