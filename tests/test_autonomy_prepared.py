"""Offline adversarial coverage; no Drive, scheduler or scientific production runs."""
import copy
import hashlib
import json
from unittest.mock import Mock
from datetime import datetime, timedelta, timezone

import pytest

from runtime.nexo_agent_api import autonomy as a, evolution as e, scientific_integrity as s
from runtime.nexo_agent_api.gpt_writer import apply_to_tower
from runtime.nexo_agent_api.inbox_apply import ProposalError, _result_request
from runtime.nexo_agent_api.live_tower import build_live_tower_payload, read_live_tower_bytes
from runtime.nexo_agent_api.tower_apply import apply_requests
from tests.test_scientific_integrity import save, store_fixture_test, install_fixture_catalog


NOW = datetime.now(timezone.utc).replace(microsecond=0)
STAMP = NOW.isoformat().replace("+00:00", "Z")


def approval(mid="AUTONOMY-1", revision=0, action="APPROVE_AUTONOMY_MANDATE"):
    return {"kind": "OPERATOR_INTENT", "source": "DENER", "created_at": STAMP,
            "payload": {"action": action, "mandate_id": mid, "expected_revision": revision,
                        "approval_ref": "HUMAN-FIXTURE-APPROVAL",
                        "activation_receipt": {"source_revision": "a" * 40, "tower_fingerprint": "b" * 64,
                                               "checked_at": STAMP, "checks": {key: True for key in
                                                   ("transport", "writer", "public_projection", "prompts", "quota")}}}}


def apply_approval(root, item):
    trusted = a.attach_human_authority(item, frozenset({a.envelope_hash(item)}))
    receipts = apply_requests(root, a.operator_requests(trusted, trusted["payload"], root))
    assert all(receipt["accepted"] for receipt in receipts), receipts


@pytest.fixture
def root(tmp_path, monkeypatch):
    root = tmp_path / "tower"
    save(root, "CONTROL.json", {"mode": "ACTIVE", "scientific_runtime": "CHATGPT_RUNTIME",
                              "truth_owner": "TOWER_V06@GOOGLE_DRIVE_PRIVATE",
                              "github_actions_science_role": "DISABLED_BUDGET_EXHAUSTED"})
    save(root, "indexes/active-roadmaps.json", {"items": []})
    install_fixture_catalog(tmp_path / "recipes", monkeypatch, "audit_recipe")
    monkeypatch.setenv("NEXO_RECIPE_REVISION", "a" * 40)
    return root


def public_test(root, tid="TEST-A"):
    test = store_fixture_test(root, tid, mandate_id="AUTONOMY-1", public_data_only=True, visibility="PUBLIC")
    test["data_binding"]["inputs"][0]["public"] = True
    save(root, "entities/test/" + tid + ".json", test)
    return test


def battery(root, tid="TEST-A", bid="bat-one"):
    test = s.entity(root, tid)
    return e.battery_requests({"source": "EXECUTOR"}, {"battery_id": bid, "tests": [
        {"test_id": tid, "recipe": test["recipe"], "params": test["recipe_params"]}]}, root)


def test_dormant_default_preserves_global_control(root):
    assert a.status(root)["status"] == "PREPARED_INACTIVE"
    assert not a.active(root)
    assert a.read(root, "CONTROL.json")["github_actions_science_role"] == "DISABLED_BUDGET_EXHAUSTED"


def test_client_metadata_cannot_authenticate_human(root):
    item = approval()
    item.update(_authenticated_human=True, authentication={"verified": True}, _autonomy_human_authority="HUMAN")
    untrusted = a.attach_human_authority(item, frozenset())
    with pytest.raises(ProposalError, match="AUTHENTICATED_HUMAN"):
        a.operator_requests(untrusted, item["payload"], root)
    assert not a.active(root)


def test_authentication_binds_exact_proposal_and_source(root):
    item = approval()
    changed = copy.deepcopy(item)
    changed["payload"]["mandate_id"] = "OTHER-ID"
    for forged in (changed, dict(item, source="EXECUTOR")):
        trusted = a.attach_human_authority(forged, {a.envelope_hash(item)})
        with pytest.raises(ProposalError, match="AUTHENTICATED_HUMAN"):
            a.operator_requests(trusted, forged["payload"], root)


def test_approval_revocation_replay_and_fresh_id(root):
    first = approval()
    apply_approval(root, first)
    assert a.active(root) and a.parallelism(root) == 1
    assert a.read(root, "CONTROL.json")["scientific_runtime"] == "CHATGPT_RUNTIME"
    apply_approval(root, first)  # identical approval is harmless
    assert a.mandate(root)["revision"] == 1
    apply_approval(root, approval(revision=1, action="REVOKE_AUTONOMY_MANDATE"))
    assert not a.active(root)
    with pytest.raises(ProposalError, match="REVISION_CONFLICT"):
        apply_approval(root, first)
    with pytest.raises(ProposalError, match="REVOKED_MANDATE"):
        apply_approval(root, approval(revision=2))
    apply_approval(root, approval("AUTONOMY-2", 2))
    assert a.active(root, "AUTONOMY-2")


def test_activation_proof_is_required(root):
    item = approval()
    item["payload"]["activation_receipt"]["checks"]["prompts"] = False
    with pytest.raises(ProposalError, match="PROOF_INCOMPLETE"):
        apply_approval(root, item)


def test_raw_document_requests_cannot_change_authority_or_fragments(root):
    for relative in ("CONTROL.json", a.FRAGMENTS_DOC, a.CAPACITY_DOC, "evolution/autonomy_capacity_reviews.json"):
        receipt = apply_requests(root, [{"request_id": "RAW-1", "document": relative,
                                        "merge": {"autonomy_mandate": {"status": "ACTIVE"}},
                                        "_autonomy_authority": "HUMAN"}])[0]
        assert not receipt["accepted"]


