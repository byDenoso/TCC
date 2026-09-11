import json
import tempfile
import unittest
from pathlib import Path

from nexo_control_plane.dispatch import DispatchRequest, load_dispatch_request, resolve_adapter


class DispatchRequestTests(unittest.TestCase):
    def valid_payload(self):
        return {
            "work_id": "CANARY-001",
            "correlation_id": "CORR-CANARY-001",
            "domain": "ENGINEERING",
            "adapter": "canary",
            "source_revision": "abc123",
            "attempt": 1,
            "args": {"message": "scheduled-dispatch-canary"},
        }

    def test_load_valid_request(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "request.json"
            path.write_text(json.dumps(self.valid_payload()), encoding="utf-8")
            req = load_dispatch_request(path)
        self.assertIsInstance(req, DispatchRequest)
        self.assertEqual(req.work_id, "CANARY-001")
        self.assertEqual(req.adapter, "canary")
        self.assertEqual(req.attempt, 1)

    def test_unknown_adapter_fails_closed(self):
        payload = self.valid_payload()
        payload["adapter"] = "not-allowed"
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "request.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaises(ValueError):
                load_dispatch_request(path)

    def test_work_id_rejects_path_like_identity(self):
        payload = self.valid_payload()
        payload["work_id"] = "BAD/ID"
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "request.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaises(ValueError):
                load_dispatch_request(path)

    def test_adapter_resolution_is_allowlisted(self):
        path = resolve_adapter("canary")
        self.assertEqual(path.as_posix(), "nexo_jobs/canary.py")
        with self.assertRaises(ValueError):
            resolve_adapter("arbitrary")

    def test_attempt_must_be_positive(self):
        payload = self.valid_payload()
        payload["attempt"] = 0
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "request.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaises(ValueError):
                load_dispatch_request(path)


if __name__ == "__main__":
    unittest.main()
