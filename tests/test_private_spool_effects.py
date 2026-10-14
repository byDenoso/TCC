"""Synthetic private ingress: the receipt must describe the intended board effect."""
import json
import base64
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from runtime.nexo_agent_api.gpt_writer import apply_to_tower, _gateway_results, _transport_gateway_report
from runtime.nexo_agent_api.live_tower import build_live_tower_payload, read_live_tower_bytes


class PrivateSpoolEffects(unittest.TestCase):
    def tower(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "CONTROL.json").write_text(json.dumps({"truth_owner": "TOWER_V06@GOOGLE_DRIVE_PRIVATE"}))
            return json.dumps(build_live_tower_payload(root)).encode()

    def item(self):
        return {"kind": "BOARD_POST", "source": "ENGINEER", "created_at": "2026-10-13T00:00:00Z",
                "intent_id": "synthetic-private-spool", "_inbox_source": "SHEET_PRIVATE",
                "_inbox_name": "gw-sheet-fixture", "_inbox_id": "gateway:sheet-fixture",
                "payload": {"to": "GUARDIAO", "text": "Synthetic canary only.", "private": False}}

    def test_applied_has_private_board_effect_and_replay_does_not_duplicate_or_export(self):
        item = self.item()
        packed, report = apply_to_tower(self.tower(), [item])
        self.assertFalse(report["rejected"], report)
        bundle = read_live_tower_bytes(packed)
        [post] = bundle["files"]["evolution/board.json"]["value"]["posts"]
        self.assertTrue(post["private"])
        self.assertEqual(post["text"], item["payload"]["text"])
        self.assertTrue(all(row["visibility"] == "PRIVATE" for row in report["operation_receipts"]))
        self.assertEqual(report["public_operation_receipts"], [])
        replay, second = apply_to_tower(packed, [item])
        self.assertIsNone(replay)
        self.assertEqual({row["outcome"] for row in second["operation_receipts"]}, {"ALREADY_APPLIED"})
        self.assertEqual(_gateway_results(second, ["sheet-fixture"])[0]["items"], [])

    def test_oversized_private_board_post_is_rejected_before_applied_receipt(self):
        item = self.item()
        item["payload"] = {**item["payload"], "text": "x" * 501}
        packed, report = apply_to_tower(self.tower(), [item])
        self.assertFalse(report["applied"], report)
        self.assertEqual(report["rejected"][0]["reason"], "BOARD_TEXT_TOO_LONG")
        self.assertEqual({row["outcome"] for row in report["operation_receipts"]}, {"REJECTED_TERMINAL"})
        self.assertNotIn("evolution/board.json", read_live_tower_bytes(packed)["files"])

    def test_ambiguous_or_nested_board_payload_never_becomes_applied_record(self):
        for changes in (
            {"kind": "UNRECOGNIZED", "payload": {"kind": "BOARD_POST", "text": "Canary"}},
            {"kind": "INTEGRITY_REPORT", "payload": {"kind": "BOARD_POST", "text": "Canary"}},
            {"payload": {"kind": "BOARD_POST", "payload": {"to": "GUARDIAO", "text": "Canary"}}},
            {"payload": {"to": "GUARDIAO"}},
            {"kind": None, "payload": {"kind": "BOARD_POST", "to": "GUARDIAO"}},
            {"payload": {"to": "INVALID_ROLE", "text": "Canary"}},
        ):
            with self.subTest(changes=changes):
                packed, report = apply_to_tower(self.tower(), [{**self.item(), **changes}])
                self.assertEqual(len(report["rejected"]), 1, report)
                self.assertFalse(report["applied"], report)
                self.assertEqual({row["outcome"] for row in report["operation_receipts"]}, {"REJECTED_TERMINAL"})
                files = read_live_tower_bytes(packed)["files"]
                self.assertNotIn("evolution/board.json", files)
                self.assertFalse(any(path.startswith("entities/artifact/") for path in files))

    def test_missing_board_readback_rolls_back_effect_before_terminal_receipt(self):
        with patch("runtime.nexo_agent_api.tower_apply.board_effect_readback", return_value=False):
            packed, report = apply_to_tower(self.tower(), [self.item()])
        self.assertFalse(report["applied"], report)
        self.assertEqual(report["rejected"][0]["reason"], "BOARD_EFFECT_READBACK_MISSING")
        self.assertNotIn("evolution/board.json", read_live_tower_bytes(packed)["files"])

    def test_transport_failure_cannot_publish_private_spool_receipt(self):
        entries = [{"id": "sheet-fixture", "source": "SHEET_PRIVATE", "envelope": self.item()}]
        report = _transport_gateway_report(entries, TimeoutError())
        self.assertEqual(report["operation_receipts"], [])
        self.assertEqual(report["public_operation_receipts"], [])

    def test_real_collector_writer_and_next_pulse_reconcile_exact_private_receipt(self):
        companion = Path(__file__).resolve().parents[2] / "Pantheon"
        if not (companion / "scripts/collect_scheduled_spool.py").exists():
            self.skipTest("Companion Pantheon checkout required for cross-repository canary")
        sys.path.append(str(companion))
        from scripts.collect_scheduled_spool import collect
        from runtime.nexo_agent_api import inbox_client, live_tower, operation_receipts
        from unittest.mock import Mock
        reader = SimpleNamespace(read=live_tower.read_live_tower_bytes, verify=live_tower.verify_live_tower,
                                 receipt_index=inbox_client.receipt_index,
                                 payload_hash=operation_receipts.payload_hash, receipt_status=inbox_client.receipt_status)
        envelope = {key: value for key, value in self.item().items() if not key.startswith("_")}
        encoded = base64.urlsafe_b64encode(json.dumps(envelope).encode()).decode().rstrip("=")
        sheet = SimpleNamespace(status_code=200,
                                text="stable_id,role,envelope_b64url\nsched-v1-canary,ENGINEER," + encoded + "\n")
        raw = self.tower()
        session = Mock(get=Mock(side_effect=[SimpleNamespace(status_code=200, content=raw), sheet]))
        first, counts = collect(session, "fixture-spool", {"items": []}, reader)
        self.assertEqual(counts["collected"], 1)
        [entry] = first["items"]
        item = {**entry["envelope"], "_inbox_source": entry["source"],
                "_inbox_name": "gw-" + entry["id"], "_inbox_id": "gateway:" + entry["id"]}
        packed, report = apply_to_tower(raw, [item])
        self.assertFalse(report["rejected"], report)
        session = Mock(get=Mock(side_effect=[SimpleNamespace(status_code=200, content=packed), sheet]))
        second, counts = collect(session, "fixture-spool", {"items": [{"id": "independent"}]}, reader)
        self.assertEqual(second["items"], [{"id": "independent"}])
        self.assertEqual(counts["resolved"], 1)
        post = read_live_tower_bytes(packed)["files"]["evolution/board.json"]["value"]["posts"][0]
        self.assertTrue(post["private"])
        self.assertEqual(_gateway_results(report, [entry["id"]])[0]["items"], [])

    def test_legacy_bundle_without_private_spool_capability_defers_before_source_read(self):
        companion = Path(__file__).resolve().parents[2] / "Pantheon"
        if not (companion / "scripts/collect_scheduled_spool.py").exists():
            self.skipTest("Companion Pantheon checkout required for bundle capability test")
        sys.path.append(str(companion))
        from scripts import collect_scheduled_spool as collector
        from runtime.nexo_agent_api import gpt_writer
        from unittest.mock import Mock
        session = Mock()
        with tempfile.TemporaryDirectory() as tmp:
            gateway = Path(tmp) / "gateway.json"
            original = '{"items":[{"id":"independent"}]}'
            gateway.write_text(original)
            with patch.dict("os.environ", {"NEXO_GATEWAY_ITEMS": str(gateway), "SPOOL_ID": "fixture"}), \
                 patch.object(collector, "authorized_session", return_value=session), \
                 patch.object(collector.runpy, "run_path"), \
                 patch.object(gpt_writer, "PRIVATE_SHEET_SPOOL_CONTRACT", None), \
                 patch("builtins.print") as log:
                self.assertEqual(collector.main(), 0)
            session.get.assert_not_called()
            self.assertEqual(gateway.read_text(), original)
            log.assert_called_once_with('{"sheet_spool": "DEFERRED", "reason": "WRITER_BUNDLE_INCOMPATIBLE"}')

    def test_receipt_index_scans_immutable_private_bundle_once_for_many_queries(self):
        from runtime.nexo_agent_api import inbox_client
        packed, _ = apply_to_tower(self.tower(), [self.item()])
        tower = read_live_tower_bytes(packed)
        prepared = {"intent_id": self.item()["intent_id"],
                    "payload_sha256": inbox_client.payload_hash(self.item(), trusted_transport=True)}
        with patch.object(inbox_client, "_receipt_records", wraps=inbox_client._receipt_records) as scan:
            index = inbox_client.receipt_index(tower)
            for _ in range(10):
                status = inbox_client.receipt_status(tower, prepared, index=index)
                self.assertEqual(status["receipt"]["outcome"], "APPLIED")
            scan.assert_called_once_with(tower)

    def test_existing_delivery_journal_recovers_after_restart_without_duplicate_create(self):
        from runtime.nexo_agent_api import inbox_client
        from runtime.nexo_agent_api.test_inbox_client import Transport
        envelope = {key: value for key, value in self.item().items() if not key.startswith("_")}
        envelope["payload"] = {**envelope["payload"], "private": True}
        prepared = inbox_client.prepare(envelope, runtime_role="ENGINEER", allowed_kinds={"BOARD_POST"})
        raw_tower = self.tower()
        with tempfile.TemporaryDirectory() as tmp:
            journal_path, envelope_path = Path(tmp) / "journal.json", Path(tmp) / "envelope.json"
            envelope_path.write_bytes(prepared["raw"])
            transport = Transport()
            transport.timeout = True
            transport.checkpoint = lambda state: journal_path.write_text(json.dumps(state))
            self.assertEqual(inbox_client.deliver(prepared, transport,
                             tower=read_live_tower_bytes(raw_tower), journal={})["stage"], "OUTCOME_UNKNOWN")
            # A new runtime recreates prepared bytes and reads the checkpoint;
            # only the remote fixture survives, never the first client's state.
            recovered = inbox_client.prepare(json.loads(envelope_path.read_bytes()),
                        runtime_role="ENGINEER", allowed_kinds={"BOARD_POST"})
            resumed = Transport()
            resumed.files = transport.files
            journal = json.loads(journal_path.read_text())
            self.assertEqual(recovered, prepared)
            delivered = inbox_client.deliver(recovered, resumed,
                        tower=read_live_tower_bytes(raw_tower), journal=journal)
            self.assertEqual(delivered["stage"], "DELIVERED")
            self.assertEqual((transport.calls, resumed.calls), (1, 0))
            packed, report = apply_to_tower(raw_tower, [{**envelope, "_inbox_source": "DRIVE",
                "_inbox_id": "FILE", "_inbox_name": recovered["filename"]}])
            self.assertFalse(report["rejected"], report)
            applied = inbox_client.deliver(recovered, resumed,
                      tower=read_live_tower_bytes(packed), journal=journal)
            self.assertEqual(applied["stage"], "APPLIED")
            self.assertEqual(resumed.calls, 0)


if __name__ == "__main__":
    unittest.main()