@pytest.mark.parametrize("patch", [{"charter": {"question": "Different"}}, {"charter": "replacement"},
                                  {"charter": None}, {"charter": ""},
                                  {"charter": {"budget": {"max_tests": 1000}}}, {"question_id": "QUESTION-OTHER"}])
def test_raw_document_cannot_modify_signed_scientific_contract(root, patch):
    original = {"roadmap_id": "RM-SIGNED", "question_id": "QUESTION-SIGNED", "charter": {
        "status": "CHARTERED", "question": "Frozen question", "scope": "public", "charter_hash": "sha256:" + "1" * 64,
        "budget": {"max_tests": 2, "max_days": 7}}}
    save(root, "roadmaps/RM-SIGNED.json", original)
    receipt = apply_requests(root, [{"request_id": "RAW-SIGNED", "document": "roadmaps/RM-SIGNED.json", "merge": patch}])[0]
    assert not receipt["accepted"]
    assert a.read(root, "roadmaps/RM-SIGNED.json") == original


def test_existing_contract_needs_new_version_identity(root):
    save(root, "contracts/scientific-v1.json", {"threshold": 0.05})
    request = {"request_id": "RAW-CONTRACT", "document": "contracts/scientific-v1.json", "merge": {"threshold": 0.9}}
    assert not apply_requests(root, [request])[0]["accepted"]
    assert a.read(root, "contracts/scientific-v1.json") == {"threshold": 0.05}
    assert apply_requests(root, [dict(request, document="contracts/scientific-v2.json")])[0]["accepted"]


@pytest.mark.parametrize("relative", ["/CONTROL.json", "evolution/./autonomy_prompt_fragments.json",
                                     "evolution//autonomy_capacity.json", "evolution/../CONTROL.json",
                                     "evolution/..\\CONTROL.json"])
def test_document_path_alias_cannot_bypass_protected_guard(root, relative):
    before = a.read(root, "CONTROL.json")
    receipt = apply_requests(root, [{"request_id": "RAW-ALIAS", "document": relative,
                                    "merge": {"autonomy_mandate": {"status": "ACTIVE"}}}])[0]
    assert not receipt["accepted"]
    assert a.read(root, "CONTROL.json") == before


@pytest.mark.parametrize("kind,identity", [("../evolution", "autonomy_capacity_reviews"),
    ("../evolution", "batteries"), ("test", "../../evolution/autonomy_capacity_reviews"),
    ("test", "..\\..\\evolution\\batteries"), ("test", "/CONTROL"),
    ("C:", "autonomy_capacity_reviews"), ("test", "C:\\Temp\\outside"), (".", "name")])
def test_service_entity_path_cannot_mutate_protected_documents(root, kind, identity):
    from runtime.nexo_agent_api.service import AgentService, TowerAgentIssue
    relative = "evolution/autonomy_capacity_reviews.json"
    original = {"schema": "NEXO_CAPACITY_REVIEW_REGISTRY_V1", "reviews": [], "entity_version": 1}
    save(root, relative, original)
    save(root, e.BATTERIES_DOC, {"batteries": [], "entity_version": 1})
    with pytest.raises(TowerAgentIssue) as rejected:
        AgentService(root).mutate(kind, identity, expected_version=1, writer_role="EXECUTOR",
            event_type="FORGED_CAPACITY", changes={"reviews": [{"decision": "PASS", "approved_by": "WRITER_GUARDIAN_POLICY"}]})
    assert rejected.value.code == "ENTITY_PATH_COMPONENT_INVALID"
    assert a.read(root, relative) == original
    assert a.read(root, e.BATTERIES_DOC)["batteries"] == []


def test_entity_path_keeps_legacy_colon_ids_but_json_identity_has_no_traversal(root):
    from runtime.nexo_agent_api.tower_paths import entity_path, json_file
    assert entity_path(root, "test", "TEST::A").parent == root / "entities/test"
    for identity in ("../CONTROL", "..\\CONTROL", "/CONTROL", ".", ".."):
        with pytest.raises(ValueError, match="ENTITY_PATH_COMPONENT_INVALID"):
            json_file(root / "events", identity)


def test_full_writer_requires_trusted_context(root):
    raw = json.dumps(build_live_tower_payload(root)).encode()
    item = dict(approval(), _inbox_id="gateway:human-fixture", _inbox_name="human-fixture")
    packed, report = apply_to_tower(raw, [item])
    assert not read_live_tower_bytes(packed or raw)["files"]["CONTROL.json"]["value"].get("autonomy_mandate")
    packed, report = apply_to_tower(raw, [item], verified_human_intents=frozenset({a.envelope_hash(item)}))
    control = read_live_tower_bytes(packed)["files"]["CONTROL.json"]["value"]
    assert control["autonomy_mandate"]["status"] == "ACTIVE", report


def charter_body(rid="RM-Q", qid="QUESTION-EXPLICIT"):
    return {"roadmap_id": rid, "question_id": qid, "question": "Does the public observable depend on selection?",
            "scope": "Public observational cosmology", "domain": "OBSERVATIONAL_COSMOLOGY", "data": "Public frozen input",
            "mandate_id": "AUTONOMY-1", "public_data_only": True, "visibility": "PUBLIC",
            "public_data_refs": ["https://example.org/public-data"], "budget": {"max_tests": 2, "max_days": 7}}


