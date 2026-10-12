"""Route-specific, fixture-only coverage for the single Writer ingress protocol.

These tests never create a real Drive session or contact GitHub. Route grants
are synthetic policy inputs, not evidence that any live route is enabled.
"""
from __future__ import annotations

import copy
import base64
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from runtime.nexo_agent_api.drive_transport import TowerConflict, TowerTransportError
from runtime.nexo_agent_api import operation_receipts
from runtime.nexo_agent_api.gpt_writer import apply_to_tower
from runtime.nexo_agent_api.live_tower import build_live_tower_payload, verify_live_tower
from runtime.nexo_agent_api.transport_adapters import (
    DriveInboxAdapter,
    GatewayVerifiedFeedAdapter,
    GitHubStagingAdapter,
    RouteGrant,
    SheetSpoolAdapter,
    retry_disposition,
)


STAMP = "2026-10-11T12:00:00Z"
BOARD = {
    "kind": "BOARD_POST",
    "source": "ENGINEER",
    "created_at": STAMP,
    "payload": {"to": "GUARDIAO", "text": "fixture only"},
}
PUBLIC_STATUS = {
    "kind": "INTEGRITY_REPORT",
    "source": "ENGINEER",
    "created_at": STAMP,
    "payload": {
        "date": "2026-10-11",
        "status": "GREEN",
        "checks": [{"area": "contract", "ok": True, "detail": "synthetic fixture"}],
    },
}


def grant(route: str, *, role: str = "ENGINEER", **changes) -> RouteGrant:
    fields = {
        "route": route,
        "principal": "fixture-principal",
        "runtime_role": role,
        "policy_revision": "fixture-policy-only",
        "enabled": True,
        "state": "ACTIVE",
        "allowed_kinds": frozenset({"BOARD_POST"}),
    }
    fields.update(changes)
    return RouteGrant(**fields)


def writer_receipt(identity: str, outcome: str = "APPLIED", item: dict | None = None) -> dict:
    payload = item or {"intent_id": identity}
    return operation_receipts.build_receipt(
        intent=identity,
        payload_sha256=operation_receipts.payload_hash(payload, trusted_transport=True),
        effect=operation_receipts.envelope_effect_id(identity),
        outcome=outcome,
        source_revision="sha256:" + "1" * 64,
        result_revision="sha256:" + "2" * 64,
        visibility="PUBLIC" if identity.startswith("gateway:") else "PRIVATE",
        occurred_at=STAMP,
        observed_at=STAMP,
    )


class FakeDriveDelivery:
    can_write = True

    def __init__(self):
        self.files = {}
        self.creates = 0
        self.checkpoints = []

    def checkpoint(self, journal):
        self.checkpoints.append(copy.deepcopy(journal))

    def lookup(self, filename, inbox):
        return [file_id for file_id, row in self.files.items() if row["filename"] == filename]

    def create(self, raw, filename, inbox):
        self.creates += 1
        self.files["fixture-file"] = {
            "raw": raw,
            "filename": filename,
            "mime_type": "application/json",
            "parent_ids": [inbox],
        }
        return "fixture-file"

    def read(self, file_id):
        return self.files[file_id]


class FakeSheetAckStore:
    def __init__(self, version="ack-v1"):
        self.version = version
        self.rows = {}
        self.writes = []

    def compare_and_swap(self, *, stable_id, expected_version, receipt_id):
        if expected_version != self.version:
            return {"accepted": False, "conflict": True}
        self.version = "ack-v2"
        self.rows[stable_id] = {"receipt_id": receipt_id, "version": self.version}
        self.writes.append((stable_id, expected_version, receipt_id))
        return {"accepted": True, "version": self.version}

    def read(self, stable_id):
        row = self.rows.get(stable_id)
        if row is None:
            return None
        return {"stable_id": stable_id, **row}


def sheet_row(stable_id: str, envelope: dict) -> str:
    raw = json.dumps(envelope, separators=(",", ":")).encode("utf-8")
    encoded = base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")
    return f"{stable_id},{encoded}"


def collect_sheet(adapter: SheetSpoolAdapter, csv_export: bytes | str, **kwargs) -> list[dict]:
    raw = csv_export if isinstance(csv_export, bytes) else csv_export.encode("utf-8")
    return adapter.collect(csv_export, verified=True,
                           expected_sha256=hashlib.sha256(raw).hexdigest(), **kwargs)


