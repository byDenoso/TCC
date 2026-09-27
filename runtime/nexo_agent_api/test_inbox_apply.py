from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from runtime.nexo_agent_api.inbox_apply import ProposalError, proposal_to_requests
from runtime.nexo_agent_api.tower_paths import entity_path


class InboxApplyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        path = entity_path(self.root, "test", "T-1")
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps({"id": "T-1", "entity_version": 3, "status": "READY",
                                    "semantic": {"domain_id": "science", "topic_id": "x"}}))

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_result_proposal_keeps_semantic_and_bumps_from_current_version(self):
        item = {"kind": "MUTATION_PROPOSAL", "created_at": "2026-09-24T00:00:00Z",
                "payload": {"test_id": "T-1", "result": {"veredito": "inconclusive", "estatísticas": {"sigma": 1.2}},
                            "semantic": {"result_meaning": "Nada robusto."}}}
        [request] = proposal_to_requests(item, self.root)
        self.assertEqual(request["expected_version"], 3)
        self.assertEqual(request["changes"]["verdict"], "INCONCLUSIVE")
        self.assertEqual(request["changes"]["statistics"], {"sigma": 1.2})
        self.assertEqual(request["changes"]["semantic"]["topic_id"], "x")
        self.assertEqual(request["changes"]["semantic"]["result_meaning"], "Nada robusto.")

    def test_incomplete_proposals_are_completed_not_rejected(self):
        # result without a plain reading -> provisional reading, still recorded on the test
        [request] = proposal_to_requests({"kind": "MUTATION_PROPOSAL", "payload": {"test_id": "T-1", "result": {}}}, self.root)
        self.assertEqual(request["entity_kind"], "test")
        self.assertEqual(request["changes"]["semantic"]["result_meaning_source"], "WRITER_PROVISIONAL")
        # result for a test that does not exist -> the test is registered first, then the result
        requests = proposal_to_requests({"kind": "MUTATION_PROPOSAL", "payload": {"test_id": "NOPE", "result": {"verdict": "PASS"}}}, self.root)
        tests = [r for r in requests if r.get("entity_kind") == "test"]
        self.assertEqual([r["entity_name"] for r in tests], ["NOPE", "NOPE"])
        self.assertEqual(tests[-1]["changes"]["verdict"], "PASS")
        # hypothesis without frozen criteria -> DRAFT, never READY, never dropped
        requests = proposal_to_requests({"kind": "HYPOTHESIS_PROPOSAL", "payload": {"test_id": "H-1", "semantic": {"domain_id": "science"}}}, self.root)
        self.assertEqual(requests[0]["changes"]["status"], "DRAFT")

    def test_generic_shapes_are_understood(self):
        # no kind, batch under "results", verdict at top level, meaning only in verdict_plain
        item = {"payload": {"results": [{"test_id": "T-1", "veredito": "PASS", "semantic": {"verdict_plain": "Passou."}}]}}
        [request] = proposal_to_requests(item, self.root)
        self.assertEqual(request["entity_kind"], "test")
        self.assertEqual(request["changes"]["verdict"], "PASS")
        self.assertEqual(request["changes"]["semantic"]["result_meaning"], "Passou.")

    def test_unknown_kind_is_recorded(self):
        [request] = proposal_to_requests({"kind": "SOMETHING_NEW", "payload": {"x": 1}}, self.root)
        self.assertEqual(request["changes"]["kind"], "INBOX_RECORD")

    def test_signal_is_recorded_as_artifact(self):
        [request] = proposal_to_requests({"kind": "LEARNING_SIGNAL", "payload": {"signals": []}, "_inbox_name": "a b"}, self.root)
        self.assertEqual(request["entity_kind"], "artifact")
        self.assertEqual(request["entity_name"], "LEARNING_SIGNAL::A-B")




class HandoffProtocolCIRegressionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "entities" / "work").mkdir(parents=True)

    def tearDown(self):
        self.tmp.cleanup()

    def test_idempotent_send_recipient_transition_and_citations(self):
        from runtime.nexo_agent_api import AgentService, TowerAgentIssue

        service = AgentService(self.root)
        envelope = {
            "request_id": "REQ-CI-HANDOFF-001",
            "from_role": "ADVISOR",
            "to_role": "EXECUTOR",
            "handoff_type": "RESEARCH_READY",
            "entity_ref": "WORK::DE-CI",
            "thread_id": "THR::DE-CI",
            "summary_plain": "Uma fonte primária relevante foi ligada ao objetivo atual.",
            "why_it_matters": "Ela altera a prioridade do próximo teste discriminante, não o resultado científico.",
            "next_action": "Executar o teste já congelado usando a fonte citada como entrada observacional.",
            "objective_ref": "OBJ::DARK-ENERGY-NATURE",
            "evidence_refs": [{"ref": "TEST::DE-CI", "kind": "TEST"}],
            "source_links": [{
                "label": "Original survey release",
                "url": "https://example.org/survey",
                "access_date": "2026-09-27",
                "publisher": "Example Survey",
                "authors": ["A. Author"],
                "date": "2026-09-26",
                "supports": "Sustenta a medição observacional usada como entrada.",
                "uncertainty": "Não determina o veredito científico.",
                "next_test_impact": "Prioriza o próximo discriminante sem reescrever critérios.",
            }],
        }
        first = service.emit_handoff(**envelope)
        replay = service.emit_handoff(**envelope)
        self.assertEqual(first["event_id"], replay["event_id"])
        self.assertEqual(len(list((self.root / "events").rglob("*.json"))), 1)

        with self.assertRaises(TowerAgentIssue) as wrong:
            service.transition_handoff(first["handoff_id"], state="ACK", writer_role="LEARNER")
        self.assertEqual(wrong.exception.code, "HANDOFF_WRITER_MISMATCH")

        ack = service.transition_handoff(first["handoff_id"], state="ACK", writer_role="EXECUTOR")
        done = service.transition_handoff(first["handoff_id"], state="DONE", writer_role="EXECUTOR")
        self.assertEqual(ack["source_links"][0]["url"], "https://example.org/survey")
        self.assertEqual(done["evidence_refs"], envelope["evidence_refs"])
        self.assertEqual(service.inbox_for("EXECUTOR"), [])

    def test_human_fields_reject_internal_codes_but_keep_structured_refs_private(self):
        from runtime.nexo_agent_api import AgentService, TowerAgentIssue

        service = AgentService(self.root)
        base = {
            "request_id": "REQ-CI-LANGUAGE-001",
            "from_role": "ADVISOR",
            "to_role": "EXECUTOR",
            "handoff_type": "RESEARCH_READY",
            "entity_ref": "WORK::DE-LANGUAGE",
            "thread_id": "THR::DE-LANGUAGE",
            "summary_plain": "Uma nova medição pública pode ajudar a separar duas explicações para a energia escura.",
            "why_it_matters": "Ela permite comparar previsões diferentes sem mudar as regras já definidas para o teste.",
            "next_action": "Use a fonte citada no próximo teste já planejado e registre o efeito observado.",
            "confidence_plain": "Confiança moderada porque a fonte mede a quantidade necessária, mas ainda não decide qual explicação é correta.",
            "evidence_refs": [{"ref": "TEST::DE-LANGUAGE", "kind": "TEST"}],
        }
        created = service.emit_handoff(**base)
        self.assertEqual(created["evidence_refs"], [{"ref": "TEST::DE-LANGUAGE", "kind": "TEST"}])
        self.assertNotIn("TEST::DE-LANGUAGE", created["summary_plain"])

        bad = dict(base, request_id="REQ-CI-LANGUAGE-RAW-REF",
                   summary_plain="Use TEST::DE-LANGUAGE e aguarde o readback.")
        with self.assertRaises(TowerAgentIssue) as leaked:
            service.emit_handoff(**bad)
        self.assertIn(
            leaked.exception.code,
            {"HANDOFF_PLAIN_FIELD_LEAKS_INTERNAL_REF", "HANDOFF_PLAIN_FIELD_MACHINE_LANGUAGE"},
        )

        bad_confidence = dict(base, request_id="REQ-CI-LANGUAGE-CONFIDENCE", confidence_plain="HIGH")
        with self.assertRaises(TowerAgentIssue) as machine_confidence:
            service.emit_handoff(**bad_confidence)
        self.assertEqual(machine_confidence.exception.code, "HANDOFF_PLAIN_FIELD_MACHINE_LANGUAGE")

        bad_field = dict(base, request_id="REQ-CI-LANGUAGE-FIELD",
                         next_action="Atualize o topic_id antes de continuar.")
        with self.assertRaises(TowerAgentIssue) as field_name:
            service.emit_handoff(**bad_field)
        self.assertEqual(field_name.exception.code, "HANDOFF_PLAIN_FIELD_LEAKS_INTERNAL_REF")

    def test_same_request_id_with_different_content_is_rejected(self):
        from runtime.nexo_agent_api import AgentService, TowerAgentIssue

        service = AgentService(self.root)
        base = {
            "request_id": "REQ-CI-HANDOFF-CONFLICT",
            "from_role": "EXECUTOR",
            "to_role": "LEARNER",
            "handoff_type": "RESULT_READY",
            "entity_ref": "WORK::CI",
            "thread_id": "THR::CI",
            "summary_plain": "O resultado canônico está pronto.",
            "why_it_matters": "A aprendizagem depende deste resultado persistido.",
            "next_action": "Registrar a lição vinculada ao resultado.",
        }
        service.emit_handoff(**base)
        changed = dict(base, next_action="Executar uma ação materialmente diferente.")
        with self.assertRaises(TowerAgentIssue) as conflict:
            service.emit_handoff(**changed)
        self.assertEqual(conflict.exception.code, "HANDOFF_REQUEST_ID_CONFLICT")