def test_question_identity_survives_wording_and_rejects_second_campaign(root):
    apply_approval(root, approval())
    body = charter_body()
    apply_requests(root, e.charter_requests({"created_at": STAMP}, body, root))
    charter = a.read(root, "roadmaps/RM-Q.json")
    assert charter["question_id"] == body["question_id"] and charter["status"] == "ACTIVE"
    assert e.charter_requests({}, dict(body, question="A new wording"), root) == []
    with pytest.raises(ProposalError, match="QUESTION_ALREADY_HAS_CAMPAIGN"):
        e.charter_requests({}, charter_body("RM-OTHER"), root)
    with pytest.raises(ProposalError, match="QUESTION_ID_IMMUTABLE"):
        e.charter_requests({}, dict(body, question_id="QUESTION-DIFFERENT"), root)


@pytest.mark.parametrize("change", [{"domain": "OLYMPUS"}, {"public_data_only": False}, {"public_data_refs": []},
                                    {"public_data_refs": ["https://user:secret@example.org/file"]}])
def test_prospective_charter_rejects_scope_expansion(root, change):
    apply_approval(root, approval())
    with pytest.raises(ProposalError, match="OUT_OF_SCOPE"):
        e.charter_requests({}, dict(charter_body(), **change), root)


def test_global_capacity_reservation_package_and_ambiguous_dispatch(root):
    apply_approval(root, approval())
    first, second = public_test(root), public_test(root, "TEST-B")
    apply_requests(root, battery(root))
    canonical = s.batteries(root)[0]
    assert canonical["parallelism"] == 1
    assert hashlib.sha256(canonical["package_json"].encode()).hexdigest() == canonical["package_sha256"]
    assert json.loads(canonical["package_json"]) == a.frozen_package(canonical)
    assert e.battery_requests({}, {"battery_id": "bat-one", "tests": [{"test_id": first["id"], "recipe": first["recipe"], "params": first["recipe_params"]}]}, root) == []
    with pytest.raises(ProposalError, match="GLOBAL_CAPACITY_FULL"):
        battery(root, second["id"], "bat-two")
    requests = e.battery_status_requests({"_writer_dispatch_token": s.WRITER_DISPATCH_TOKEN},
                                        {"battery_id": "bat-one", "status": "DISPATCH_PENDING"}, root, _result_request)
    apply_requests(root, requests)
    assert e.pending_batteries(root) == []  # unknown external response is never redispatched
    run = {"battery_id": "bat-one", "status": "DISPATCHED", "run_ref": "actions/runs/123"}
    apply_requests(root, e.battery_status_requests({"_inbox_source": "RUNNER_OBSERVATION"}, run, root, _result_request))
    assert s.batteries(root)[0]["run_ref"] == "actions/runs/123"
    with pytest.raises(ProposalError, match="EXTERNAL_RUN_CONFLICT"):
        e.battery_status_requests({"_inbox_source": "RUNNER_OBSERVATION"}, dict(run, run_ref="actions/runs/124"), root, _result_request)


def test_quota_expiration_missing_public_provenance_and_revocation(root):
    apply_approval(root, approval())
    test = public_test(root)
    assert a.admission(root, [test], 1, NOW + timedelta(hours=2)) == "AUTONOMY_FREE_QUOTA_UNVERIFIED"
    test["data_binding"]["inputs"][0].pop("public")
    assert a.admission(root, [test], 1, NOW) == "AUTONOMY_PUBLIC_PROVENANCE_REQUIRED"
    test = public_test(root)
    apply_requests(root, battery(root))
    apply_approval(root, approval(revision=1, action="REVOKE_AUTONOMY_MANDATE"))
    assert e.pending_batteries(root) == []
    assert a.admission(root, [test], 1, NOW) == "AUTONOMY_MANDATE_INACTIVE_OR_MIXED"


@pytest.mark.parametrize("url", ["https://example.org/frozen.csv?download=1", "https://example.org/frozen.csv#slice"])
def test_scoped_input_url_matches_machine_package_query_and_fragment_policy(root, url):
    apply_approval(root, approval())
    test = public_test(root)
    test["data_binding"]["inputs"] = [{"name": "sample", "kind": "public_url", "public": True, "sha256": "a" * 64, "url": url}]
    assert a.admission(root, [test], 1) == "AUTONOMY_PUBLIC_PROVENANCE_REQUIRED"
    test.pop("mandate_id")
    assert a.admission(root, [test], 1) is None  # preserve the existing legacy contract


def test_legacy_admission_remains_compatible(root):
    store_fixture_test(root, "TEST-LEGACY")
    assert battery(root, "TEST-LEGACY", "bat-legacy")


def test_mandate_cannot_bypass_scientific_guards_through_wrong_domain(root):
    apply_approval(root, approval())
    test = public_test(root)
    test["domain"] = "ENGINEERING"
    save(root, "entities/test/TEST-A.json", test)
    assert a.admission(root, [test], 1) == "AUTONOMY_DOMAIN_OUT_OF_SCOPE"
    receipt = apply_requests(root, [{"entity_kind": "test", "entity_name": "TEST-A", "expected_version": 1,
                                    "writer_role": "ADVISOR", "event_type": "FORGED_DOMAIN_MUTATION",
                                    "changes": {"question": "Change frozen criteria"}}])[0]
    assert not receipt["accepted"] and receipt["issue"]["code"] == "FROZEN_DEFINITION_IMMUTABLE"


