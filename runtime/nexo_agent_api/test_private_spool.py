"""Private scheduled Sheet ingress security and autonomy regressions."""
import copy
import unittest

from .private_spool import CONTRACT, PrivateSpoolError, validated_private_sheet_items
from .inbox_apply import proposal_to_requests, ProposalError


def envelope(kind="BOARD_POST", source="PITIA", payload=None):
    return {
        "kind": kind,
        "source": source,
        "created_at": "2026-10-12T15:00:00Z",
        "intent_id": "NEXO-SCHEDULED-TEST-001",
        "payload": payload if payload is not None else
            {"to": "EXECUTOR", "text": "Valide o input existente com a fonte oficial."},
    }


def doc(rows):
    return {"contract": CONTRACT, "items": rows}


def row(env, stable="sched-v2-abc001"):
    return {"stable_id": stable, "envelope": env}


class PrivateSpoolTests(unittest.TestCase):
    def test_board_and_ordinary_science_are_admitted_with_private_not_public_provenance(self):
        for kind, source, body in (
            ("BOARD_POST", "PITIA", {"to": "LEARNER", "text": "Revisar proposta."}),
            ("HYPOTHESIS_PROPOSAL", "LEARNER", {"question": "Hipotese?", "null": "LCDM"}),
            ("INTEGRITY_REPORT", "GUARDIAO", {"status": "YELLOW", "issues": []}),
            ("SEMANTIC_BACKFILL", "ADVISOR", {"items": []}),
        ):
            with self.subTest(kind=kind):
                [item] = validated_private_sheet_items(doc([row(envelope(kind, source, body))]))
                self.assertEqual(item["_inbox_source"], "DRIVE_SHEET")
                self.assertEqual(item["_inbox_id"], "drive-sheet:sched-v2-abc001")
                self.assertEqual(item["kind"], kind)
                self.assertTrue(item["_inbox_name"].startswith("scheduled-ps-"))

    def test_private_handoff_and_transition_keep_normal_role_and_writer_gates(self):
        handoff = dict(request_id="REQ-SHEET-001", from_role="ADVISOR",
                       to_role="EXECUTOR", handoff_type="RESEARCH_READY",
                       entity_ref="WORK::SYNTHETIC", thread_id="THREAD::SYNTHETIC",
                       summary_plain="Input verificado.", why_it_matters="Destrava contrato.",
                       next_action="Executar teste ja registrado.")
        [item] = validated_private_sheet_items(doc([
            row(envelope("HANDOFF", "ENGINEER", handoff))
        ]))
        [request] = proposal_to_requests(item, "/tmp")
        self.assertEqual(request["nexo_operation"], "HANDOFF_CREATE")
        self.assertEqual(request["_inbox_source"], "DRIVE_SHEET")
        [item] = validated_private_sheet_items(doc([
            row(envelope("HANDOFF_TRANSITION", "EXECUTOR",
                {"handoff_id": "HO-SYNTHETIC", "state": "ACK", "writer_role": "EXECUTOR"}))
        ]))
        [request] = proposal_to_requests(item, "/tmp")
        self.assertEqual(request["nexo_operation"], "HANDOFF_TRANSITION")
        self.assertEqual(request["_inbox_source"], "DRIVE_SHEET")

    def test_public_gateway_metadata_cannot_self_authorize_private_handoff(self):
        candidate = envelope("HANDOFF", "ADVISOR",
                             {"handoff_id": "FAKE", "from_role": "ADVISOR"})
        with self.assertRaisesRegex(ProposalError, "PRIVATE_HANDOFF_REQUIRES_DRIVE_INBOX"):
            proposal_to_requests({**candidate, "_inbox_source": "GATEWAY"}, "/tmp")
        with self.assertRaisesRegex(ProposalError, "PRIVATE_HANDOFF_REQUIRES_DRIVE_INBOX"):
            proposal_to_requests({**candidate, "source": "DRIVE_SHEET"}, "/tmp")

    def test_sensitive_actions_and_impersonation_are_refused(self):
        vectors = [
            envelope("OPERATOR_INTENT", "DENER", {"action": "APPROVE_AUTONOMY_MANDATE"}),
            envelope("HANDOFF", "PITIA", {"from_role": "PITIA"}),
            envelope("HANDOFF_TRANSITION", "LEARNER",
                     {"handoff_id": "H-1", "state": "DONE", "writer_role": "EXECUTOR"}),
            envelope("MUTATION_PROPOSAL", "LEARNER", {"test_id": "TEST-1"}),
            envelope("VERDICT_REVIEW", "EXECUTOR", {"test_id": "TEST-1"}),
            envelope("ENXAME_EVENT", "EXECUTOR", {}),
        ]
        for item in vectors:
            with self.subTest(kind=item["kind"], source=item["source"]):
                with self.assertRaises(PrivateSpoolError):
                    validated_private_sheet_items(doc([row(item)]))

    def test_cross_envelope_id_conflict_rejected_but_exact_replay_deduplicated(self):
        item = row(envelope())
        self.assertEqual(len(validated_private_sheet_items(doc([item, copy.deepcopy(item)]))), 1)
        other = copy.deepcopy(item)
        other["envelope"]["payload"]["text"] = "Payload divergente."
        with self.assertRaisesRegex(PrivateSpoolError, "STABLE_ID_CONFLICT"):
            validated_private_sheet_items(doc([item, other]))

    def test_fails_on_untrusted_annotations_and_missing_identity(self):
        item = row(envelope())
        bad = copy.deepcopy(item)
        bad["envelope"]["_inbox_source"] = "DRIVE"
        with self.assertRaisesRegex(PrivateSpoolError, "ENVELOPE_FIELDS"):
            validated_private_sheet_items(doc([bad]))
        bad = copy.deepcopy(item)
        bad["stable_id"] = "another-channel"
        with self.assertRaisesRegex(PrivateSpoolError, "STABLE_ID_INVALID"):
            validated_private_sheet_items(doc([bad]))


if __name__ == "__main__":
    unittest.main()
