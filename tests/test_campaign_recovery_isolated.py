"""Exercise existing failure paths without network or a production mutation."""
import json
import os
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase, main
from unittest.mock import Mock, patch

from runtime.nexo_agent_api import gpt_writer, operation_receipts
from runtime.nexo_agent_api.drive_transport import (
    DriveHead, DriveInbox, DriveTower, TowerConflict,
    TowerReadbackMismatch, TowerTransportError, writer_lock,
)


class RecoveryIsolatedTests(TestCase):
    def test_403_is_authorization_failure_without_transport_retry(self):
        response = SimpleNamespace(status_code=403, text="denied")
        with self.assertRaises(TowerTransportError) as caught:
            DriveTower._check(response, "UPLOAD")
        self.assertEqual(str(caught.exception), "DRIVE_UPLOAD_FAILED:403:OPERATOR_REAUTHORIZATION")

    def test_429_and_503_are_explicit_transient_failures(self):
        for code in (429, 503):
            with self.subTest(code=code), self.assertRaises(TowerTransportError) as caught:
                DriveTower._check(SimpleNamespace(status_code=code, text="temporary"), "READ")
            self.assertEqual(caught.exception.retry_condition, "AFTER_TRANSPORT_RECOVERY")

    def test_uncertain_write_is_not_automatically_repeated(self):
        session = Mock()
        session.patch.side_effect = TimeoutError("private transport detail")
        tower = DriveTower(file_id="synthetic", session=session, write=True)
        with self.assertRaises(TowerTransportError) as caught:
            tower.upload(b'{"synthetic":true}')
        self.assertEqual(session.patch.call_count, 1)
        self.assertNotIn("private transport detail", str(caught.exception))

    def test_head_conflict_prevents_write(self):
        tower = DriveTower(file_id="synthetic", session=Mock(), write=True)
        base = DriveHead("1", "a", None, 1)
        with patch.object(tower, "head", return_value=DriveHead("2", "b", None, 1)), patch.object(tower, "upload") as upload:
            with self.assertRaises(TowerConflict):
                tower.compare_and_swap(base, b'{"state_fingerprint":"expected"}')
            upload.assert_not_called()

    def test_readback_mismatch_does_not_become_pass(self):
        tower = DriveTower(file_id="synthetic", session=Mock(), write=True)
        base = DriveHead("1", "a", None, 1)
        with patch.object(tower, "head", return_value=base), patch.object(tower, "upload", return_value=base), patch.object(tower, "read", return_value=({"state_fingerprint":"different"}, base)):
            with self.assertRaises(TowerReadbackMismatch):
                tower.compare_and_swap(base, b'{"state_fingerprint":"expected"}')

    def test_incomplete_listing_is_not_an_empty_queue(self):
        session = Mock()
        session.get.return_value = SimpleNamespace(status_code=200, json=lambda: {"files":[], "incompleteSearch":True})
        with self.assertRaisesRegex(RuntimeError, "INBOX_LIST_INCOMPLETE"):
            DriveInbox(session=session, folder_id="synthetic")._query("synthetic")

    def test_repeated_page_token_terminates_without_infinite_loop(self):
        session = Mock()
        session.get.return_value = SimpleNamespace(status_code=200, json=lambda: {"files":[], "nextPageToken":"same"})
        with self.assertRaisesRegex(RuntimeError, "INBOX_LIST_REPEATED_PAGE_TOKEN"):
            DriveInbox(session=session, folder_id="synthetic")._query("synthetic")
        self.assertEqual(session.get.call_count, 2)

    def test_lock_is_released_on_error(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {"NEXO_HOME":folder}):
            with self.assertRaisesRegex(RuntimeError, "isolated"):
                with writer_lock():
                    raise RuntimeError("isolated")
            self.assertFalse((Path(folder) / "tower.lock").exists())
            with writer_lock():
                self.assertTrue((Path(folder) / "tower.lock").exists())
            self.assertFalse((Path(folder) / "tower.lock").exists())

    def test_busy_lock_does_not_take_over_existing_owner(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {"NEXO_HOME":folder}):
            with writer_lock():
                with self.assertRaises(TowerConflict):
                    with writer_lock():
                        self.fail("must not acquire another owner's lock")
                self.assertTrue((Path(folder) / "tower.lock").exists())

    def test_applied_receipt_is_replayed_without_applying_again(self):
        self._replay("APPLIED", "ALREADY_APPLIED")

    def test_terminal_rejection_is_not_retried_under_same_identity(self):
        self._replay("REJECTED_TERMINAL", "REJECTED_TERMINAL")

    def _replay(self, previous_outcome, expected_outcome):
        request = {"document":"contracts/synthetic.json", "merge":{"synthetic":True}, "request_id":"REQ-SYNTHETIC"}
        intent = "synthetic-stable-intent"
        effect = operation_receipts.effect_id(request, intent=intent, index=0)
        digest = operation_receipts.payload_hash(request, trusted_transport=True)
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            receipt = operation_receipts.build_receipt(intent=intent, payload_sha256=digest, effect=effect,
                outcome=previous_outcome, source_revision="sha256:"+"1"*64, result_revision="sha256:"+"2"*64)
            operation_receipts.persist_receipt(root, receipt)
            result = gpt_writer._existing_effect(root, intent=intent, request=request, payload={},
                request_index=0, source_revision="sha256:"+"3"*64, supersedes=None)
            self.assertEqual(result["outcome"], expected_outcome)
            self.assertFalse((root/"contracts/synthetic.json").exists())


if __name__ == "__main__":
    main()