def gene_fixture(root):
    value = {"role": "EXECUTOR", "version": 1, "text": "Confira os dados congelados e explique o próximo passo."}
    value["sha256"] = hashlib.sha256(value["text"].encode()).hexdigest()
    gene = {"id": "operator-instructions", "status": "CANARY", "evolution_kind": "operational_prompt_fragment",
            "mandate_id": "AUTONOMY-1", "proposed_by": "EXECUTOR", "canary": value,
            "evaluation_frozen_at": (NOW - timedelta(minutes=10)).isoformat(),
            "evaluation_plan": {"metric": "confirmed_per_test", "minimum_rounds_per_arm": 10,
                                "minimum_gain": 0.1, "higher_is_better": True, "units": []},
            "independent_evaluation_ref": "entities/evidence/GENE-REVIEW.json"}
    observations = []
    units = [{"test_id": f"TEST-GENE-{arm.upper()}-{number}", "arm": arm}
             for arm in ("canonical", "canary") for number in range(10)]
    gene["evaluation_plan"]["units"] = units
    gene["evaluation_plan_sha256"] = a.digest(gene["evaluation_plan"])
    attempts = []
    for arm in ("canonical", "canary"):
        for number in range(10):
            tid = f"TEST-GENE-{arm.upper()}-{number}"
            attempt_id, bid = "attempt-" + tid, "bat-gene-" + tid.lower()
            reviewed = store_fixture_test(root, tid, gene_id=gene["id"], gene_arm=arm)
            attack_id = "ATTACK-" + tid
            reviewed.update({"gene_plan_sha256": gene["evaluation_plan_sha256"],
                             "contests": [{"by": "REFEREE_1", "contest_test_id": attack_id, "at": STAMP}]})
            reviewed.update({"id": tid, "gene_id": gene["id"], "gene_arm": arm,
                                                    "gene_plan_sha256": gene["evaluation_plan_sha256"],
                                                    "executed_at": STAMP, "started_at": (NOW - timedelta(minutes=1)).isoformat(),
                                                    "verdict": "PROMOTED" if arm == "canary" else "REJECTED",
                                                    "status": "DONE", "state": "DONE", "review_state": "CONTESTED",
                                                    "battery_id": bid, "attempt_id": attempt_id, "run_ref": "actions/runs/123"})
            reviewed["prereg_hash"] = e.prereg_hash(tid, reviewed)
            save(root, f"entities/test/{tid}.json", reviewed)
            attack = store_fixture_test(root, attack_id, dataset_and_selection="Independent generated sample B",
                                        contests_test_id=tid, status="DONE", state="DONE", executed_at=STAMP,
                                        verdict="PROMOTED" if arm == "canary" else "REJECTED")
            declaration = {"axis": "data", "evidence_refs": ["entities/evidence/independent-fixture.json"],
                           "frozen_at": attack["frozen_at"], "on_pass": "CONFIRMED", "on_fail": "REFUTED"}
            attack.update(independence=declaration, independence_fingerprint=s.digest(declaration))
            save(root, f"entities/test/{attack_id}.json", attack)
            save(root, "entities/evidence/independent-fixture.json", {"id": "independent-fixture", "source": "synthetic_fixture"})
            attempts.append({"id": bid, "status": "DONE", "conclusion": "success", "run_ref": "actions/runs/123", "tests": [
                {"test_id": tid, "attempt_id": attempt_id, "gene_id": gene["id"], "gene_arm": arm,
                 "gene_plan_sha256": gene["evaluation_plan_sha256"]}]})
            observations.append({"test_id": tid, "arm": arm})
    report = {"schema": "NEXO_OPERATIONAL_GENE_EVALUATION_V1", "gene_id": gene["id"], "canary_sha256": a.digest(value),
              "plan_sha256": a.digest(gene["evaluation_plan"]), "reviewer_role": "REFEREE_1", "decision": "PASS",
              "regression_passed": True, "rollback_ref": "sha256:" + a.digest(gene.get("canonical")), "observations": observations}
    save(root, "evolution/genome.json", {"genes": [gene], "generation": 0})
    save(root, e.BATTERIES_DOC, {"batteries": attempts})
    save(root, gene["independent_evaluation_ref"], report)
    reviews = e.contest_chain_reconcile_requests(root)
    assert len(reviews) == 20
    receipts = apply_requests(root, reviews)
    assert all(receipt["accepted"] for receipt in receipts), [row for row in receipts if not row["accepted"]]
    return gene, report


def test_gene_promotion_requires_actual_independent_records_and_preserves_core(root):
    apply_approval(root, approval())
    gene, report = gene_fixture(root)
    receipt = apply_requests(root, [{"entity_kind": "test", "entity_name": "TEST-GENE-CANARY-0",
                                    "expected_version": 2, "writer_role": "ADVISOR", "event_type": "FAKE_REVIEW",
                                    "changes": {"reviews": [{"referee": "EXECUTOR"}]}}])[0]
    assert not receipt["accepted"] and receipt["issue"]["code"] == "CANONICAL_REVIEW_LEDGER_WRITER_ONLY"
    broken = copy.deepcopy(report)
    broken["reviewer_role"] = "EXECUTOR"
    save(root, gene["independent_evaluation_ref"], broken)
    assert a.canonization_requests(root) == []
    save(root, gene["independent_evaluation_ref"], report)
    requests = a.canonization_requests(root)
    assert len(requests) == 2
    assert all(receipt["accepted"] for receipt in apply_requests(root, requests))
    fragment = a.prompt_fragment(root, "EXECUTOR")
    assert fragment["text"] == gene["canary"]["text"]
    assert a.canonization_requests(root) == []
    assert a.mandate(root)["immutable_constraints"] == list(a.IMMUTABLE)
    apply_approval(root, approval(revision=1, action="REVOKE_AUTONOMY_MANDATE"))
    assert a.prompt_fragment(root, "EXECUTOR") is None


