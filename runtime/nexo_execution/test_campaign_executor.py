from __future__ import annotations

import unittest

from runtime.nexo_execution.campaign_executor import CampaignGraph, classify_dependency


class CampaignExecutorTests(unittest.TestCase):
    def test_h0_graph_releases_first_ten_in_parallel(self):
        graph = CampaignGraph.h0_lcdm_origin(max_parallel=10)
        ready = graph.ready_tests({})
        self.assertEqual(ready, [f"T-H0LCDM26-{i:03d}" for i in range(1, 11)])

    def test_h0_graph_enforces_composition_chain(self):
        graph = CampaignGraph.h0_lcdm_origin(max_parallel=10)
        terminal = {f"T-H0LCDM26-{i:03d}": "DONE" for i in range(1, 11)}
        self.assertEqual(graph.ready_tests(terminal), ["T-H0LCDM26-011"])
        terminal["T-H0LCDM26-011"] = "DONE"
        self.assertEqual(graph.ready_tests(terminal), ["T-H0LCDM26-012"])

    def test_running_and_checkpointed_tests_are_not_redispatched(self):
        graph = CampaignGraph.h0_lcdm_origin(max_parallel=10)
        states = {"T-H0LCDM26-001": "RUNNING", "T-H0LCDM26-002": "CHECKPOINTED"}
        ready = graph.ready_tests(states)
        self.assertNotIn("T-H0LCDM26-001", ready)
        self.assertNotIn("T-H0LCDM26-002", ready)

    def test_dependency_classifier_keeps_science_configuration_out_of_hydration(self):
        self.assertEqual(classify_dependency("h0_estimator"), "SCIENTIFIC_CONTRACT")
        self.assertEqual(classify_dependency("hubble_flow_selection"), "SCIENTIFIC_CONTRACT")
        self.assertEqual(classify_dependency("external_priors"), "SCIENTIFIC_CONTRACT")
        self.assertEqual(classify_dependency("pantheon_plus_shoes"), "INPUT_ARTIFACT")
        self.assertEqual(classify_dependency("mock_observer_backend"), "CAPABILITY")


if __name__ == "__main__":
    unittest.main()
