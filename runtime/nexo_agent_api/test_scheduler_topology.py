from __future__ import annotations

import unittest

from .scheduler_topology import reconcile_scheduler_policy


class SchedulerTopologyTests(unittest.TestCase):
    def test_legacy_single_scheduler_claim_is_reconciled_to_runtime_truth(self) -> None:
        control = {
            "domain_workflow_policy": {
                "scheduler": "NEXO_CORE_LOOP_LEAN_MIN_V2",
                "one_scheduler_for_all_domains": True,
                "domain_contract_owns_workflow": True,
            }
        }
        result = reconcile_scheduler_policy(control)
        self.assertTrue(result["changed"])
        policy = result["domain_workflow_policy"]
        self.assertFalse(policy["one_scheduler_for_all_domains"])
        self.assertEqual(policy["execution_scheduler_topology"], "TWO_EXECUTORS_DOMAIN_SPLIT_V1")
        self.assertEqual(policy["execution_schedulers"]["GENERAL"], "NEXO_GENERAL_EXECUTION_LOOP")
        self.assertEqual(policy["execution_schedulers"]["SCIENCE"], "NEXO_CORE_LOOP_LEAN_MIN_V2")
        self.assertFalse(policy["learning_loops_are_execution_schedulers"])
        self.assertTrue(policy["domain_contract_owns_workflow"])

    def test_reconciled_policy_is_idempotent(self) -> None:
        first = reconcile_scheduler_policy({"domain_workflow_policy": {}})
        second = reconcile_scheduler_policy({"domain_workflow_policy": first["domain_workflow_policy"]})
        self.assertFalse(second["changed"])


if __name__ == "__main__":
    unittest.main()