@pytest.mark.parametrize("tamper", ["rounds", "plan", "bytes", "unexecuted", "duplicate", "rollback", "review_author", "contest"])
def test_gene_eval_fails_closed_on_missing_or_tampered_evidence(root, tamper):
    apply_approval(root, approval())
    gene, report = gene_fixture(root)
    if tamper == "rounds":
        report["observations"].pop()
    elif tamper == "plan":
        report["plan_sha256"] = "0" * 64
    elif tamper == "bytes":
        gene["canary"]["text"] += " changed"
        save(root, "evolution/genome.json", {"genes": [gene]})
    elif tamper == "unexecuted":
        save(root, "entities/test/TEST-GENE-CANARY-0.json", {"id": "TEST-GENE-CANARY-0", "review_state": "REFUTED"})
    elif tamper == "duplicate":
        report["observations"][1] = report["observations"][0]
    elif tamper == "rollback":
        report["rollback_ref"] = "arbitrary-prose"
    elif tamper == "review_author":
        test = a.read(root, "entities/test/TEST-GENE-CANARY-0.json")
        test["reviews"][0]["referee"] = "EXECUTOR"
        save(root, "entities/test/TEST-GENE-CANARY-0.json", test)
    elif tamper == "contest":
        save(root, "entities/test/ATTACK-TEST-GENE-CANARY-0.json", {"id": "ATTACK-TEST-GENE-CANARY-0"})
    save(root, gene["independent_evaluation_ref"], report)
    assert a.canonization_requests(root) == []


def test_capacity_cannot_skip_stages_or_promote_without_run_evidence(root):
    apply_approval(root, approval())
    observation = {"parallelism": 4, "quota": {"status": "AVAILABLE_FREE", "additional_cost": 0,
                                               "standard_public_runners": True, "checked_at": STAMP}}
    assert a.capacity_requests(root, observation) == []
    assert a.capacity_requests(root, dict(observation, parallelism=2)) == []
    observation["parallelism"] = 1
    assert a.capacity_requests(root, observation)


def capacity_fixture(root, *, activate=True, width=1, prefix="CAP", run_base=100, at=STAMP, now=None):
    """Real reservation/runner/result/review converters over synthetic inputs."""
    from runtime.nexo_agent_api import capacity_guard as guard
    if activate:
        apply_approval(root, approval())
    parents, attacks = [], []
    save(root, "entities/evidence/capacity-input.json", {"source": "synthetic_fixture_only"})
    for index in range(width):
        suffix = "" if width == 1 else "-" + str(index)
        parent, attack = public_test(root, "TEST-" + prefix + "-PARENT" + suffix), public_test(root, "TEST-" + prefix + "-ATTACK" + suffix)
        declaration = {"axis": "data", "evidence_refs": ["entities/evidence/capacity-input.json"],
                       "frozen_at": attack["frozen_at"], "on_pass": "CONFIRMED", "on_fail": "REFUTED"}
        attack.update(contests_test_id=parent["id"], dataset_and_selection="Independent synthetic sample B",
                      independence=declaration, independence_fingerprint=s.digest(declaration))
        attack["prereg_hash"] = e.prereg_hash(attack["id"], attack)
        save(root, "entities/test/" + attack["id"] + ".json", attack)
        update = e._test_update(root, parent["id"], {"review_state": "CONTESTED", "contests": [
            {"by": "REFEREE_1", "contest_test_id": attack["id"], "at": at}]}, "CAPACITY-CONTEST-" + parent["id"], "RESULT_CONTESTED")
        assert apply_requests(root, [update])[0]["accepted"]
        parents.append(parent)
        attacks.append(attack)
    for number, tests in enumerate((parents, attacks), 1):
        bid, run = "bat-" + prefix.lower() + "-" + str(number), "actions/runs/" + str(run_base + number)
        requests = e.battery_requests({"source": "EXECUTOR", "created_at": at}, {"battery_id": bid,
            "tests": [{"test_id": test["id"], "recipe": test["recipe"], "params": test["recipe_params"]} for test in tests]}, root)
        assert all(row["accepted"] for row in apply_requests(root, requests))
        observer = {"_inbox_source": "RUNNER_OBSERVATION", "created_at": at}
        running = {"battery_id": bid, "status": "RUNNING", "run_ref": run, "started_tests": {test["id"]: at for test in tests}}
        assert all(row["accepted"] for row in apply_requests(root, e.battery_status_requests(observer, running, root, _result_request)))
        end = (a.timestamp(at) + timedelta(seconds=1)).isoformat() if width > 1 else at
        specs = next(value for value in s.batteries(root) if value["id"] == bid)["tests"]
        done = {"battery_id": bid, "status": "DONE", "run_ref": run, "completed_at": end,
                "conclusion": "success", "results": [{"test_id": spec["test_id"], "ok": True,
                    "attempt_id": spec["attempt_id"], "recipe_sha256": spec["recipe_sha256"], "executed_at": end,
                    "result": {"verdict": "PROMOTED", "decision": "PASS", "statistics": {"mean": 0.2}}} for spec in specs]}
        receipts = apply_requests(root, e.battery_status_requests(observer, done, root, _result_request))
        assert all(row["accepted"] for row in receipts), receipts
    receipts = apply_requests(root, e.contest_chain_reconcile_requests(root))
    assert receipts and all(row["accepted"] for row in receipts), receipts
    assert guard.facts(root, now)
    return guard


def test_capacity_policy_issues_protected_receipt_from_actual_reviewed_runs(root):
    guard = capacity_fixture(root)
    requests = guard.review_requests(root)
    assert len(requests) == 1 and a.guard_document(root, requests[0]) is None
    assert all(row["accepted"] for row in apply_requests(root, requests))
    review = a.read(root, guard.REGISTRY)["reviews"][0]
    assert review["approved_by"] == "WRITER_GUARDIAN_POLICY" and review["stage"] == 1
    assert guard.review_requests(root) == []
    observation = {"parallelism": 2, "quota": a.read(root, a.CAPACITY_DOC)["quota"],
                   "battery_refs": review["battery_refs"], "review_ref": guard.REGISTRY + "#" + review["id"]}
    assert all(row["accepted"] for row in apply_requests(root, a.capacity_requests(root, observation)))
    assert a.parallelism(root) == 2
    assert a.capacity_requests(root, dict(observation, parallelism=4)) == []  # old receipt cannot release the next stage


