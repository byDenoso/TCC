"""Regression coverage for the unattended Writer, with isolated transport."""
import json
import os
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock, patch

from runtime.nexo_agent_api import gpt_writer
from runtime.nexo_agent_api import operation_receipts
from runtime.nexo_agent_api.evolution import _emergence, _review_queue


class ReviewClockTest(unittest.TestCase):
    def test_missing_and_mixed_clocks_keep_originals_in_oldest_first_queue(self):
        rows = [
            {"id": "new", "executed_at": "2026-09-30T06:00:00-03:00"},
            {"id": "old", "executed_at": {"at": "2026-09-30T08:00:00Z"}},
            {"id": "missing"},
            {"id": "bad", "updated_at": "unknown"},
            {"id": "closed", "review_state": "CONFIRMED"},
            {"id": "attack", "contests_test_id": "old"},
            {"id": "archived", "state": "ARCHIVED"},
        ]
        self.assertEqual(_review_queue(rows)["referee_1"], ["bad", "missing", "old", "new"])


class WatchdogActionabilityTest(unittest.TestCase):
    def test_quiet_science_is_only_flagged_when_the_owner_has_work(self):
        now = datetime(2026, 9, 30, 12, 0, tzinfo=timezone.utc)
        genome = {"genes": [], "fitness": [], "lineage": []}
        with tempfile.TemporaryDirectory() as work:
            root = Path(work)
            full_reserve = [{"id": f"ready-{i}", "status": "READY"} for i in range(30)]
            stale = {row["loop"] for row in _emergence(root, full_reserve, genome, now)["stale"]}
            self.assertNotIn("new_hypothesis", stale)
            self.assertNotIn("contest", stale)

            low_reserve = full_reserve[:-1]
            stale = {row["loop"] for row in _emergence(root, low_reserve, genome, now)["stale"]}
            self.assertIn("new_hypothesis", stale)

            reviewable_positive = full_reserve + [{
                "id": "positive", "status": "RESULT", "verdict": "SUPPORTED", "review_state": "PENDING_REVIEW",
            }]
            stale = {row["loop"] for row in _emergence(root, reviewable_positive, genome, now)["stale"]}
            self.assertIn("contest", stale)


class RobotPersistenceTest(unittest.TestCase):
    def test_no_op_family_stage_never_discards_previously_applied_proposals(self):
        tower = Mock()
        tower.download.return_value = (b"original", "revision")
        tower.compare_and_swap.return_value = {"state_fingerprint": "committed", "readback": True}
        inbox = Mock()
        inbox.pending.return_value = []
        github = Mock(seen=[])
        github.pending.return_value = []
        calls = []
        intent = "gateway:isolated-engineering"
        gateway_receipt = operation_receipts.public_receipt(operation_receipts.build_receipt(
            intent=intent,
            payload_sha256=operation_receipts.payload_hash({"kind": "BOARD_POST", "source": "ENGINEER",
                                                            "payload": {"domain": "ENGINEERING"}}),
            effect=operation_receipts.envelope_effect_id(intent), outcome="APPLIED",
            source_revision="sha256:" + "1" * 64, result_revision="sha256:" + "2" * 64,
            visibility="PUBLIC"))

        def apply(raw, items):
            calls.append(raw)
            stage = items[0]["kind"]
            changed = b"applied" if stage == "BOARD_POST" else None
            return changed, {
                "before": "original" if changed else "applied",
                "after": "applied",
                "status": "READY_TO_UPLOAD" if changed else "NO_OP",
                "applied": [items[0].get("_inbox_name", stage)],
                "rejected": [],
                "public_operation_receipts": [gateway_receipt] if changed else [],
            }

        with tempfile.TemporaryDirectory() as work:
            gateway = Path(work, "gateway.json")
            gateway.write_text(json.dumps({"items": [{"id": "isolated-engineering", "envelope": {
                "kind": "BOARD_POST", "source": "ENGINEER", "payload": {"domain": "ENGINEERING"}
            }}]}))
            output = Path(work, "outputs")
            with patch.dict(os.environ, {"NEXO_GATEWAY_ITEMS": str(gateway), "GITHUB_OUTPUT": str(output), "NEXO_HOME": str(Path(work) / "nexo-home")}, clear=True), \
                 patch("runtime.nexo_agent_api.drive_transport.DriveTower", return_value=tower), \
                 patch("runtime.nexo_agent_api.drive_transport.DriveInbox", return_value=inbox), \
                 patch.object(gpt_writer, "_GitHubInbox", return_value=github), \
                 patch.object(gpt_writer, "apply_to_tower", side_effect=apply), \
                 patch.object(gpt_writer, "_stop_closures", return_value=[{"kind": "close"}]), \
                 patch.object(gpt_writer, "_family_items", side_effect=lambda raw, kind: [{"kind": kind}]), \
                 patch.object(gpt_writer, "_queued_batteries", return_value=[]):
                self.assertEqual(gpt_writer.main(["robot"]), 0)
            tower.compare_and_swap.assert_called_once_with("revision", b"applied")
            self.assertEqual(calls, [b"original"] + [b"applied"] * 5)
            self.assertIn("tower_revision=committed", output.read_text())
            self.assertIn("gateway_reported=isolated-engineering", output.read_text())
            self.assertIn("gateway_resolved=isolated-engineering", output.read_text())


if __name__ == "__main__":
    unittest.main()
