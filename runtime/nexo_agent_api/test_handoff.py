from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

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


if __name__ == "__main__":
    unittest.main()