def test_writer_applies_capacity_policy_in_same_verified_canonical_round(root):
    guard = capacity_fixture(root)
    raw = json.dumps(build_live_tower_payload(root)).encode()
    packed, report = apply_to_tower(raw, [])
    files = read_live_tower_bytes(packed)["files"]
    assert files[a.CAPACITY_DOC]["value"]["parallelism"] == 2
    assert files[guard.REGISTRY]["value"]["reviews"][0]["approved_by"] == "WRITER_GUARDIAN_POLICY"
    assert report["autonomy_capacity"]["parallelism"] == 2


def test_capacity_two_to_four_requires_actual_two_way_overlap_and_fresh_stage_receipt(root):
    guard = capacity_fixture(root)
    assert all(row["accepted"] for row in apply_requests(root, guard.review_requests(root)))
    first = a.read(root, guard.REGISTRY)["reviews"][0]
    next_time = NOW + timedelta(minutes=1)
    observation = {"parallelism": 2, "quota": a.read(root, a.CAPACITY_DOC)["quota"],
                   "battery_refs": first["battery_refs"], "review_ref": guard.REGISTRY + "#" + first["id"]}
    assert all(row["accepted"] for row in apply_requests(root, a.capacity_requests(root, observation, next_time)))
    evaluated = next_time + timedelta(minutes=1)
    capacity_fixture(root, activate=False, width=2, prefix="CAP2", run_base=200,
                     at=(next_time + timedelta(seconds=1)).isoformat(), now=evaluated)
    assert all(row["accepted"] for row in apply_requests(root, guard.review_requests(root, evaluated)))
    second = a.read(root, guard.REGISTRY)["reviews"][-1]
    assert second["stage"] == 2 and second["next_parallelism"] == 4
    observation.update(parallelism=4, battery_refs=second["battery_refs"], review_ref=guard.REGISTRY + "#" + second["id"])
    assert all(row["accepted"] for row in apply_requests(root, a.capacity_requests(root, observation, evaluated)))
    assert a.parallelism(root) == 4
    assert guard.facts(root, evaluated) is None  # technical cap20 never becomes another automatic stage


@pytest.mark.parametrize("tamper", ["failure", "duplicate_run", "review", "quota", "pending", "metadata"])
def test_capacity_policy_fails_closed_on_unstable_or_incomplete_whole_sample(root, tamper):
    guard = capacity_fixture(root)
    if tamper == "quota":
        capacity = a.read(root, a.CAPACITY_DOC)
        capacity["quota"]["status"] = "UNVERIFIED"
        save(root, a.CAPACITY_DOC, capacity)
    elif tamper == "review":
        parent = a.read(root, "entities/test/TEST-CAP-PARENT.json")
        parent["reviews"] = []
        save(root, "entities/test/TEST-CAP-PARENT.json", parent)
    else:
        records = s.batteries(root)
        if tamper == "failure":
            records[-1]["failed"] = 1
        elif tamper == "duplicate_run":
            records[-1]["run_ref"] = records[0]["run_ref"]
        elif tamper == "pending":
            records.append(dict(records[-1], id="bat-pending", status="DISPATCH_PENDING"))
        elif tamper == "metadata":
            records[-1]["created_at"] = None
        save(root, e.BATTERIES_DOC, {"batteries": records})
    assert guard.review_requests(root) == [] and a.parallelism(root) == 1


def test_raw_guardian_label_cannot_create_authorized_capacity_review(root):
    guard = capacity_fixture(root)
    fake = dict(guard.facts(root), reviewer_role="GUARDIAO", writer_role="GUARDIAO", reviewed_at=STAMP)
    save(root, "entities/evidence/FAKE-CAPACITY.json", fake)
    quota = a.read(root, a.CAPACITY_DOC)["quota"]
    assert a.capacity_requests(root, {"parallelism": 2, "quota": quota, "review_ref": "entities/evidence/FAKE-CAPACITY.json",
                                      "battery_refs": fake["battery_refs"]}) == []
    request = {"request_id": "FORGED-CAPACITY", "writer_role": "EXECUTOR", "document": guard.REGISTRY,
               "merge": {"schema": guard.SCHEMA, "reviews": [fake]}, "_autonomy_authority": "WRITER_AUTHORITY"}
    assert not apply_requests(root, [request])[0]["accepted"]


def test_scoped_reservation_history_and_stage_metadata_cannot_be_rewritten(root):
    capacity_fixture(root)
    records = s.batteries(root)
    rewritten = copy.deepcopy(records)
    rewritten[0]["parallelism"] = 2
    for proposed in (rewritten, records[1:]):
        receipt = apply_requests(root, [{"request_id": "FORGED-STABILITY", "document": e.BATTERIES_DOC,
                                         "merge": {"batteries": proposed}}])[0]
        assert not receipt["accepted"]


def test_raw_reservation_cannot_drop_scoped_admission_metadata(root):
    apply_approval(root, approval())
    public_test(root)
    request = battery(root)[0]
    request.pop("_autonomy_authority")
    record = request["merge"]["batteries"][0]
    for key in ("mandate_id", "mandate_revision", "parallelism", "source_revision", "package_json", "package_sha256"):
        record.pop(key, None)
    assert not apply_requests(root, [request])[0]["accepted"]


