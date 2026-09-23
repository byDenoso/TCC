from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from .global_reconciler import reconcile_verified_work, validate_terminal_render_readback
from runtime.nexo_agent_api.tower_paths import entity_path


class GlobalReconcilerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "indexes").mkdir(parents=True)
        (self.root / "entities" / "work").mkdir(parents=True)
        (self.root / "snapshot").mkdir(parents=True)
        (self.root / "manifests").mkdir(parents=True)
        (self.root / "CONTROL.json").write_text(json.dumps({"mode": "ACTIVE"}), encoding="utf-8")
        (self.root / "snapshot" / "latest.json").write_text(json.dumps({}), encoding="utf-8")
        (self.root / "manifests" / "capabilities.json").write_text(json.dumps({"capabilities": {}}), encoding="utf-8")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def write_work(self, work_id: str, **payload) -> None:
        value = {"id": work_id, "entity_version": 1, "kind": "ACTION", "owner_role": "EXECUTOR", **payload}
        (entity_path(self.root, "work", work_id)).write_text(json.dumps(value), encoding="utf-8")

    @staticmethod
    def proof(**overrides):
        value = {
            "status": "PASS",
            "rendered": True,
            "http_status": 200,
            "url": "https://example.test/app",
            "render_marker": "data-app-ready=true",
            "observed_revision": "abc123",
            "projection_fingerprint": "sha256:" + "a" * 64,
            "readback_ref": "ci://run/42",
        }
        value.update(overrides)
        return value

    def seed_queue(self) -> None:
        (self.root / "indexes" / "active-work.json").write_text(json.dumps({"work": [
            {"id": "W-VERIFY", "entity_version": 1, "status": "VERIFY_PENDING", "owner_role": "EXECUTOR", "kind": "ACTION", "domain": "ENGINEERING"},
            {"id": "W-NEXT", "entity_version": 1, "status": "READY", "owner_role": "EXECUTOR", "kind": "ACTION", "domain": "ENGINEERING", "task_id": "cosmology_benchmark"},
            {"id": "W-SCI", "entity_version": 1, "status": "READY", "owner_role": "EXECUTOR", "kind": "ACTION", "domain": "SCIENCE", "task_id": "cosmology_benchmark"},
        ]}), encoding="utf-8")

    def test_render_readback_is_stricter_than_deploy_success(self) -> None:
        work = {"expected_deploy_revision": "abc123"}
        with self.assertRaisesRegex(ValueError, "RENDER_NOT_PROVEN"):
            validate_terminal_render_readback(work, self.proof(rendered=False))
        with self.assertRaisesRegex(ValueError, "REVISION_MISMATCH"):
            validate_terminal_render_readback(work, self.proof(observed_revision="other"))

    def test_verify_pending_closes_and_starts_next_in_same_reconciliation(self) -> None:
        self.seed_queue()
        self.write_work("W-VERIFY", status="VERIFY_PENDING", operational_status="VERIFY_PENDING", domain="ENGINEERING", expected_deploy_revision="abc123", expected_projection_fingerprint="sha256:" + "a" * 64)
        self.write_work("W-NEXT", status="READY", operational_status="READY", domain="ENGINEERING", task_id="cosmology_benchmark")
        self.write_work("W-SCI", status="READY", operational_status="READY", domain="SCIENCE", task_id="cosmology_benchmark")

        result = reconcile_verified_work(
            self.root,
            work_id="W-VERIFY",
            readback=self.proof(),
            allowed_domains={"ENGINEERING"},
            now="2026-09-22T21:00:00Z",
        )

        self.assertEqual(result["outcome"], "CLOSED_VERIFIED")
        self.assertFalse(result["replay"])
        closed = json.loads((entity_path(self.root, "work", "W-VERIFY")).read_text())
        self.assertEqual(closed["status"], "DONE")
        self.assertEqual(closed["closure_state"], "CLOSED_VERIFIED")
        self.assertEqual(closed["verification_status"], "PASS")
        self.assertTrue(closed["terminal_readback"]["rendered"])
        self.assertEqual(result["continuation"]["action"], "SELECT_NEXT")
        self.assertEqual(result["continuation"]["work_id"], "W-NEXT")
        self.assertTrue(result["continuation"]["started"])
        next_work = json.loads((entity_path(self.root, "work", "W-NEXT")).read_text())
        self.assertEqual(next_work["status"], "RUNNING")
        self.assertEqual(next_work["selection_state"], "SELECT_NEXT")
        science = json.loads((entity_path(self.root, "work", "W-SCI")).read_text())
        self.assertEqual(science["status"], "READY")

    def test_failed_readback_keeps_work_verify_pending(self) -> None:
        self.seed_queue()
        self.write_work("W-VERIFY", status="VERIFY_PENDING", operational_status="VERIFY_PENDING", domain="ENGINEERING")
        with self.assertRaisesRegex(ValueError, "HTTP_NOT_SUCCESS"):
            reconcile_verified_work(
                self.root,
                work_id="W-VERIFY",
                readback=self.proof(http_status=503),
                allowed_domains={"ENGINEERING"},
            )
        work = json.loads((entity_path(self.root, "work", "W-VERIFY")).read_text())
        self.assertEqual(work["status"], "VERIFY_PENDING")
        self.assertNotIn("closure_state", work)

    def test_replay_is_idempotent_and_does_not_restart_running_next(self) -> None:
        self.seed_queue()
        self.write_work("W-VERIFY", status="DONE", operational_status="DONE", domain="ENGINEERING", closure_state="CLOSED_VERIFIED", verification_status="PASS")
        self.write_work("W-NEXT", status="RUNNING", operational_status="RUNNING", domain="ENGINEERING", task_id="cosmology_benchmark")
        self.write_work("W-SCI", status="READY", operational_status="READY", domain="SCIENCE", task_id="cosmology_benchmark")
        result = reconcile_verified_work(
            self.root,
            work_id="W-VERIFY",
            readback=self.proof(),
            allowed_domains={"ENGINEERING"},
        )
        self.assertTrue(result["replay"])
        self.assertEqual(result["continuation"]["action"], "SELECT_NEXT")
        self.assertEqual(result["continuation"]["work_id"], "W-NEXT")
        self.assertEqual(result["continuation"]["state"], "RUNNING")


if __name__ == "__main__":
    unittest.main()