class RouteAdapterTests(unittest.TestCase):
    def test_all_routes_fail_closed_before_reading_without_explicit_grant(self):
        drive = Mock()
        github = Mock()
        sheet = SheetSpoolAdapter()

        with self.assertRaisesRegex(PermissionError, "INGRESS_ROUTE_NOT_AUTHORIZED"):
            DriveInboxAdapter(inbox=drive).collect()
        with self.assertRaisesRegex(PermissionError, "INGRESS_ROUTE_NOT_AUTHORIZED"):
            GatewayVerifiedFeedAdapter().collect({"items": []}, verified=True)
        with self.assertRaisesRegex(PermissionError, "INGRESS_ROUTE_NOT_AUTHORIZED"):
            GitHubStagingAdapter(client=github).collect()
        with self.assertRaisesRegex(PermissionError, "INGRESS_ROUTE_NOT_AUTHORIZED"):
            sheet.collect("stable_id,envelope_b64url\n", verified=True)

        drive.pending.assert_not_called()
        github.pending.assert_not_called()

    def test_gateway_feed_requires_verifier_boundary_and_binds_role(self):
        adapter = GatewayVerifiedFeedAdapter(grant=grant(
            "gateway", public_sanitized=True,
            allowed_kinds=frozenset({"INTEGRITY_REPORT"}),
        ))
        feed = {"items": [{"id": "synthetic-1", "envelope": PUBLIC_STATUS}]}

        with self.assertRaisesRegex(PermissionError, "VERIFIED_GATEWAY_FEED_REQUIRED"):
            adapter.collect(feed, verified=False)

        changed_role = {"items": [{"id": "synthetic-1", "envelope": {
            **PUBLIC_STATUS, "source": "DENER",
        }}]}
        with self.assertRaisesRegex(PermissionError, "RUNTIME_ROLE_NOT_AUTHORIZED"):
            adapter.collect(changed_role, verified=True)

        items = adapter.collect(feed, verified=True)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["_inbox_source"], "GATEWAY")
        self.assertEqual(items[0]["_inbox_id"], "gateway:synthetic-1")
        self.assertEqual(items[0]["intent_id"], "gateway:synthetic-1")
        self.assertEqual(items[0]["source"], "ENGINEER")

    def test_gateway_requires_public_sanitization_and_rejects_private_kinds_recursively(self):
        feed = {"items": [{"id": "public", "envelope": PUBLIC_STATUS}]}
        not_sanitized = GatewayVerifiedFeedAdapter(grant=grant(
            "gateway", allowed_kinds=frozenset({"INTEGRITY_REPORT"}),
        ))
        with self.assertRaisesRegex(PermissionError, "SANITIZED_PUBLIC_PAYLOAD_REQUIRED"):
            not_sanitized.collect(feed, verified=True)

        private_grant = grant("gateway", public_sanitized=True,
                              allowed_kinds=frozenset({"BATCH", "BOARD_POST", "HANDOFF"}))
        adapter = GatewayVerifiedFeedAdapter(grant=private_grant)
        handoff = {**BOARD, "kind": "HANDOFF", "payload": {
            "from_role": "ENGINEER", "to_role": "EXECUTOR", "id": "fixture-private",
        }}
        for label, envelope in (("board", BOARD), ("handoff", handoff)):
            with self.subTest(location="direct", kind=label):
                with self.assertRaisesRegex(PermissionError, "PRIVATE_EVENT_REQUIRES_DRIVE"):
                    adapter.collect({"items": [{"id": "direct-" + label,
                                                 "envelope": envelope}]}, verified=True)

        nested_private = (
            ("board", {"items": [BOARD]}),
            ("handoff", {"items": [{
                "kind": "BATCH", "source": "ENGINEER", "created_at": STAMP,
                "payload": {"items": [handoff]},
            }]}),
        )
        for label, children in nested_private:
            with self.subTest(location="batch", kind=label):
                envelope = {
                    "kind": "BATCH", "source": "ENGINEER", "created_at": STAMP,
                    "payload": children,
                }
                with self.assertRaisesRegex(PermissionError, "PRIVATE_EVENT_REQUIRES_DRIVE"):
                    adapter.collect({"items": [{"id": "nested-" + label,
                                                 "envelope": envelope}]}, verified=True)

    def test_gateway_batch_child_id_namespace_is_reserved_without_rewriting_writer_ids(self):
        adapter = GatewayVerifiedFeedAdapter(grant=grant(
            "gateway", public_sanitized=True,
            allowed_kinds=frozenset({"BATCH", "INTEGRITY_REPORT"}),
        ))
        batch = {
            "kind": "BATCH", "source": "ENGINEER", "created_at": STAMP,
            "payload": {"items": [PUBLIC_STATUS, PUBLIC_STATUS]},
        }
        valid = adapter.collect({"items": [{"id": "batch", "envelope": batch}]},
                                verified=True)
        self.assertEqual([child["intent_id"] for child in valid[0]["payload"]["items"]],
                         ["gateway:batch.batch-0", "gateway:batch.batch-1"])

        collision = {"items": [
            {"id": "batch", "envelope": {**batch, "payload": {"items": [PUBLIC_STATUS]}}},
            {"id": "batch.batch-0", "envelope": PUBLIC_STATUS},
        ]}
        with self.assertRaisesRegex(ValueError, "AMBIGUOUS_BATCH_CHILD_ID"):
            adapter.collect(collision, verified=True)

    def test_gateway_reserves_sheet_namespace_and_preserves_sheet_identity(self):
        gateway = GatewayVerifiedFeedAdapter(grant=grant(
            "gateway", public_sanitized=True,
            allowed_kinds=frozenset({"INTEGRITY_REPORT"}),
        ))
        with self.assertRaisesRegex(ValueError, "GATEWAY_ID_RESERVED_FOR_SHEET"):
            gateway.collect({"items": [{"id": "sheet-good", "envelope": PUBLIC_STATUS}]},
                            verified=True)

        sheet_export = "stable_id,envelope_b64url\n" + sheet_row("good", PUBLIC_STATUS) + "\n"
        [sheet_item] = collect_sheet(SheetSpoolAdapter(grant=grant(
            "sheet_spool", public_sanitized=True,
            allowed_kinds=frozenset({"INTEGRITY_REPORT"}),
        )), sheet_export)
        self.assertEqual(sheet_item["intent_id"], "gateway:sheet-good")

    def test_drive_batch_child_id_collision_is_detected_without_rewriting_legacy_id(self):
        adapter = DriveInboxAdapter(grant=grant(
            "drive", allowed_kinds=frozenset({"BATCH", "INTEGRITY_REPORT"}),
        ))
        batch = {
            "kind": "BATCH", "source": "ENGINEER", "created_at": STAMP,
            "intent_id": "legacy",
            "payload": {"items": [PUBLIC_STATUS, PUBLIC_STATUS]},
        }
        valid = adapter.collect([{
            "id": "parent-file", "name": "batch.json", "payload": batch,
        }])
        self.assertEqual([child["intent_id"] for child in valid[0]["payload"]["items"]],
                         ["legacy.batch-0", "legacy.batch-1"])

        sibling = {**PUBLIC_STATUS, "intent_id": "legacy.batch-0",
                   "payload": {**PUBLIC_STATUS["payload"], "status": "RED"}}
        with self.assertRaisesRegex(ValueError, "AMBIGUOUS_BATCH_CHILD_ID"):
            adapter.collect([
                {"id": "parent-file", "name": "batch.json", "payload": {
                    **batch, "payload": {"items": [PUBLIC_STATUS]},
                }},
                {"id": "sibling-file", "name": "sibling.json", "payload": sibling},
            ])

        legacy = adapter.collect([{
            "id": "legacy-file", "name": "legacy.json",
            "payload": {**PUBLIC_STATUS, "intent_id": "legacy.batch-0"},
        }])
        self.assertEqual(legacy[0]["intent_id"], "legacy.batch-0")

        root_batch = {key: value for key, value in batch.items() if key != "intent_id"}
        with self.assertRaisesRegex(ValueError, "AMBIGUOUS_BATCH_CHILD_ID"):
            adapter.collect([
                {"id": "root", "name": "batch.json", "payload": root_batch},
                {"id": "sibling", "name": "sibling.json", "payload": {
                    **PUBLIC_STATUS, "intent_id": "drive:root.batch-0",
                    "payload": {**PUBLIC_STATUS["payload"], "status": "RED"},
                }},
            ])

    def test_drive_nested_batch_collision_is_detected(self):
        adapter = DriveInboxAdapter(grant=grant(
            "drive", allowed_kinds=frozenset({"BATCH", "INTEGRITY_REPORT"}),
        ))
        nested = {
            "kind": "BATCH", "source": "ENGINEER", "created_at": STAMP,
            "payload": {"items": [PUBLIC_STATUS]},
        }
        outer = {
            "kind": "BATCH", "source": "ENGINEER", "created_at": STAMP,
            "intent_id": "nested", "payload": {"items": [nested]},
        }
        sibling = {**PUBLIC_STATUS, "intent_id": "nested.batch-0.batch-0",
                   "payload": {**PUBLIC_STATUS["payload"], "status": "RED"}}
        with self.assertRaisesRegex(ValueError, "AMBIGUOUS_BATCH_CHILD_ID"):
            adapter.collect([
                {"id": "nested-file", "name": "nested.json", "payload": outer},
                {"id": "sibling-file", "name": "sibling.json", "payload": sibling},
            ])

    def test_drive_identical_batch_replay_is_idempotent_but_identity_conflict_fails(self):
        adapter = DriveInboxAdapter(grant=grant(
            "drive", allowed_kinds=frozenset({"BATCH", "INTEGRITY_REPORT"}),
        ))
        batch = {
            "kind": "BATCH", "source": "ENGINEER", "created_at": STAMP,
            "intent_id": "replayed-batch", "payload": {"items": [PUBLIC_STATUS]},
        }
        replay = adapter.collect([
            {"id": "replay-a", "name": "batch-a.json", "payload": batch},
            {"id": "replay-b", "name": "batch-b.json", "payload": batch},
        ])
        self.assertEqual(len(replay), 2)
        self.assertEqual(replay[0]["payload"], replay[1]["payload"])

        identical_child_replay = adapter.collect([
            {"id": "child-parent", "name": "parent.json", "payload": batch},
            {"id": "child-replay", "name": "child.json", "payload": {
                **PUBLIC_STATUS, "intent_id": "replayed-batch.batch-0",
            }},
        ])
        self.assertEqual(len(identical_child_replay), 2)
        self.assertEqual(identical_child_replay[0]["payload"]["items"][0]["intent_id"],
                         identical_child_replay[1]["intent_id"])

        original = {**PUBLIC_STATUS, "intent_id": "replayed-batch"}
        conflicting = {**original,
                       "payload": {**PUBLIC_STATUS["payload"], "status": "RED"}}
        with self.assertRaisesRegex(ValueError, "AMBIGUOUS_BATCH_CHILD_ID"):
            adapter.collect([
                {"id": "same-a", "name": "same-a.json", "payload": original},
                {"id": "same-b", "name": "same-b.json", "payload": conflicting},
            ])

    def test_github_staging_requires_explicit_public_sanitization_grant(self):
        client = Mock()
        client.pending.return_value = [{
            "name": "fixture.json",
            "path": "inbox/fixture.json",
            "payload": BOARD,
        }]
        retired = grant("github", enabled=False, state="RETIRED")
        with self.assertRaisesRegex(PermissionError, "INGRESS_ROUTE_NOT_AUTHORIZED"):
            GitHubStagingAdapter(client=client, grant=retired).collect()
        client.pending.assert_not_called()

        not_sanitized = grant("github")
        with self.assertRaisesRegex(PermissionError, "SANITIZED_PUBLIC_PAYLOAD_REQUIRED"):
            GitHubStagingAdapter(client=client, grant=not_sanitized).collect()
        client.pending.assert_not_called()

        public_fixture = grant("github", public_sanitized=True)
        with self.assertRaisesRegex(PermissionError, "PRIVATE_EVENT_REQUIRES_DRIVE"):
            GitHubStagingAdapter(client=client, grant=public_fixture).collect()

        client.pending.return_value = [{
            "name": "fixture.json",
            "path": "inbox/fixture.json",
            "payload": PUBLIC_STATUS,
        }]
        public_fixture = grant("github", public_sanitized=True,
                               allowed_kinds=frozenset({"INTEGRITY_REPORT"}))
        items = GitHubStagingAdapter(client=client, grant=public_fixture).collect()
        self.assertEqual(items[0]["_inbox_source"], "GITHUB")
        self.assertEqual(items[0]["_inbox_id"], "github:inbox/fixture.json")
        self.assertEqual(items[0]["intent_id"], "github:inbox/fixture.json")
        self.assertEqual(client.pending.call_count, 2)

    def test_sheet_spool_uses_csv_contract_and_requires_verified_public_export(self):
        adapter = SheetSpoolAdapter(grant=grant(
            "sheet_spool", public_sanitized=True,
            allowed_kinds=frozenset({"INTEGRITY_REPORT"}),
        ))
        csv_export = "stable_id,envelope_b64url\n" + sheet_row("status-001", PUBLIC_STATUS) + "\n"

        with self.assertRaisesRegex(PermissionError, "VERIFIED_SHEET_EXPORT_REQUIRED"):
            adapter.collect(csv_export, verified=False)
        with self.assertRaisesRegex(ValueError, "SHEET_EXPORT_REVISION_REQUIRED"):
            adapter.collect(csv_export, verified=True)
        with self.assertRaisesRegex(ValueError, "SHEET_EXPORT_READBACK_MISMATCH"):
            adapter.collect(csv_export, verified=True, expected_sha256="0" * 64)

        items = collect_sheet(adapter, csv_export.encode("utf-8"))
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["_inbox_source"], "GATEWAY")
        self.assertEqual(items[0]["_inbox_id"], "gateway:sheet-status-001")
        self.assertEqual(items[0]["intent_id"], "gateway:sheet-status-001")
        self.assertEqual(items[0]["kind"], "INTEGRITY_REPORT")
        self.assertEqual(collect_sheet(adapter, csv_export +
                                       sheet_row("other-status", PUBLIC_STATUS) + "\n")[0], items[0])
        self.assertEqual(collect_sheet(adapter, csv_export, acknowledged={"status-001"}), [])

        private = "stable_id,envelope_b64url\n" + sheet_row("private-001", BOARD) + "\n"
        private_adapter = SheetSpoolAdapter(grant=grant(
            "sheet_spool", public_sanitized=True,
            allowed_kinds=frozenset({"BOARD_POST", "INTEGRITY_REPORT"}),
        ))
        with self.assertRaisesRegex(PermissionError, "PRIVATE_EVENT_REQUIRES_DRIVE"):
            collect_sheet(private_adapter, private)
        duplicate = csv_export + sheet_row("status-001", PUBLIC_STATUS) + "\n"
        with self.assertRaisesRegex(ValueError, "SHEET_SPOOL_DUPLICATE_STABLE_ID"):
            collect_sheet(adapter, duplicate)

    def test_sheet_ack_requires_cas_readback_and_matching_writer_receipt(self):
        store = FakeSheetAckStore()
        adapter = SheetSpoolAdapter(grant=grant(
            "sheet_spool", public_sanitized=True,
            allowed_kinds=frozenset({"INTEGRITY_REPORT"}),
        ), ack_store=store)
        csv_export = "stable_id,envelope_b64url\n" + sheet_row("status-001", PUBLIC_STATUS) + "\n"
        [item] = collect_sheet(adapter, csv_export)
        receipt = writer_receipt(item["intent_id"], item=item)

        wrong_sibling = {**item, "_inbox_id": "gateway:sheet-victim"}
        with self.assertRaisesRegex(ValueError, "SHEET_ACK_IDENTITY_MISMATCH"):
            adapter.acknowledge(wrong_sibling, receipt, expected_version="ack-v1")
        wrong_source = {**item, "_inbox_source": "DRIVE"}
        with self.assertRaisesRegex(ValueError, "SHEET_ACK_SOURCE_MISMATCH"):
            adapter.acknowledge(wrong_source, receipt, expected_version="ack-v1")
        self.assertEqual(store.writes, [])

        with self.assertRaisesRegex(ValueError, "SHEET_ACK_EXPECTED_VERSION_REQUIRED"):
            adapter.acknowledge(item, receipt, expected_version="")
        with self.assertRaisesRegex(ValueError, "WRITER_RECEIPT_IDENTITY_MISMATCH"):
            adapter.acknowledge(item, writer_receipt("another"), expected_version="ack-v1")
        no_effect = writer_receipt(item["intent_id"], item=item)
        no_effect["effect_id"] = "effect-" + "b" * 32
        with self.assertRaisesRegex(ValueError, "WRITER_READBACK_RECEIPT_REQUIRED"):
            adapter.acknowledge(item, no_effect, expected_version="ack-v1")
        mismatched_payload = writer_receipt(item["intent_id"], item={
            **item, "payload": {**item["payload"], "status": "AMBER"},
        })
        with self.assertRaisesRegex(ValueError, "WRITER_RECEIPT_PAYLOAD_MISMATCH"):
            adapter.acknowledge(item, mismatched_payload, expected_version="ack-v1")
        self.assertEqual(store.writes, [])

        acknowledged = adapter.acknowledge(item, receipt, expected_version="ack-v1")
        self.assertEqual(acknowledged, {
            "stable_id": "status-001", "receipt_id": receipt["receipt_id"], "version": "ack-v2",
        })
        with self.assertRaisesRegex(TowerConflict, "SHEET_ACK_VERSION_CONFLICT"):
            adapter.acknowledge(item, receipt, expected_version="ack-v1")
        self.assertEqual(len(store.writes), 1)

        no_readback = Mock()
        no_readback.compare_and_swap.return_value = {"accepted": True, "version": "ack-v3"}
        no_readback.read.return_value = None
        adapter_without_readback = SheetSpoolAdapter(grant=adapter.grant, ack_store=no_readback)
        with self.assertRaisesRegex(RuntimeError, "SHEET_ACK_READBACK_REQUIRED"):
            adapter_without_readback.acknowledge(item, receipt, expected_version="ack-v2")

    def test_three_additional_routes_have_distinct_stable_idempotency_keys(self):
        kinds = frozenset({"INTEGRITY_REPORT"})
        drive = DriveInboxAdapter(grant=grant("drive", allowed_kinds=kinds)).collect([{
            "id": "drive-file-1", "name": "fixture.json", "payload": PUBLIC_STATUS,
        }])
        gateway = GatewayVerifiedFeedAdapter(grant=grant(
            "gateway", public_sanitized=True, allowed_kinds=kinds,
        )).collect(
            {"items": [{"id": "shared-fixture", "envelope": PUBLIC_STATUS}]}, verified=True)
        sheet_export = "stable_id,envelope_b64url\n" + sheet_row("spool-fixture", PUBLIC_STATUS) + "\n"
        sheet = collect_sheet(SheetSpoolAdapter(grant=grant(
            "sheet_spool", public_sanitized=True, allowed_kinds=kinds,
        )), sheet_export)
        github = GitHubStagingAdapter(
            grant=grant("github", public_sanitized=True, allowed_kinds=kinds),
        ).collect([{
            "name": "fixture.json", "path": "inbox/fixture.json", "payload": PUBLIC_STATUS,
        }])

        identities = [drive[0]["intent_id"], gateway[0]["intent_id"],
                      sheet[0]["intent_id"], github[0]["intent_id"]]
        self.assertEqual(len(set(identities)), 4)
        self.assertEqual([item["_inbox_source"] for item in
                          (drive[0], gateway[0], sheet[0], github[0])],
                         ["DRIVE", "GATEWAY", "GATEWAY", "GITHUB"])

    def test_three_additional_route_fixtures_share_one_writer_and_receipt_ledger(self):
        kinds = frozenset({"INTEGRITY_REPORT"})
        drive = DriveInboxAdapter(grant=grant("drive", allowed_kinds=kinds)).collect([{
            "id": "fixture-drive-file", "name": "drive.json",
            "payload": {**PUBLIC_STATUS, "payload": {**PUBLIC_STATUS["payload"], "date": "2026-10-08"}},
        }])
        gateway = GatewayVerifiedFeedAdapter(grant=grant(
            "gateway", public_sanitized=True, allowed_kinds=kinds,
        )).collect(
            {"items": [{"id": "fixture-gateway", "envelope": {
                **PUBLIC_STATUS, "payload": {**PUBLIC_STATUS["payload"], "date": "2026-10-09"},
            }}]}, verified=True)
        sheet_export = "stable_id,envelope_b64url\n" + sheet_row("fixture-sheet", {
            **PUBLIC_STATUS, "payload": {**PUBLIC_STATUS["payload"], "date": "2026-10-10"},
        }) + "\n"
        sheet = collect_sheet(SheetSpoolAdapter(grant=grant(
            "sheet_spool", public_sanitized=True, allowed_kinds=kinds,
        )), sheet_export)
        github = GitHubStagingAdapter(grant=grant(
            "github", public_sanitized=True, allowed_kinds=kinds)).collect([{
                "name": "github.json", "path": "inbox/github.json",
                "payload": {**PUBLIC_STATUS, "payload": {**PUBLIC_STATUS["payload"], "date": "2026-10-11"}},
            }])
        items = drive + gateway + sheet + github

        with tempfile.TemporaryDirectory(prefix="nexo-transport-fixture-") as temporary:
            root = Path(temporary)
            (root / "CONTROL.json").write_text(json.dumps({
                "truth_owner": "TOWER_V06@GOOGLE_DRIVE_PRIVATE",
            }), encoding="utf-8")
            raw = json.dumps(build_live_tower_payload(root)).encode("utf-8")
            written, report = apply_to_tower(raw, items)

        self.assertIsNotNone(written)
        self.assertFalse(report["rejected"], report)
        receipts = report["operation_receipts"]
        identities = {row["intent_id"] for row in receipts}
        self.assertEqual(identities, {
            drive[0]["intent_id"], gateway[0]["intent_id"],
            sheet[0]["intent_id"], github[0]["intent_id"],
        })
        self.assertTrue(all(row["source_revision"].startswith("sha256:")
                            and row["result_revision"].startswith("sha256:") for row in receipts))
        self.assertTrue(verify_live_tower(json.loads(written)))

        replay, replay_report = apply_to_tower(written, items)
        self.assertIsNone(replay)
        self.assertFalse(replay_report["rejected"], replay_report)
        self.assertEqual({row["outcome"] for row in replay_report["operation_receipts"]}, {"ALREADY_APPLIED"})

    def test_drive_delivery_preserves_identity_and_requires_readback_and_journal(self):
        adapter = DriveInboxAdapter(grant=grant("drive", role="CHATGPT"))
        transport = FakeDriveDelivery()
        envelope = {
            "kind": "BOARD_POST",
            "source": "CHATGPT",
            "intent_id": "fixture-drive-intent",
            "created_at": STAMP,
            "payload": {"to": "DENER", "text": "fixture only"},
        }
        prepared = adapter.prepare(envelope)
        journal = {}

        self.assertEqual(adapter.receipt_status(
            {"files": {}, "revision": "fixture-revision"}, prepared)["stage"], "UNOBSERVED")
        result = adapter.submit(envelope, transport, tower={"files": {}, "revision": "fixture-revision"},
                                journal=journal)
        self.assertEqual(result["stage"], "DELIVERED")
        self.assertEqual(result["intent_id"], "fixture-drive-intent")
        self.assertEqual(json.loads(transport.files["fixture-file"]["raw"]), envelope)
        self.assertEqual(transport.creates, 1)

        repeated = adapter.submit(envelope, transport, tower={"files": {}, "revision": "fixture-revision"},
                                  journal=journal)
        self.assertEqual(repeated["stage"], "DELIVERED")
        self.assertEqual(transport.creates, 1)
        # A Drive readback proves delivery only; the Writer ledger remains the
        # authority for application.
        self.assertEqual(adapter.receipt_status(
            {"files": {}, "revision": "fixture-revision"}, prepared)["stage"], "UNOBSERVED")

    def test_drive_inbox_ack_waits_for_matching_terminal_receipt(self):
        inbox = Mock()
        adapter = DriveInboxAdapter(grant=grant("drive"), inbox=inbox)
        item = {
            **BOARD,
            "intent_id": "drive:fixture-intent",
            "_inbox_source": "DRIVE",
            "_inbox_name": "fixture.json",
            "_inbox_id": "fixture-file",
        }
        with self.assertRaisesRegex(ValueError, "WRITER_TERMINAL_RECEIPT_REQUIRED"):
            adapter.acknowledge(item, None)
        with self.assertRaisesRegex(ValueError, "WRITER_RECEIPT_IDENTITY_MISMATCH"):
            adapter.acknowledge(item, {"intent_id": "other", "outcome": "APPLIED"})
        with self.assertRaisesRegex(ValueError, "WRITER_RECEIPT_INVALID"):
            adapter.acknowledge(item, {"intent_id": "drive:fixture-intent", "outcome": "APPLIED"})
        inbox.mark_processed.assert_not_called()

        adapter.acknowledge(item, writer_receipt(
            "drive:fixture-intent", "ALREADY_APPLIED", item=item))
        inbox.mark_processed.assert_called_once_with("fixture-file")

    def test_drive_rejects_foreign_route_intents_without_fallback(self):
        adapter = DriveInboxAdapter(grant=grant(
            "drive", allowed_kinds=frozenset({"INTEGRITY_REPORT"}),
        ))
        for foreign_id in ("gateway:shared", "github:inbox/shared.json",
                           "runner:receipt-fixture"):
            with self.subTest(foreign_id=foreign_id):
                entry = {"id": "drive-file", "name": "fixture.json",
                         "payload": {**PUBLIC_STATUS, "intent_id": foreign_id}}
                with self.assertRaisesRegex(ValueError, "DRIVE_FOREIGN_ROUTE_INTENT_ID"):
                    adapter.collect([entry])
                with self.assertRaisesRegex(ValueError, "DRIVE_FOREIGN_ROUTE_INTENT_ID"):
                    adapter.prepare({**PUBLIC_STATUS, "intent_id": foreign_id})

        gateway = GatewayVerifiedFeedAdapter(grant=grant(
            "gateway", public_sanitized=True,
            allowed_kinds=frozenset({"INTEGRITY_REPORT"}),
        )).collect({"items": [{"id": "shared", "envelope": PUBLIC_STATUS}]}, verified=True)
        self.assertEqual(gateway[0]["intent_id"], "gateway:shared")

        legacy = adapter.collect([{
            "id": "drive-file", "name": "fixture.json",
            "payload": {**PUBLIC_STATUS, "intent_id": "legacy-drive-id"},
        }])
        legacy_batch_suffix = adapter.collect([{
            "id": "drive-file", "name": "fixture.json",
            "payload": {**PUBLIC_STATUS, "intent_id": "legacy.batch-0"},
        }])
        owned = adapter.collect([{
            "id": "drive-file", "name": "fixture.json",
            "payload": {**PUBLIC_STATUS, "intent_id": "drive:owned-id"},
        }])
        self.assertEqual(legacy[0]["intent_id"], "legacy-drive-id")
        self.assertEqual(legacy_batch_suffix[0]["intent_id"], "legacy.batch-0")
        self.assertEqual(owned[0]["intent_id"], "drive:owned-id")

    def test_authorization_refusal_never_becomes_cross_route_fallback(self):
        denied = TowerTransportError("UPLOAD", 403, "OPERATOR_REAUTHORIZATION")
        recoverable = TowerTransportError("UPLOAD", 503, "AFTER_TRANSPORT_RECOVERY")

        self.assertEqual(retry_disposition(denied), "STOP_AUTHORIZATION")
        self.assertEqual(retry_disposition(PermissionError("ACL")), "STOP_AUTHORIZATION")
        self.assertEqual(retry_disposition(recoverable), "RECONCILE_SAME_ROUTE")
        self.assertEqual(retry_disposition(TimeoutError()), "RECONCILE_SAME_ROUTE")
        self.assertEqual(retry_disposition(ValueError("contract")), "STOP")

    def test_staging_ack_requires_a_terminal_writer_receipt(self):
        client = Mock()
        client.read_pending_fresh.return_value = []
        adapter = GitHubStagingAdapter(client=client, grant=grant(
            "github", public_sanitized=True,
            allowed_kinds=frozenset({"INTEGRITY_REPORT"}),
        ))
        entry = {"name": "fixture.json", "path": "inbox/fixture.json", "payload": PUBLIC_STATUS}
        normalized = {**PUBLIC_STATUS, "intent_id": "github:inbox/fixture.json"}

        with self.assertRaisesRegex(ValueError, "WRITER_TERMINAL_RECEIPT_REQUIRED"):
            adapter.acknowledge(entry, None)
        with self.assertRaisesRegex(ValueError, "WRITER_TERMINAL_RECEIPT_REQUIRED"):
            adapter.acknowledge(entry, {"intent_id": "github:inbox/fixture.json", "outcome": "DEFERRED_DEPENDENCY"})
        client.mark_processed.assert_not_called()

        adapter.acknowledge(entry, writer_receipt(
            "github:inbox/fixture.json", item=normalized))
        client.mark_processed.assert_called_once_with(entry)
        client.read_pending_fresh.assert_called_once_with()

    def test_staging_ack_does_not_claim_success_without_pending_readback(self):
        client = Mock()
        entry = {"name": "fixture.json", "path": "inbox/fixture.json", "payload": PUBLIC_STATUS}
        client.read_pending_fresh.return_value = [entry]
        adapter = GitHubStagingAdapter(client=client, grant=grant(
            "github", public_sanitized=True,
            allowed_kinds=frozenset({"INTEGRITY_REPORT"}),
        ))
        normalized = {**PUBLIC_STATUS, "intent_id": "github:inbox/fixture.json"}

        with self.assertRaisesRegex(RuntimeError, "GITHUB_STAGING_ACK_READBACK_REQUIRED"):
            adapter.acknowledge(entry, writer_receipt(
                "github:inbox/fixture.json", item=normalized))
        client.mark_processed.assert_called_once_with(entry)

    def test_staging_client_without_fresh_readback_cannot_ack(self):
        client = Mock()
        client.read_pending_fresh = None
        entry = {"name": "fixture.json", "path": "inbox/fixture.json", "payload": PUBLIC_STATUS}
        adapter = GitHubStagingAdapter(client=client, grant=grant(
            "github", public_sanitized=True,
            allowed_kinds=frozenset({"INTEGRITY_REPORT"}),
        ))
        normalized = {**PUBLIC_STATUS, "intent_id": "github:inbox/fixture.json"}

        with self.assertRaisesRegex(RuntimeError, "GITHUB_STAGING_READBACK_BINDING_REQUIRED"):
            adapter.acknowledge(entry, writer_receipt(
                "github:inbox/fixture.json", item=normalized))
        client.mark_processed.assert_not_called()


if __name__ == "__main__":
    unittest.main()
