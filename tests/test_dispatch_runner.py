import json
import tempfile
import unittest
from pathlib import Path

from nexo_control_plane.dispatch import run_dispatch_request


class DispatchRunnerTests(unittest.TestCase):
    def test_canary_adapter_emits_structured_result(self):
        payload = {
            "work_id": "CANARY-002",
            "correlation_id": "CORR-CANARY-002",
            "domain": "ENGINEERING",
            "adapter": "canary",
            "source_revision": "abc123",
            "attempt": 1,
            "args": {"message": "scheduled-dispatch-canary"},
        }
        with tempfile.TemporaryDirectory() as tmp:
            request = Path(tmp) / "request.json"
            output = Path(tmp) / "result.json"
            request.write_text(json.dumps(payload), encoding="utf-8")
            result = run_dispatch_request(request, output)
            persisted = json.loads(output.read_text(encoding="utf-8"))

        self.assertEqual(result["work_id"], "CANARY-002")
        self.assertEqual(result["status"], "COMPLETED")
        self.assertEqual(result["result"]["message"], "scheduled-dispatch-canary")
        self.assertEqual(persisted, result)

    def test_execution_adapter_emits_actions_contract_for_mcmc(self):
        payload = {
            "work_id": "WORK-SCI-001",
            "correlation_id": "CORR-SCI-001",
            "domain": "SCIENCE",
            "adapter": "execution",
            "source_revision": "c4158fec93625d638ef05ecc92799bee4700513f",
            "attempt": 1,
            "args": {
                "runtime_requirement": "MCMC",
                "task_id": "cosmology_benchmark",
                "repository": "byDenoso/TCC",
                "required_outputs": ["benchmark_result.json"],
                "parameters": {},
                "seed": 20260911,
                "timeout_minutes": 15,
                "test_id": "T-DE001"
            },
        }
        with tempfile.TemporaryDirectory() as tmp:
            request = Path(tmp) / "request.json"
            output = Path(tmp) / "result.json"
            request.write_text(json.dumps(payload), encoding="utf-8")
            result = run_dispatch_request(request, output)

        self.assertEqual(result["status"], "COMPLETED")
        self.assertEqual(result["result"]["provider"], "github_actions")
        contract = result["result"]["contract"]
        self.assertEqual(contract["execution_id"], "EXEC-WORK-SCI-001-A1")
        self.assertEqual(contract["test_id"], "T-DE001")
        self.assertEqual(contract["task_id"], "cosmology_benchmark")

    def test_adapter_failure_persists_failure_receipt_and_still_raises(self):
        payload = {
            "work_id": "CANARY-003",
            "correlation_id": "CORR-CANARY-003",
            "domain": "ENGINEERING",
            "adapter": "canary",
            "source_revision": "abc123",
            "attempt": 1,
            "args": {"command": "not-permitted"},
        }
        with tempfile.TemporaryDirectory() as tmp:
            request = Path(tmp) / "request.json"
            output = Path(tmp) / "result.json"
            request.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaises(ValueError):
                run_dispatch_request(request, output)
            persisted = json.loads(output.read_text(encoding="utf-8"))

        self.assertEqual(persisted["work_id"], "CANARY-003")
        self.assertEqual(persisted["status"], "FAILED")
        self.assertEqual(persisted["error"]["type"], "ValueError")
        self.assertIn("unsupported canary args", persisted["error"]["message"])


if __name__ == "__main__":
    unittest.main()
