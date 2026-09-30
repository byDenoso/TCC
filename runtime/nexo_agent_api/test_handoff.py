from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from . import AgentService, TowerAgentIssue, materialize_role_views
from runtime.nexo_agent_api.tower_paths import entity_path


class HandoffProtocolTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        for rel in ("entities/work", "manifests", "snapshot"):
            (self.root / rel).mkdir(parents=True)
        (self.root / "CONTROL.json").write_text(json.dumps({"mode": "ACTIVE", "schema_version": "0.6"}))
        (self.root / "snapshot/latest.json").write_text(json.dumps({"event_cursor": None}))
        (self.root / "manifests/capabilities.json").write_text(json.dumps({"capabilities": {}}))
        (self.root / "manifests/artifacts.json").write_text(json.dumps({"artifacts": {}}))

    def tearDown(self):
        self.tmp.cleanup()

    def emit(self, service, **kwargs):
        kwargs.setdefault("request_id", f"REQ-TEST-{kwargs.get('handoff_type')}-{kwargs.get('entity_ref')}")
        kwargs.setdefault("summary_plain", "Há uma atualização operacional pronta para o próximo papel.")
        kwargs.setdefault("why_it_matters", "A próxima etapa depende desta passagem de contexto.")
        return service.emit_handoff(**kwargs)

    def test_director_handoff_routes_pending_ack_done(self):
        service = AgentService(self.root)
        created = self.emit(service, 
            from_role="DIRECTOR",
            to_role="EXECUTOR",
            handoff_type="WORK_READY",
            entity_ref="WORK::GZ01-T02",
            thread_id="THR::SCIENCE::GZ-01",
            next_action="execute",
        )
        self.assertEqual(created["state"], "PENDING")
        self.assertEqual(service.inbox_for("ADVISOR"), [])
        self.assertEqual(service.inbox_for("EXECUTOR")[0]["handoff_id"], created["handoff_id"])

        service.transition_handoff(created["handoff_id"], state="ACK", writer_role="EXECUTOR")
        self.assertEqual(service.inbox_for("EXECUTOR")[0]["state"], "ACK")

        service.transition_handoff(created["handoff_id"], state="DONE", writer_role="EXECUTOR")
        self.assertEqual(service.inbox_for("EXECUTOR"), [])
        with self.assertRaises(TowerAgentIssue):
            service.transition_handoff(created["handoff_id"], state="ACK", writer_role="EXECUTOR")

    def test_request_id_retries_are_idempotent_and_preserve_source_citations(self):
        service = AgentService(self.root)
        payload = {
            "request_id": "REQ-HO-RESEARCH-001",
            "from_role": "ADVISOR",
            "to_role": "EXECUTOR",
            "handoff_type": "RESEARCH_READY",
            "entity_ref": "WORK::DARK-ENERGY",
            "thread_id": "THR::SCIENCE::DARK-ENERGY",
            "summary_plain": "Uma fonte primária nova restringe o próximo teste discriminante.",
            "why_it_matters": "A evidência muda qual comparação observacional deve ser priorizada.",
            "next_action": "Executar o teste discriminante já congelado com a nova fonte pública.",
            "objective_ref": "OBJ::DARK-ENERGY-NATURE",
            "confidence_plain": "Confiança moderada; a fonte sustenta o dado, não o veredito científico.",
            "evidence_refs": [{"ref": "TEST::DE-01", "kind": "TEST", "relation": "MOTIVA"}],
            "source_links": [{
                "label": "Primary release",
                "url": "https://example.org/primary",
                "access_date": "2026-09-27",
                "publisher": "Example Survey",
                "authors": ["A. Author", "B. Author"],
                "date": "2026-09-26",
                "supports": "Mede a quantidade observacional usada pelo teste.",
                "uncertainty": "Não estabelece causalidade por si só.",
                "next_test_impact": "Prioriza a comparação já pré-registrada.",
            }],
            "correlation_id": "CORR-DE-01",
        }
        first = service.emit_handoff(**payload)
        replay = service.emit_handoff(**payload)

        self.assertEqual(replay["handoff_id"], first["handoff_id"])
        self.assertEqual(replay["event_id"], first["event_id"])
        self.assertEqual(replay["source_links"][0]["access_date"], "2026-09-27")
        self.assertEqual(len(list((self.root / "events").rglob("*.json"))), 1)

        changed = dict(payload)
        changed["next_action"] = "Fazer outra coisa."
        with self.assertRaises(TowerAgentIssue) as conflict:
            service.emit_handoff(**changed)
        self.assertEqual(conflict.exception.code, "HANDOFF_REQUEST_ID_CONFLICT")

    def test_only_recipient_transitions_and_citations_survive_terminal_events(self):
        service = AgentService(self.root)
        created = service.emit_handoff(
            request_id="REQ-HO-CITATION-001",
            from_role="EXECUTOR",
            to_role="LEARNER",
            handoff_type="RESULT_READY",
            entity_ref="WORK::SCIENCE-01",
            thread_id="THR::SCIENCE::01",
            summary_plain="O teste terminou e o resultado canônico está disponível.",
            why_it_matters="O Learner pode transformar o resultado persistido em aprendizagem sem reexecutar o teste.",
            next_action="Ler o resultado canônico e registrar a lição aplicável.",
            evidence_refs=[{"ref": "TEST::SCIENCE-01", "kind": "TEST"}],
            source_links=[{
                "label": "Official data release",
                "url": "https://example.org/data",
                "access_date": "2026-09-27",
                "supports": "Fonte primária do dado usado no teste.",
                "uncertainty": "A fonte não substitui a análise do TEST.",
                "next_test_impact": "Nenhum critério congelado é alterado.",
            }],
        )
        with self.assertRaises(TowerAgentIssue):
            service.transition_handoff(created["handoff_id"], state="ACK", writer_role="ADVISOR")

        ack = service.transition_handoff(created["handoff_id"], state="ACK", writer_role="LEARNER")
        done = service.transition_handoff(created["handoff_id"], state="DONE", writer_role="LEARNER")
        self.assertEqual(ack["source_links"], created["source_links"])
        self.assertEqual(done["evidence_refs"], created["evidence_refs"])
        self.assertEqual(service.inbox_for("LEARNER"), [])

    def test_bootstrap_projects_only_five_actionable_handoffs(self):
        service = AgentService(self.root)
        for i in range(6):
            self.emit(service, 
                from_role="ADVISOR",
                to_role="EXECUTOR",
                handoff_type="WORK_READY",
                entity_ref=f"W{i}",
                thread_id="THR-1",
                next_action="execute",
            )
        bootstrap = service.bootstrap("EXECUTOR")
        self.assertEqual(bootstrap["inbox_count"], 5)
        self.assertEqual(bootstrap["inbox_limit"], 5)
        self.assertEqual(len(bootstrap["inbox"]), 5)

        materialize_role_views(self.root)
        persisted = json.loads((self.root / "bootstrap/executor.json").read_text())
        self.assertEqual(persisted["inbox_count"], 5)
        self.assertEqual(persisted["inbox_limit"], 5)

    def test_handoff_embeds_canonical_work_envelope_and_preserves_it_on_ack(self):
        work = {
            "id": "WORK::GZ01-B03",
            "entity_version": 7,
            "kind": "ACTION",
            "status": "READY",
            "owner_role": "EXECUTOR",
            "thread_id": "THR::SCIENCE::GZ-01",
            "question": "Run the next bounded discriminant",
            "next_action": "execute",
            "task_id": "gz01_multprobe_consistency",
            "repository": "byDenoso/TCC",
            "source_revision": "abc123",
            "required_outputs": ["benchmark_result.json"],
        }
        (entity_path(self.root, "work", "WORK::GZ01-B03")).write_text(json.dumps(work))
        service = AgentService(self.root)

        created = self.emit(service, 
            from_role="ADVISOR",
            to_role="EXECUTOR",
            handoff_type="WORK_READY",
            entity_ref=work["id"],
            thread_id=work["thread_id"],
            next_action=work["next_action"],
        )

        self.assertEqual(created["entity_version"], 7)
        self.assertEqual(created["entity_path"], "entities/work/WORK::GZ01-B03.json")
        self.assertEqual(created["work_envelope"]["task_id"], "gz01_multprobe_consistency")
        self.assertFalse(created["hydration_required"])

        ack = service.transition_handoff(created["handoff_id"], state="ACK", writer_role="EXECUTOR")
        self.assertEqual(ack["entity_version"], 7)
        self.assertEqual(ack["work_envelope"]["source_revision"], "abc123")

    def test_inbox_suppresses_stale_handoff_after_work_moved_to_next_owner(self):
        work_v1 = {
            "id": "WORK::GZ01-B03",
            "entity_version": 1,
            "kind": "ACTION",
            "status": "READY",
            "owner_role": "ADVISOR",
            "thread_id": "THR::SCIENCE::GZ-01",
            "next_action": "freeze contract",
        }
        path = entity_path(self.root, "work", "WORK::GZ01-B03")
        path.write_text(json.dumps(work_v1))
        service = AgentService(self.root)
        created = self.emit(service, 
            from_role="DIRECTOR",
            to_role="ADVISOR",
            handoff_type="CAMPAIGN_READY_FOR_BINDING",
            entity_ref=work_v1["id"],
            thread_id=work_v1["thread_id"],
            next_action=work_v1["next_action"],
        )
        self.assertEqual(service.inbox_for("ADVISOR")[0]["handoff_id"], created["handoff_id"])

        work_v4 = dict(work_v1)
        work_v4.update({
            "entity_version": 4,
            "owner_role": "EXECUTOR",
            "advisor_state": "HANDED_OFF",
            "next_action": "execute frozen test",
        })
        path.write_text(json.dumps(work_v4))

        self.assertEqual(service.inbox_for("ADVISOR"), [])

    def test_inbox_suppresses_terminal_cold_work_handoff_not_in_active_index(self):
        work_v1 = {
            "id": "WORK::GZ01-B02",
            "entity_version": 1,
            "kind": "ACTION",
            "status": "VERIFIED",
            "owner_role": "LEARNER",
            "thread_id": "THR::SCIENCE::GZ-01",
            "next_action": "learn",
        }
        path = entity_path(self.root, "work", "WORK::GZ01-B02")
        path.write_text(json.dumps(work_v1))
        service = AgentService(self.root)
        created = self.emit(service, 
            from_role="DIRECTOR",
            to_role="LEARNER",
            handoff_type="WORK_VERIFIED",
            entity_ref=work_v1["id"],
            thread_id=work_v1["thread_id"],
            next_action=work_v1["next_action"],
        )
        self.assertEqual(service.inbox_for("LEARNER")[0]["handoff_id"], created["handoff_id"])

        (self.root / "indexes").mkdir(parents=True)
        (self.root / "indexes/active-work.json").write_text(json.dumps({"work": []}))
        work_v5 = dict(work_v1)
        work_v5.update({
            "entity_version": 5,
            "status": "DONE",
            "owner_role": "ADVISOR",
            "learning_state": "DONE",
        })
        path.write_text(json.dumps(work_v5))

        self.assertEqual(service.inbox_for("LEARNER"), [])


