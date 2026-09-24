from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

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

    def test_unapplicable_proposals_are_recorded_not_lost(self):
        for item in ({"kind": "MUTATION_PROPOSAL", "payload": {"test_id": "T-1", "result": {}}},
                     {"kind": "MUTATION_PROPOSAL", "payload": {"test_id": "NOPE", "result": {"verdict": "PASS"}}},
                     {"kind": "HYPOTHESIS_PROPOSAL", "payload": {"test_id": "H-1", "semantic": {"domain_id": "science"}}}):
            [request] = proposal_to_requests(item, self.root)
            self.assertEqual(request["entity_kind"], "artifact")
            self.assertTrue(request["changes"]["kind"].startswith("UNAPPLIED_"))
            self.assertIn("_not_applied_reason", request["changes"]["payload"])

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


if __name__ == "__main__":
    unittest.main()
