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
        self.assertEqual(result["correlation_id"], "CORR-CANARY-002")
        self.assertEqual(result["status"], "COMPLETED")
        self.assertEqual(result["adapter"], "canary")
        self.assertEqual(result["source_revision"], "abc123")
        self.assertEqual(result["attempt"], 1)
        self.assertEqual(result["result"]["message"], "scheduled-dispatch-canary")
        self.assertEqual(persisted, result)

    def test_request_cannot_choose_an_arbitrary_command(self):
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


if __name__ == "__main__":
    unittest.main()
