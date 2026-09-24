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

    def test_result_without_meaning_or_unknown_test_is_rejected(self):
        with self.assertRaises(ProposalError):
            proposal_to_requests({"kind": "MUTATION_PROPOSAL", "payload": {"test_id": "T-1", "result": {}}}, self.root)
        with self.assertRaises(ProposalError):
            proposal_to_requests({"kind": "MUTATION_PROPOSAL", "payload": {"test_id": "NOPE"}}, self.root)

    def test_hypothesis_needs_frozen_criteria(self):
        with self.assertRaises(ProposalError):
            proposal_to_requests({"kind": "HYPOTHESIS_PROPOSAL", "payload": {"test_id": "H-1",
                                  "semantic": {"domain_id": "science"}}}, self.root)

    def test_signal_is_recorded_as_artifact(self):
        [request] = proposal_to_requests({"kind": "LEARNING_SIGNAL", "payload": {"signals": []}, "_inbox_name": "a b"}, self.root)
        self.assertEqual(request["entity_kind"], "artifact")
        self.assertEqual(request["entity_name"], "LEARNING_SIGNAL::A-B")


if __name__ == "__main__":
    unittest.main()
