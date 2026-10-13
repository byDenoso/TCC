"""Exercise real private bootstrap/queue/handoff paths; no scheduler or network."""
import json

import pytest

from runtime.nexo_agent_api import autonomy as a
from runtime.nexo_agent_api.service import AgentService
from runtime.nexo_agent_api.views import materialize_role_views
from tests.test_autonomy_prepared import root, approval, apply_approval, STAMP
from tests.test_scientific_integrity import save, store_fixture_test


def prepare_roles(root):
    save(root, "snapshot/latest.json", {"event_cursor": "synthetic-role-interface"})
    for role in ("ENGINEER", "ADVISOR", "GUARDIAO"):
        save(root, "entities/work/WORK-" + role + ".json", {
            "id": "WORK-" + role, "entity_version": 1, "kind": "ENGINEERING_FIX" if role != "GUARDIAO" else "GOVERNANCE",
            "status": "READY", "owner_role": role, "question": "Conferir a pendência declarada.",
            "director_relevant": role == "GUARDIAO"})
    store_fixture_test(root, "TEST-PENDING-REVIEW", status="DONE", state="DONE", verdict="PROMOTED",
                       executed_at=STAMP, review_state="PENDING_REVIEW")
    store_fixture_test(root, "TEST-CLOSED-REVIEW", status="DONE", state="DONE", verdict="PROMOTED",
                       executed_at=STAMP, review_state="CONFIRMED")
    store_fixture_test(root, "ATTACK-EXECUTED", status="DONE", state="DONE", verdict="PROMOTED",
                       executed_at=STAMP, contests_test_id="TEST-PENDING-REVIEW")
    save(root, "manifests/capabilities.json", {"capabilities": {"existing-engineering": {"roles": ["ADVISOR"]}}})


def test_five_roles_use_existing_real_bootstrap_paths(root):
    prepare_roles(root)
    service = AgentService(root)
    before = a.read(root, "CONTROL.json")
    for role in ("LEARNER", "EXECUTOR", "ENGINEER", "REFEREE_1", "GUARDIAO"):
        value = service.bootstrap(role)
        assert value["role"] == role and value["autonomy"]["status"] == "PREPARED_INACTIVE"
        assert isinstance(value["queue"], list) and isinstance(value["inbox"], list)
    assert {card["id"] for card in service.queue_for("ENGINEER")} == {"WORK-ENGINEER", "WORK-ADVISOR"}
    assert {card["id"] for card in service.queue_for("REFEREE_1")} == {"TEST-PENDING-REVIEW"}
    assert {card["id"] for card in service.queue_for("GUARDIAO")} == {"WORK-GUARDIAO"}
    assert service.capabilities_for("ENGINEER") == service.capabilities_for("ADVISOR")
    assert a.read(root, "CONTROL.json") == before


@pytest.mark.parametrize("recipient", ["ENGINEER", "REFEREE_1", "GUARDIAO"])
def test_new_role_handoff_has_real_event_receipts(root, recipient):
    prepare_roles(root)
    service = AgentService(root)
    receipt = service.emit_handoff(request_id="role-interface-" + recipient, from_role="LEARNER", to_role=recipient,
                                   handoff_type="REVIEW", entity_ref="WORK-GUARDIAO", thread_id="synthetic-topic",
                                   summary_plain="A preparação terminou.", why_it_matters="A pendência precisa de conferência.",
                                   next_action="Confira a evidência e registre o próximo passo.")
    assert service.inbox_for(recipient)[0]["handoff_id"] == receipt["handoff_id"]
    acknowledged = service.transition_handoff(receipt["handoff_id"], state="ACK", writer_role=recipient)
    assert acknowledged["state"] == "ACK" and acknowledged["to_role"] == recipient


def test_engineer_alias_keeps_original_offer_identity(root):
    prepare_roles(root)
    service = AgentService(root)
    receipt = service.emit_handoff(request_id="legacy-engineer-offer", from_role="LEARNER", to_role="ADVISOR",
                                   handoff_type="REVIEW", entity_ref="WORK-ADVISOR", thread_id="synthetic-topic",
                                   summary_plain="A infraestrutura aguarda conferência.", why_it_matters="A preparação depende dessa etapa.",
                                   next_action="Confira o material preparado.")
    assert service.inbox_for("ENGINEER")[0]["handoff_id"] == receipt["handoff_id"]
    acknowledged = service.transition_handoff(receipt["handoff_id"], state="ACK", writer_role="ENGINEER")
    assert acknowledged["to_role"] == "ADVISOR" and acknowledged["request_id"] == "legacy-engineer-offer"


def test_new_materialized_views_are_scoped_to_mandate_and_keep_review_queue(root):
    prepare_roles(root)
    assert materialize_role_views(root)["roles"] == 5
    assert not (root / "bootstrap/engineer.json").exists()
    apply_approval(root, approval())
    assert materialize_role_views(root)["roles"] == 8
    value = a.read(root, "bootstrap/referee_1.json")
    assert value["queue"][0]["id"] == "TEST-PENDING-REVIEW"
    apply_approval(root, approval(revision=1, action="REVOKE_AUTONOMY_MANDATE"))
    materialize_role_views(root)
    assert a.read(root, "bootstrap/engineer.json")["autonomy"]["status"] == "REVOKED"
