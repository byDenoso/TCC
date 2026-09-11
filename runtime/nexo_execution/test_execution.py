import unittest

from runtime.nexo_execution.core import ExecutionContract, ExecutionResult, ResultVerifier
from runtime.nexo_execution.router import RoutingInput, choose_provider


BASE = {
    "schema": "nexo.execution.v1",
    "execution_id": "EXEC-TEST-001",
    "work_id": "WORK-TEST-001",
    "test_id": "T-INFRA-001",
    "provider": "github_actions",
    "repository": "byDenoso/TCC",
    "commit_sha": "abc123",
    "task_id": "cosmology_benchmark",
    "parameters": {},
    "seed": 1,
    "timeout_minutes": 10,
    "required_outputs": ["result.json"],
}


class ExecutionTests(unittest.TestCase):
    def test_contract_hash_is_stable(self):
        a = ExecutionContract.from_dict(dict(BASE))
        b = ExecutionContract.from_dict(dict(BASE))
        self.assertEqual(a.contract_hash, b.contract_hash)

    def test_unknown_task_is_rejected(self):
        data = dict(BASE)
        data["task_id"] = "not_allowed"
        with self.assertRaises(ValueError):
            ExecutionContract.from_dict(data)

    def test_router_local_for_short_serial_work(self):
        self.assertEqual(choose_provider(RoutingInput(expected_runtime_minutes=2)), "local")

    def test_router_actions_for_heavy_work(self):
        self.assertEqual(choose_provider(RoutingInput(expected_runtime_minutes=20)), "github_actions")
        self.assertEqual(choose_provider(RoutingInput(parallelizable=True)), "github_actions")
        self.assertEqual(choose_provider(RoutingInput(requires_checkpoint=True)), "github_actions")

    def test_rollback_switch_forces_local(self):
        self.assertEqual(
            choose_provider(RoutingInput(expected_runtime_minutes=60, parallelizable=True, external_enabled=False)),
            "local",
        )

    def test_verifier_passes_matching_result(self):
        contract = ExecutionContract.from_dict(dict(BASE))
        result = ExecutionResult(
            execution_id=contract.execution_id,
            work_id=contract.work_id,
            provider=contract.provider,
            run_id="1",
            commit_sha=contract.commit_sha,
            exit_code=0,
            started_at=1.0,
            finished_at=2.0,
            outputs=[{"path": "result.json", "sha256": "deadbeef", "bytes": 1}],
            contract_hash=contract.contract_hash,
        )
        self.assertEqual(ResultVerifier().verify(contract, result)["status"], "PASS")


if __name__ == "__main__":
    unittest.main()