def test_partial_runner_observation_cannot_start_unobserved_sibling_or_rewrite_started_at(root):
    from runtime.nexo_agent_api.service import AgentService, TowerAgentIssue
    guard = capacity_fixture(root)
    assert all(row["accepted"] for row in apply_requests(root, guard.review_requests(root)))
    review = a.read(root, guard.REGISTRY)["reviews"][0]
    observation = {"parallelism": 2, "quota": a.read(root, a.CAPACITY_DOC)["quota"],
                   "battery_refs": review["battery_refs"], "review_ref": guard.REGISTRY + "#" + review["id"]}
    assert all(row["accepted"] for row in apply_requests(root, a.capacity_requests(root, observation)))
    first, second = public_test(root, "TEST-OBS-A"), public_test(root, "TEST-OBS-B")
    requests = e.battery_requests({"source": "EXECUTOR", "created_at": STAMP}, {"battery_id": "bat-partial",
        "tests": [{"test_id": test["id"], "recipe": test["recipe"], "params": test["recipe_params"]} for test in (first, second)]}, root)
    assert all(row["accepted"] for row in apply_requests(root, requests))
    observer = {"_inbox_source": "RUNNER_OBSERVATION", "created_at": STAMP}
    base = {"battery_id": "bat-partial", "run_ref": "actions/runs/987"}
    for status in (dict(base, status="DISPATCHED"), dict(base, status="RUNNING", started_tests={first["id"]: STAMP})):
        assert all(row["accepted"] for row in apply_requests(root, e.battery_status_requests(observer, status, root, _result_request)))
    canonical = next(batch for batch in s.batteries(root) if batch["id"] == base["battery_id"])
    assert canonical["started_tests"] == {first["id"]: STAMP}
    service = AgentService(root)
    current = s.entity(root, second["id"])
    assert current["execution_phase"] == "DISPATCHED"
    with pytest.raises(TowerAgentIssue):
        service.mutate("test", second["id"], expected_version=current["entity_version"], writer_role="EXECUTOR", event_type="TEST_RUNNING",
            changes={"status": "RUNNING", "state": "RUNNING", "execution_phase": "RUNNING", "run_ref": base["run_ref"],
                     "execution_observation": "GITHUB_JOB_STEP", "started_at": STAMP}, _runner_observation_authority="FORGED")
    current = s.entity(root, first["id"])
    with pytest.raises(TowerAgentIssue):
        service.mutate("test", first["id"], expected_version=current["entity_version"], writer_role="EXECUTOR", event_type="EDIT_START",
            changes={"started_at": (NOW - timedelta(minutes=1)).isoformat()})
    with pytest.raises(ProposalError, match="START_COMMITMENT_CHANGED"):
        e.battery_status_requests(observer, dict(base, status="RUNNING", started_tests={first["id"]: "2026-09-30T10:00:00Z"}), root, _result_request)
    observed = dict(base, status="RUNNING", started_tests={second["id"]: STAMP})
    assert all(row["accepted"] for row in apply_requests(root, e.battery_status_requests(observer, observed, root, _result_request)))
    assert s.entity(root, second["id"])["execution_phase"] == "RUNNING"


def test_runner_start_metadata_remains_protected_after_terminal_result(root):
    capacity_fixture(root)
    current = s.entity(root, "TEST-CAP-PARENT")
    receipt = apply_requests(root, [{"entity_kind": "test", "entity_name": current["id"],
        "expected_version": current["entity_version"], "writer_role": "EXECUTOR", "event_type": "FORGED_OVERLAP",
        "changes": {"started_at": (NOW - timedelta(minutes=1)).isoformat()}}])[0]
    assert not receipt["accepted"] and receipt["issue"]["code"] == "RUNNER_OBSERVATION_METADATA_WRITER_ONLY"


def test_verified_retry_binds_a_fresh_start_to_new_attempt_and_keeps_old_receipt(root):
    apply_approval(root, approval())
    test = public_test(root)
    assert all(row["accepted"] for row in apply_requests(root, battery(root)))
    observer = {"_inbox_source": "RUNNER_OBSERVATION", "created_at": STAMP}
    running = {"battery_id": "bat-one", "status": "RUNNING", "run_ref": "actions/runs/987", "started_tests": {test["id"]: STAMP}}
    assert all(row["accepted"] for row in apply_requests(root, e.battery_status_requests(observer, running, root, _result_request)))
    failed = dict(running, status="DONE", completed_at=STAMP, conclusion="failure", results=[
        {"test_id": test["id"], "ok": False, "log_tail": "Temporary network timeout"}])
    receipts = apply_requests(root, e.battery_status_requests(observer, failed, root, _result_request))
    assert all(row["accepted"] for row in receipts), receipts
    prior = copy.deepcopy(s.batteries(root)[0])
    old_attempt = s.entity(root, test["id"])["attempt_id"]
    assert s.entity(root, test["id"])["status"] == "READY"
    receipts = apply_requests(root, battery(root, bid="bat-two"))
    assert all(row["accepted"] for row in receipts), receipts
    current = s.entity(root, test["id"])
    assert current["attempt_id"] != old_attempt
    assert all(current.get(field) is None for field in ("started_at", "execution_observation", "run_ref"))
    next_start = (NOW + timedelta(seconds=10)).isoformat()
    running.update(battery_id="bat-two", run_ref="actions/runs/988", started_tests={test["id"]: next_start})
    receipts = apply_requests(root, e.battery_status_requests(observer, running, root, _result_request))
    assert all(row["accepted"] for row in receipts), receipts
    assert s.entity(root, test["id"])["started_at"] == next_start
    assert next(value for value in s.batteries(root) if value["id"] == "bat-one") == prior


def test_operational_seed_cannot_bypass_review_or_change_immutable_core(root):
    apply_approval(root, approval())
    for kind in ("scheduler", "credentials", "authority", "frozen_science", "cost"):
        assert not e.mutation_requests({}, {"gene": "anything", "evolution_kind": kind, "mandate_id": "AUTONOMY-1", "value": "changed"}, root)
    assert not e.mutation_requests({}, {"gene": "anything", "seed": True, "evolution_kind": "attack_strategy", "mandate_id": "AUTONOMY-1", "value": "new tactic"}, root)