class HandoffCLIPersistenceTests(unittest.TestCase):
    def test_create_handoff_uses_writer_lock_cas_readback_and_atlas_notification(self):
        from scripts import nexo_tower

        calls = {"lock": 0, "cas": 0, "notify": []}

        class FakeLock:
            def __enter__(self):
                calls["lock"] += 1
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

        class FakeDriveTower:
            def __init__(self, write=False):
                self.write = write

            def download(self):
                return b"raw-before", "BASE-HEAD"

            def compare_and_swap(self, base, packed):
                self_base = base
                assert self.write is True
                assert self_base == "BASE-HEAD"
                assert packed == b"raw-after"
                calls["cas"] += 1
                return {
                    "status": "PASS",
                    "state_fingerprint": "sha256:after",
                    "head_revision_id": "HEAD-AFTER",
                    "readback": "PASS",
                }

        def fake_materialize(raw, dest):
            self.assertEqual(raw, b"raw-before")
            Path(dest).mkdir(parents=True, exist_ok=True)
            return Path(dest), {"tower_revision": "sha256:before"}

        def fake_publish(root):
            (Path(root) / nexo_tower.LIVE_TOWER_NAME).write_bytes(b"raw-after")
            return {"status": "PASS", "revision": "sha256:after"}

        def fake_verify(raw):
            if raw == b"raw-before":
                return "sha256:before"
            if raw == b"raw-after":
                return "sha256:after"
            raise AssertionError(raw)

        with tempfile.TemporaryDirectory() as tmp:
            envelope = Path(tmp) / "handoff.json"
            envelope.write_text(json.dumps({
                "request_id": "REQ-CLI-HANDOFF-001",
                "from_role": "EXECUTOR",
                "to_role": "LEARNER",
                "handoff_type": "RESULT_READY",
                "entity_ref": "WORK::SCIENCE-CLI",
                "thread_id": "THR::SCIENCE::CLI",
                "summary_plain": "O resultado persistido está pronto para aprendizagem.",
                "why_it_matters": "A próxima automação pode continuar sem reconstruir o contexto.",
                "next_action": "Ler o resultado canônico e registrar a lição correspondente.",
                "evidence_refs": [{"ref": "TEST::SCIENCE-CLI", "kind": "TEST"}],
                "source_links": [{
                    "label": "Primary paper",
                    "url": "https://example.org/paper",
                    "access_date": "2026-09-27",
                    "publisher": "Example Collaboration",
                    "authors": ["A. Author"],
                    "date": "2026-09-26",
                    "supports": "Sustenta apenas a entrada observacional citada.",
                    "uncertainty": "Não é um resultado do NEXO.",
                    "next_test_impact": "Informa o próximo teste discriminante sem mudar critérios congelados.",
                }],
            }), encoding="utf-8")
            args = type("Args", (), {
                "action": "create",
                "envelope": str(envelope),
                "dry_run": False,
                "retries": 0,
            })()

            output = io.StringIO()
            with patch.object(nexo_tower, "DriveTower", FakeDriveTower), \
                 patch.object(nexo_tower, "writer_lock", lambda: FakeLock()), \
                 patch.object(nexo_tower, "materialize_live_tower", fake_materialize), \
                 patch.object(nexo_tower, "read_live_tower_bytes", lambda raw: raw), \
                 patch.object(nexo_tower, "verify_live_tower", fake_verify), \
                 patch("runtime.nexo_agent_api.live_tower.publish_live_tower", fake_publish), \
                 patch.object(nexo_tower, "_notify_atlas", lambda fingerprint: calls["notify"].append(fingerprint) or "DISPATCHED_TEST"), \
                 contextlib.redirect_stdout(output):
                code = nexo_tower.cmd_handoff(args)

        self.assertEqual(code, 0)
        self.assertEqual(calls["lock"], 1)
        self.assertEqual(calls["cas"], 1)
        self.assertEqual(calls["notify"], ["sha256:after"])
        payload = json.loads(output.getvalue())
        self.assertEqual(payload["status"], "PASS")
        self.assertEqual(payload["write"]["readback"], "PASS")
        self.assertEqual(payload["after"], "sha256:after")
        self.assertEqual(payload["handoff"]["request_id"], "REQ-CLI-HANDOFF-001")
        self.assertEqual(payload["handoff"]["source_links"][0]["access_date"], "2026-09-27")