class RecoveryOwnershipTests(unittest.TestCase):
    def setUp(self):
        HandoffProtocolTests.setUp(self)
        self.service = AgentService(self.root)
        self.work = {"id": "WORK::RECOVERY", "entity_version": 1, "kind": "DEPENDENCY_RECOVERY",
                     "status": "BLOCKED", "owner_role": "ADVISOR", "test_id": "TEST::RECOVERY",
                     "recovery": {"policy": "EXECUTION_RECOVERY_V1", "fingerprint": "frozen-inputs",
                                  "target_role": "EXECUTOR", "ownership_state": "ASSIGNED_UNACCEPTED",
                                  "reasons": ["RECIPE_BINDING_MISSING"], "validation": {"eligible": False}}}
        self.work_path = entity_path(self.root, "work", self.work["id"])
        self.work_path.write_text(json.dumps(self.work))
        self.envelope = {"request_id": "REQ-RECOVERY-1", "from_role": "ADVISOR", "to_role": "EXECUTOR",
                         "handoff_type": "BLOCKER_RECOVERY", "entity_ref": self.work["id"], "thread_id": "THR-RECOVERY",
                         "summary_plain": "O dado público necessário ainda precisa ser vinculado.",
                         "why_it_matters": "A recuperação permite executar o desenho já congelado.",
                         "next_action": "Validar a recuperação sem alterar a definição científica."}

    def tearDown(self):
        self.tmp.cleanup()

    def create(self):
        return self.service.emit_handoff(**self.envelope)

    def current_work(self):
        return json.loads(self.work_path.read_text())

    def change_work(self, **changes):
        work = self.current_work()
        self.service.mutate("work", work["id"], expected_version=work["entity_version"], changes=changes,
                            writer_role="EXECUTOR", event_type="RECOVERY_TEST_CHANGE")

    def complete_work(self):
        self.change_work(status="DONE")

    def prepare_ready_test(self, status="READY"):
        from .evolution import prereg_hash
        from .scientific_integrity import FROZEN

        recipes = self.root / "recipes"
        (recipes / "smoke").mkdir(parents=True)
        (recipes / "recovery_test.py").write_text("value = 1\n")
        (recipes / "smoke/recovery_test.json").write_text("{}")
        test = {key: "frozen " + key for key in FROZEN}
        test.update(id=self.work["test_id"], entity_version=3, status=status, recipe="recovery_test", recipe_params={},
                    frozen_at="2026-09-29T00:00:00Z", data_binding={"status": "BOUND", "inputs": [
                        {"name": "data", "kind": "generated", "generator": "fixture", "seed": 1, "sha256": "a" * 64}]})
        test["prereg_hash"] = prereg_hash(test["id"], test)
        path = entity_path(self.root, "test", test["id"])
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps(test))
        self.addCleanup(patch.stopall)
        patch.dict("os.environ", {"NEXO_RECIPE_ROOT": str(recipes)}).start()
        return path

    def test_create_keeps_owner_and_only_owner_can_offer(self):
        created = self.create()
        self.assertEqual(self.current_work(), self.work)
        self.assertEqual(created["recovery_fingerprint"], "frozen-inputs")
        self.envelope.update(request_id="REQ-NONOWNER", from_role="LEARNER")
        with self.assertRaises(TowerAgentIssue) as exc:
            self.create()
        self.assertEqual(exc.exception.code, "HANDOFF_RECOVERY_SENDER_NOT_OWNER")

    def test_creation_requires_current_recovery_contract_and_target(self):
        self.envelope["to_role"] = "LEARNER"
        with self.assertRaises(TowerAgentIssue) as exc:
            self.create()
        self.assertEqual(exc.exception.code, "HANDOFF_RECOVERY_TARGET_MISMATCH")
        self.work_path.unlink()
        with self.assertRaises(TowerAgentIssue) as exc:
            self.create()
        self.assertEqual(exc.exception.code, "HANDOFF_RECOVERY_WORK_REQUIRED")

    def test_ack_changes_owner_once_with_canonical_acceptance(self):
        created = self.create()
        ack = self.service.transition_handoff(created["handoff_id"], state="ACK", writer_role="EXECUTOR")
        work = self.current_work()
        self.assertEqual(work["owner_role"], "EXECUTOR")
        self.assertEqual(work["entity_version"], 2)
        self.assertEqual(work["recovery"]["ownership_state"], "ACCEPTED")
        self.assertEqual(work["recovery"]["acceptance_source"], ack["acceptance_source"])
        self.assertEqual(ack["acceptance_source"]["source_entity_version"], 1)
        self.assertEqual(ack["acceptance_source"]["handoff_id"], created["handoff_id"])
        self.assertEqual(ack["work_envelope"], work)
        replay = self.service.transition_handoff(created["handoff_id"], state="ACK", writer_role="EXECUTOR")
        self.assertEqual(replay["event_id"], ack["event_id"])
        self.assertEqual(self.current_work()["entity_version"], 2)
        self.assertEqual(self.create()["event_id"], ack["event_id"])

    def test_ack_requires_recipient_but_accepts_refreshed_diagnostics(self):
        created = self.create()
        with self.assertRaises(TowerAgentIssue) as exc:
            self.service.transition_handoff(created["handoff_id"], state="ACK", writer_role="LEARNER")
        self.assertEqual(exc.exception.code, "HANDOFF_WRITER_MISMATCH")
        self.change_work(recovery={**self.work["recovery"], "validation": {"eligible": False, "checked_at": "later"}})
        self.assertEqual(self.service.inbox_for("EXECUTOR")[0]["state"], "PENDING")
        ack = self.service.transition_handoff(created["handoff_id"], state="ACK", writer_role="EXECUTOR")
        self.assertEqual(self.current_work()["owner_role"], "EXECUTOR")
        self.assertEqual(ack["acceptance_source"]["source_entity_version"], 2)
        self.assertEqual(self.current_work()["recovery"]["validation"]["checked_at"], "later")

    def test_ack_uses_existing_entity_compare_and_swap(self):
        created = self.create()
        with patch.object(self.service, "mutate", side_effect=TowerAgentIssue("WRITE_CONFLICT_RETRY_REQUIRED", "race")) as mutate:
            with self.assertRaises(TowerAgentIssue):
                self.service.transition_handoff(created["handoff_id"], state="ACK", writer_role="EXECUTOR")
        self.assertEqual(mutate.call_args.kwargs["expected_version"], 1)
        self.assertEqual(self.current_work(), self.work)
        self.assertEqual(self.service.inbox_for("EXECUTOR")[0]["state"], "PENDING")

    def test_actual_concurrent_change_is_rejected_by_entity_cas(self):
        created = self.create()
        mutate = self.service.mutate

        def concurrent_change(*args, **kwargs):
            mutate("work", self.work["id"], expected_version=1, changes={"owner_role": "LEARNER"},
                   writer_role="ADVISOR", event_type="CONCURRENT_TRANSFER")
            return mutate(*args, **kwargs)

        with patch.object(self.service, "mutate", side_effect=concurrent_change):
            with self.assertRaises(TowerAgentIssue) as exc:
                self.service.transition_handoff(created["handoff_id"], state="ACK", writer_role="EXECUTOR")
        self.assertEqual(exc.exception.code, "WRITE_CONFLICT_RETRY_REQUIRED")
        self.assertEqual(self.current_work()["owner_role"], "LEARNER")
        self.assertEqual(self.current_work()["recovery"]["ownership_state"], "ASSIGNED_UNACCEPTED")

    def test_ack_retry_recovers_event_failure_without_second_owner_mutation(self):
        from . import handoff

        created = self.create()
        with patch.object(handoff, "_write_event", side_effect=OSError("event write failed")):
            with self.assertRaises(OSError):
                self.service.transition_handoff(created["handoff_id"], state="ACK", writer_role="EXECUTOR")
        self.assertEqual(self.current_work()["entity_version"], 2)
        recovered = self.service.transition_handoff(created["handoff_id"], state="ACK", writer_role="EXECUTOR")
        self.assertEqual(recovered["state"], "ACK")
        self.assertEqual(self.current_work()["entity_version"], 2)

    def test_done_requires_ack_terminal_work_and_live_evidence(self):
        created = self.create()
        with self.assertRaises(TowerAgentIssue) as exc:
            self.service.transition_handoff(created["handoff_id"], state="DONE", writer_role="EXECUTOR")
        self.assertEqual(exc.exception.code, "HANDOFF_RECOVERY_ACK_REQUIRED")
        self.service.transition_handoff(created["handoff_id"], state="ACK", writer_role="EXECUTOR")
        with self.assertRaises(TowerAgentIssue) as exc:
            self.service.transition_handoff(created["handoff_id"], state="DONE", writer_role="EXECUTOR")
        self.assertEqual(exc.exception.code, "HANDOFF_RECOVERY_WORK_NOT_COMPLETE")
        self.complete_work()
        # A bare terminal label and cached validation never constitute evidence.
        work = self.current_work()
        self.change_work(recovery={**work["recovery"], "validation": {"eligible": True}})
        with self.assertRaises(TowerAgentIssue) as exc:
            self.service.transition_handoff(created["handoff_id"], state="DONE", writer_role="EXECUTOR")
        self.assertEqual(exc.exception.code, "HANDOFF_RECOVERY_EVIDENCE_REQUIRED")
        self.assertEqual(self.service.inbox_for("EXECUTOR")[0]["state"], "ACK")
        self.prepare_ready_test()
        done = self.service.transition_handoff(created["handoff_id"], state="DONE", writer_role="EXECUTOR")
        self.assertTrue(done["completion_evidence"]["validation"]["eligible"])
        self.assertEqual(done["completion_evidence"]["test_version"], 3)
        self.assertEqual(self.service.inbox_for("EXECUTOR"), [])

    def test_done_ignores_reservation_but_never_frozen_science_validation(self):
        created = self.create()
        self.service.transition_handoff(created["handoff_id"], state="ACK", writer_role="EXECUTOR")
        self.complete_work()
        path = self.prepare_ready_test(status="QUEUED")
        original = path.read_bytes()
        test = json.loads(original)
        test["question"] = "changed after freezing"
        path.write_text(json.dumps(test))
        with self.assertRaises(TowerAgentIssue) as exc:
            self.service.transition_handoff(created["handoff_id"], state="DONE", writer_role="EXECUTOR")
        self.assertIn("FROZEN_DESIGN_CHANGED", exc.exception.details["validation"]["reasons"])
        path.write_bytes(original)
        self.service.transition_handoff(created["handoff_id"], state="DONE", writer_role="EXECUTOR")
        self.assertEqual(path.read_bytes(), original)

    def test_failed_preserves_owner_before_and_after_acceptance(self):
        created = self.create()
        failed = self.service.transition_handoff(created["handoff_id"], state="FAILED", writer_role="EXECUTOR")
        self.assertFalse(failed["route_failure"]["accepted"])
        self.assertEqual(self.current_work(), self.work)
        self.envelope["request_id"] = "REQ-RECOVERY-RETRY"
        created = self.create()
        self.service.transition_handoff(created["handoff_id"], state="ACK", writer_role="EXECUTOR")
        before = self.current_work()
        failed = self.service.transition_handoff(created["handoff_id"], state="FAILED", writer_role="EXECUTOR")
        self.assertTrue(failed["route_failure"]["accepted"])
        self.assertEqual(failed["route_failure"]["owner_role"], "EXECUTOR")
        self.assertEqual(self.current_work(), before)

    def test_changed_owner_or_recovery_contract_cannot_be_masked_by_transition(self):
        created = self.create()
        self.service.transition_handoff(created["handoff_id"], state="ACK", writer_role="EXECUTOR")
        self.change_work(owner_role="LEARNER")
        for state in ("ACK", "DONE", "FAILED"):
            with self.subTest(state=state), self.assertRaises(TowerAgentIssue) as exc:
                self.service.transition_handoff(created["handoff_id"], state=state, writer_role="EXECUTOR")
            self.assertEqual(exc.exception.code, "HANDOFF_RECOVERY_OWNER_CHANGED")
        self.change_work(owner_role="EXECUTOR", recovery={**self.current_work()["recovery"], "fingerprint": "new-scope"})
        with self.assertRaises(TowerAgentIssue) as exc:
            self.service.transition_handoff(created["handoff_id"], state="FAILED", writer_role="EXECUTOR")
        self.assertEqual(exc.exception.code, "HANDOFF_RECOVERY_CONTRACT_CHANGED")

    def test_pending_route_rejects_changed_target_test_even_if_fingerprint_was_not_updated(self):
        created = self.create()
        self.change_work(test_id="TEST::OTHER")
        with self.assertRaises(TowerAgentIssue) as exc:
            self.service.transition_handoff(created["handoff_id"], state="ACK", writer_role="EXECUTOR")
        self.assertEqual(exc.exception.code, "HANDOFF_RECOVERY_CONTRACT_CHANGED")
        self.assertEqual(self.current_work()["owner_role"], "ADVISOR")


if __name__ == "__main__":
    unittest.main()