def test_legacy_gene_routes_cannot_reuse_scoped_plan_or_reactivate_revoked_gene(root):
    apply_approval(root, approval())
    gene = {"id": "attack-tactic", "status": "CANONICAL", "evolution_kind": "attack_strategy",
            "mandate_id": "AUTONOMY-1", "canonical": "Existing tactic", "evaluation_plan": {"units": ["OLD"]}}
    save(root, e.GENOME_DOC, {"genes": [gene]})
    for body in ({"gene": gene["id"], "value": "Unscoped change"},
                 {"gene": gene["id"], "value": "Wrong kind", "evolution_kind": "priority", "mandate_id": "AUTONOMY-1"}):
        assert not e.mutation_requests({"source": "EXECUTOR"}, body, root)
    assert not apply_requests(root, [{"document": e.GENOME_DOC, "merge": {"genes": None}}])[0]["accepted"]
    apply_approval(root, approval(revision=1, action="REVOKE_AUTONOMY_MANDATE"))
    assert not e.mutation_requests({"source": "EXECUTOR"}, {"gene": gene["id"], "value": "Unscoped change"}, root)
    assert not e.mutation_requests({"source": "EXECUTOR"}, {"gene": gene["id"], "value": "Scoped change",
                                   "evolution_kind": "attack_strategy", "mandate_id": "AUTONOMY-1"}, root)


@pytest.mark.parametrize("changes,code", [({"question": "Changed frozen question"}, "FROZEN_DEFINITION_IMMUTABLE"),
                                         ({"review_state": "CONFIRMED"}, "REVIEW_EVIDENCE_REQUIRED"),
                                         ({"domain": "UNRELATED", "question": "Changed"}, "AUTONOMY_SCOPE_IMMUTABLE")])
def test_observational_domain_preserves_frozen_and_review_gates(root, changes, code):
    test = store_fixture_test(root, "TEST-OBS", domain="OBSERVATIONAL_COSMOLOGY", mandate_id="AUTONOMY-1")
    receipt = apply_requests(root, [{"request_id": "REQ-OBS-FORGED", "entity_kind": "test", "entity_name": test["id"],
                                    "expected_version": 1, "writer_role": "ADVISOR", "event_type": "TEST_UPDATED",
                                    "changes": changes}])[0]
    assert not receipt["accepted"] and receipt["issue"]["code"] == code


def test_gene_plan_cannot_be_retrofitted_or_selectively_sampled(root):
    apply_approval(root, approval())
    gene, report = gene_fixture(root)
    gene["evaluation_frozen_at"] = (NOW + timedelta(minutes=1)).isoformat()
    save(root, "evolution/genome.json", {"genes": [gene]})
    assert not a.canonization_requests(root)
    gene["evaluation_frozen_at"] = (NOW - timedelta(minutes=10)).isoformat()
    report["observations"] = report["observations"][:-1]
    save(root, "evolution/genome.json", {"genes": [gene]})
    save(root, gene["independent_evaluation_ref"], report)
    assert not a.canonization_requests(root)


@pytest.mark.parametrize("failure", ["conflict", "transport", "dry", "success"])
def test_robot_never_exports_dispatch_before_verified_cas(root, tmp_path, monkeypatch, failure):
    from runtime.nexo_agent_api import gpt_writer
    from runtime.nexo_agent_api.drive_transport import TowerConflict, TowerTransportError
    test = store_fixture_test(root, "TEST-LEGACY")
    apply_requests(root, battery(root, test["id"], "bat-legacy"))
    raw = json.dumps(build_live_tower_payload(root)).encode()
    tower, inbox, github = Mock(), Mock(), Mock(seen=[])
    tower.download.return_value = (raw, "base")
    inbox.pending.return_value = []
    github.pending.return_value = []
    if failure == "conflict":
        tower.compare_and_swap.side_effect = TowerConflict("HEAD_MOVED")
    elif failure == "transport":
        tower.compare_and_swap.side_effect = TowerTransportError("UPLOAD", None, "RECONCILE_UNKNOWN_WRITE")
    else:
        tower.compare_and_swap.return_value = {"readback": True, "state_fingerprint": "committed"}
    staging = tmp_path / "dispatch"
    save(staging, "bat-stale.json", {"id": "bat-stale", "tests": []})
    monkeypatch.setenv("NEXO_BATTERY_DIR", str(staging))
    monkeypatch.setenv("NEXO_HOME", str(tmp_path / "isolated-home"))
    monkeypatch.delenv("NEXO_GATEWAY_ITEMS", raising=False)
    monkeypatch.delenv("NEXO_VERIFIED_HUMAN_INTENTS", raising=False)
    if failure == "dry":
        monkeypatch.setenv("NEXO_ROBOT_DRY", "1")
    monkeypatch.setattr("runtime.nexo_agent_api.drive_transport.DriveTower", lambda **kwargs: tower)
    monkeypatch.setattr("runtime.nexo_agent_api.drive_transport.DriveInbox", lambda **kwargs: inbox)
    monkeypatch.setattr(gpt_writer, "_GitHubInbox", lambda token: github)
    monkeypatch.setattr(gpt_writer, "_family_items", lambda raw, kind: [])
    monkeypatch.setattr(gpt_writer, "_stop_closures", lambda raw: [])
    result = gpt_writer.main(["robot"])
    if failure == "success":
        assert result == 0
        exported = json.loads((staging / "bat-legacy.json").read_text())
        assert exported["status"] == "DISPATCH_PENDING"
        tower.compare_and_swap.assert_called_once()
    else:
        assert result == (3 if failure == "conflict" else 0)
        assert list(staging.glob("*.json")) == []