if __name__ == "__main__":
    unittest.main()


class SiteFormatTests(unittest.TestCase):
    def test_new_hypothesis_inherits_roadmap_context_and_semantics(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sib = entity_path(root, "test", "S-1")
            sib.parent.mkdir(parents=True)
            sib.write_text(json.dumps({"id": "S-1", "campaign_id": "CAMP-X", "hypothesis_id": "HYP-X",
                                       "semantic": {"topic_id": "science.cosmology.dark_matter.nature"}}))
            (root / "roadmaps").mkdir()
            (root / "roadmaps" / "RM-X.json").write_text(json.dumps({"frontier_refs": ["S-1"]}))
            requests = proposal_to_requests({"kind": "HYPOTHESIS_PROPOSAL", "payload": {
                "test_id": "H-2", "roadmap_id": "RM-X", "question": "Does X happen?",
                "success_criteria": "a", "kill_criteria": "b"}}, root)
            test = requests[0]["changes"]
            self.assertEqual(test["campaign_id"], "CAMP-X")
            self.assertEqual(test["hypothesis_id"], "HYP-X")
            self.assertEqual(test["roadmap_test_id"], "H-2")
            self.assertEqual(test["semantic"]["subdomain_id"], "science.cosmology.dark_matter")
            self.assertEqual(test["semantic"]["question_plain"], "Does X happen?")
            [merge] = [r for r in requests if "document" in r]
            self.assertEqual(merge["merge"]["frontier_refs"], ["S-1", "H-2"])
            [hyp] = [r for r in requests if r.get("entity_kind") == "hypothesis"]
            self.assertEqual(hyp["entity_name"], "HYP-X")
            self.assertEqual(hyp["changes"]["falsification_criterion"], "b")


class RedactTests(unittest.TestCase):
    def test_backfill_redacts_names_in_legacy_fields_but_not_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = entity_path(root, "campaign", "CAMP-OLY-JOAO-1")
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps({"id": "CAMP-OLY-JOAO-1", "entity_version": 2, "subject_code": "JOA",
                                        "title": "Campanha do Joao", "meta": {"display_name": "JOAO SILVA", "source_ref": "x/joao.csv"}}))
            [req] = proposal_to_requests({"kind": "SEMANTIC_BACKFILL", "payload": {"items": [
                {"id": "CAMP-OLY-JOAO-1", "entity_kind": "campaign", "redact_names": ["Joao", "Silva"]}]}}, root)
            self.assertEqual(req["changes"]["title"], "Campanha do JOA")
            self.assertEqual(req["changes"]["meta"], {"display_name": "JOA JOA", "source_ref": "x/JOA.csv"})
            self.assertNotIn("id", req["changes"])
