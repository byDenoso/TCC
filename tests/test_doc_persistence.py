"""Native Doc delivery, interrupted writes and exact private Writer effects."""
from __future__ import annotations

import base64
import copy
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from runtime.nexo_agent_api import doc_persistence as docs, gpt_writer, inbox_client
from runtime.nexo_agent_api.drive_transport import DriveInbox, TowerTransportError
from runtime.nexo_agent_api.drive_transport import DriveTower, TowerConflict
from runtime.nexo_agent_api.live_tower import build_live_tower_payload, read_live_tower_bytes, materialize_live_tower


def package(**changes):
    values = dict(artifact_id="result-fixture-v1", campaign_id="CAMP-FIXTURE", created_at="2026-10-15T12:00:00Z",
                  producer_role="EXECUTOR", provenance={"test_id": "TEST-FIXTURE", "code_revision": "fixture-only"},
                  files=[{"name": "code.py", "mime_type": "text/x-python", "content": "print('ciência')\r\n".encode()},
                         {"name": "table.csv", "mime_type": "text/csv", "content": b"x,y\n1,2\n"},
                         {"name": "figure.png", "mime_type": "image/png", "content": base64.b64decode(
                             "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jvYkAAAAASUVORK5CYII=")}])
    return docs.pack(**{**values, **changes})


class CodecTests(unittest.TestCase):
    def test_original_bytes_roundtrip_and_exclusive_restore(self):
        p = package()
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "package.json"
            source.write_bytes(docs.canonical(p))
            out = Path(tmp) / "restored"
            self.assertEqual(docs.main(["restore", str(source), str(out)]), 0)
            for entry in p["files"]:
                self.assertEqual(docs.digest((out / entry["name"]).read_bytes()), entry["sha256"])
            with self.assertRaises(FileExistsError):
                docs.main(["restore", str(source), str(out)])

    def test_native_export_framing_does_not_change_package_identity(self):
        p = package()
        self.assertEqual(docs.parse_package(b"\xef\xbb\xbf" + docs.canonical(p) + b"\r\n"), p)
        self.assertEqual(docs.digest(docs.canonical(docs.parse_package(docs.canonical(p)))), docs.digest(docs.canonical(p)))

    def test_size_limit_counts_original_bytes_not_base64(self):
        p = package(files=[{"name": "large.bin", "mime_type": "application/octet-stream", "content": b"x" * docs.MAX_BYTES}])
        self.assertEqual(docs.parse_package(docs.canonical(p)), p)
        with self.assertRaises(docs.PackageError):
            package(files=[{"name": "large.bin", "mime_type": "application/octet-stream", "content": b"x" * (docs.MAX_BYTES + 1)}])

    def test_invalid_bytes_names_roles_and_hashes_are_rejected_before_restore(self):
        for name in ("../escape", "nested/file", "file\\escape", "CON.txt", "trailing.", "..", "a:b"):
            with self.subTest(name=name), self.assertRaises(docs.PackageError):
                package(files=[{"name": name, "mime_type": "text/plain", "content": b"x"}])
        for key, value in (("producer_role", {}), ("created_at", "2026-10-15T12:00:00-03:00"), ("provenance", {})):
            p = package()
            p[key] = value
            with self.subTest(key=key), self.assertRaises(docs.PackageError):
                docs.validate_package(p)
        for field, value in (("sha256", "sha256:" + "0" * 64), ("content_b64", "!!!"), ("size_bytes", True)):
            p = package()
            p["files"][0][field] = value
            with self.subTest(field=field), self.assertRaises(docs.PackageError):
                docs.validate_package(p)
        p = package()
        p["files"].append({**p["files"][0], "name": "CODE.py"})
        with self.assertRaises(docs.PackageError):
            docs.validate_package(p)

    def test_duplicate_json_keys_nonfinite_and_unknown_fields_fail_closed(self):
        for raw in (b'{"contract":"a","contract":"b"}', b'{"a":NaN}', b"not-json", b"[]"):
            with self.subTest(raw=raw), self.assertRaises(docs.PackageError):
                docs.parse_package(raw)
        p = package()
        p["unexpected"] = "not allowed"
        with self.assertRaises(docs.PackageError):
            docs.validate_package(p)


class MemoryDocs:
    staging_folder_id = "OWNER_ROOT"
    def __init__(self):
        self.files, self.saved, self.calls = {}, [], []
        self.fail_after = None
        self.destination_private = True
        self.hidden = False
    def checkpoint(self, state):
        self.saved.append(copy.deepcopy(state))
    def verify_destination(self, folder):
        return self.destination_private
    def lookup(self, title):
        return [] if self.hidden else [fid for fid, f in self.files.items() if f["title"] == title]
    def fail(self, method):
        if self.fail_after == method:
            self.fail_after = None
            raise TimeoutError()
    def create(self, title):
        self.calls.append("create")
        identity = "DOC" + str(len(self.files) + 1)
        self.files[identity] = {"title": title, "raw": b"\n", "revision": "r1", "mime_type": docs.DOC_MIME,
                                "parent_ids": [self.staging_folder_id], "private_verified": True}
        self.fail("create")
        return identity
    def read(self, fid):
        self.calls.append("read")
        return dict(self.files[fid])
    def fill(self, fid, text, revision):
        self.calls.append("fill")
        if self.files[fid]["revision"] != revision:
            raise TowerTransportError("DOC_FILL", 409, "RECONCILE_TOWER_BEFORE_REAPPLY")
        self.files[fid].update(raw=text.encode() + b"\n", revision="r2")
        self.fail("fill")
    def move(self, fid, folder):
        self.calls.append("move")
        assert self.files[fid]["raw"] != b"\n", "Empty Doc was published"
        self.files[fid]["parent_ids"] = [folder]
        self.fail("move")


class PublishTests(unittest.TestCase):
    def prepared(self, folder="CAMPAIGN_FOLDER"):
        return docs.prepare_document(docs.canonical(package()), stable_id="fixture-delivery", folder_id=folder)

    def test_empty_doc_never_reaches_destination_and_replay_is_read_only(self):
        transport, journal = MemoryDocs(), {}
        result = docs.publish_document(self.prepared(), transport, journal=journal)
        self.assertEqual(result["stage"], "DELIVERED")
        self.assertEqual(transport.calls.count("create"), 1)
        self.assertEqual(transport.calls.count("fill"), 1)
        docs.publish_document(self.prepared(), transport, journal=journal)
        self.assertEqual(transport.calls.count("create"), 1)
        self.assertEqual(transport.calls.count("fill"), 1)
        self.assertEqual(transport.calls.count("move"), 1)

    def test_new_runtime_reconciles_each_lost_response_without_duplicate_mutation(self):
        for method in ("create", "fill", "move"):
            with self.subTest(method=method):
                first, journal = MemoryDocs(), {}
                first.fail_after = method
                self.assertEqual(docs.publish_document(self.prepared(), first, journal=journal)["stage"], "OUTCOME_UNKNOWN")
                resumed = MemoryDocs()
                resumed.files = first.files
                resumed.calls = list(first.calls)
                result = docs.publish_document(self.prepared(), resumed, journal=copy.deepcopy(first.saved[-1]))
                self.assertEqual(result["stage"], "DELIVERED")
                for action in ("create", "fill", "move"):
                    self.assertEqual(resumed.calls.count(action), 1, (method, action))

    def test_unknown_create_and_incomplete_discovery_cannot_create_again(self):
        transport, journal = MemoryDocs(), {}
        transport.fail_after = "create"
        docs.publish_document(self.prepared(), transport, journal=journal)
        transport.hidden = True
        self.assertEqual(docs.publish_document(self.prepared(), transport, journal=journal)["stage"], "OUTCOME_UNKNOWN")
        self.assertEqual(transport.calls.count("create"), 1)

    def test_private_destination_is_checked_before_creating_or_moving(self):
        transport = MemoryDocs()
        transport.destination_private = False
        with self.assertRaisesRegex(docs.PackageError, "DESTINATION_UNVERIFIED"):
            docs.publish_document(self.prepared(), transport, journal={})
        self.assertFalse(transport.files)

    def test_existing_doc_with_different_content_is_never_overwritten(self):
        transport = MemoryDocs()
        fid = transport.create(self.prepared()["title"])
        transport.files[fid]["raw"] = b"different content\n"
        with self.assertRaisesRegex(docs.PackageError, "CONTENT_CONFLICT"):
            docs.publish_document(self.prepared(), transport, journal={})
        self.assertNotIn("fill", transport.calls)

    def test_permission_denial_never_switches_route_or_retries(self):
        transport, journal = MemoryDocs(), {}
        transport.create = lambda title: (_ for _ in ()).throw(TowerTransportError("DOC_CREATE", 403, "OPERATOR_REAUTHORIZATION"))
        with self.assertRaises(TowerTransportError):
            docs.publish_document(self.prepared(), transport, journal=journal)
        self.assertEqual(journal["stage"], "PERMISSION_DENIED")
        with self.assertRaises(PermissionError):
            docs.publish_document(self.prepared(), transport, journal=journal)

    def test_checkpoint_failure_prevents_remote_create(self):
        transport = MemoryDocs()
        transport.checkpoint = lambda state: (_ for _ in ()).throw(OSError("fixture checkpoint unavailable"))
        with self.assertRaises(OSError):
            docs.publish_document(self.prepared(), transport, journal={})
        self.assertFalse(transport.files)


class Reply:
    def __init__(self, value=None, raw=b"", status=200):
        self.value, self.content, self.status_code = value, raw, status
        self.text = raw.decode("utf-8", "replace")
    def json(self):
        return self.value


class EvidenceDrive:
    def __init__(self, p):
        self.p, self.denied, self.public = p, False, False
        self.export_status = 200
        self.wrong_parent = False
        self.calls = []
    def get(self, url, params=None, timeout=None):
        self.calls.append((url, params))
        if self.denied:
            return Reply(status=403)
        if url.endswith("/permissions"):
            return Reply({"permissions": [
                {"id": "owner-fixture", "type": "user", "role": "owner"},
                {"id": "reader-fixture", "type": "anyone" if self.public else "user", "role": "reader"},
            ]})
        if url.endswith("/export"):
            return Reply(raw=b"\xef\xbb\xbf" + docs.canonical(self.p) + b"\n", status=self.export_status)
        identity = url.rsplit("/", 1)[-1]
        value = {"id": identity, "trashed": False, "permissions": [{"type": "anyone" if self.public else "user", "role": "reader"}]}
        if identity == docs.CAMPAIGNS_ID:
            value.update(mimeType=DriveInbox.FOLDER)
        elif identity == "CAMPAIGN_FOLDER":
            value.update(mimeType=DriveInbox.FOLDER, name=self.p["campaign_id"], parents=[docs.CAMPAIGNS_ID])
        elif identity == "PACKAGE_DOC":
            value.update(mimeType=docs.DOC_MIME, name="nexo-doc-v1-" + self.p["artifact_id"],
                         parents=["WRONG" if self.wrong_parent else "CAMPAIGN_FOLDER"])
        return Reply(value)


class WriterTests(unittest.TestCase):
    def setUp(self):
        self.p = package()
        self.ref = dict(file_id="PACKAGE_DOC", folder_id="CAMPAIGN_FOLDER", artifact_id=self.p["artifact_id"],
                        campaign_id=self.p["campaign_id"], package_sha256=docs.digest(docs.canonical(self.p)))
        self.envelope = dict(kind="BOARD_POST", source="ENGINEER", created_at="2026-10-15T12:00:00Z", intent_id="fixture-doc-delivery",
                             payload={"to": "GUARDIAO", "text": "Synthetic persisted evidence", "private": True}, artifact_packages=[self.ref])
        self.item = {**self.envelope, "_inbox_source": "DRIVE", "_inbox_name": "fixture-doc-delivery", "_inbox_id": "INBOX_DOC"}
        self.drive = EvidenceDrive(self.p)
        self.reader = DriveInbox(session=self.drive).read_artifact_package
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "CONTROL.json").write_text(json.dumps({"truth_owner": "TOWER_V06@GOOGLE_DRIVE_PRIVATE"}))
            self.raw = json.dumps(build_live_tower_payload(root)).encode()

    def test_drive_export_writer_catalog_exact_effect_and_replay(self):
        packed, report = gpt_writer.apply_to_tower(self.raw, [self.item], artifact_reader=self.reader)
        self.assertFalse(report["rejected"], report)
        self.assertEqual(report["public_operation_receipts"], [])
        tower = read_live_tower_bytes(packed)
        catalog = tower["files"]["entities/artifact/ARTIFACT_PACKAGE::result-fixture-v1.json"]["value"]
        self.assertTrue(catalog["private"])
        self.assertNotIn("content_b64", catalog["files"][0])
        prepared = inbox_client.prepare(self.envelope, runtime_role="ENGINEER", allowed_kinds={"BOARD_POST"})
        result = docs.confirm_application(tower, prepared, expected_effects=[
            {"path": "evolution/board.json", "contains": {"posts": [{"text": self.envelope["payload"]["text"], "private": True}]}},
            {"path": "entities/artifact/ARTIFACT_PACKAGE::result-fixture-v1.json", "contains": {"package_sha256": self.ref["package_sha256"]}},
        ])
        self.assertEqual(result["stage"], "TOWER_APPLIED_READBACK")
        replay, second = gpt_writer.apply_to_tower(packed, [self.item], artifact_reader=self.reader)
        self.assertIsNone(replay)
        self.assertFalse(second["rejected"])
        self.assertEqual({row["outcome"] for row in second["operation_receipts"]}, {"ALREADY_APPLIED"})

    def test_missing_reader_or_access_leaves_original_proposal_pending(self):
        for reader in (None, self.reader):
            self.drive.denied = True
            packed, report = gpt_writer.apply_to_tower(self.raw, [self.item], artifact_reader=reader)
            self.assertFalse(report["applied"])
            self.assertFalse(report["handled"])
            self.assertTrue(report["deferred"])
            self.assertFalse(report["operation_receipts"])

    def test_invalid_reference_hash_parent_or_acl_cannot_apply_scientific_effect(self):
        for mode in ("hash", "parent", "acl"):
            with self.subTest(mode=mode):
                self.drive = EvidenceDrive(self.p)
                item = copy.deepcopy(self.item)
                if mode == "hash":
                    item["artifact_packages"][0]["package_sha256"] = "sha256:" + "0" * 64
                self.drive.wrong_parent = mode == "parent"
                self.drive.public = mode == "acl"
                packed, report = gpt_writer.apply_to_tower(self.raw, [item], artifact_reader=DriveInbox(session=self.drive).read_artifact_package)
                self.assertFalse(report["applied"])
                self.assertTrue(report["rejected"])
                self.assertNotIn("evolution/board.json", read_live_tower_bytes(packed)["files"])

    def test_receipt_without_actual_effect_cannot_be_confirmed(self):
        packed, _ = gpt_writer.apply_to_tower(self.raw, [self.item], artifact_reader=self.reader)
        with tempfile.TemporaryDirectory() as tmp:
            root, _ = materialize_live_tower(packed, Path(tmp) / "tower")
            (root / "evolution/board.json").unlink()
            tower = build_live_tower_payload(root)
        prepared = inbox_client.prepare(self.envelope, runtime_role="ENGINEER", allowed_kinds={"BOARD_POST"})
        with self.assertRaisesRegex(docs.PackageError, "TOWER_EFFECT_READBACK_MISSING"):
            docs.confirm_application(tower, prepared, expected_effects=[{"path": "evolution/board.json", "contains": {"posts": [{}]}}])

    def test_catalog_readback_failure_rolls_back_primary_effect(self):
        with patch.object(docs, "catalog_readback", return_value=False):
            packed, report = gpt_writer.apply_to_tower(self.raw, [self.item], artifact_reader=self.reader)
        self.assertFalse(report["applied"])
        self.assertNotIn("evolution/board.json", read_live_tower_bytes(packed)["files"])

    def test_replay_rechecks_evidence_access(self):
        packed, _ = gpt_writer.apply_to_tower(self.raw, [self.item], artifact_reader=self.reader)
        self.drive.denied = True
        _, second = gpt_writer.apply_to_tower(packed, [self.item], artifact_reader=self.reader)
        self.assertFalse(second["applied"])
        self.assertTrue(second["deferred"])

    def test_export_failure_does_not_block_independent_delivery(self):
        self.drive.export_status = 404
        independent = {"kind": "BOARD_POST", "source": "ENGINEER", "intent_id": "independent-fixture",
                       "_inbox_source": "DRIVE", "_inbox_name": "independent", "payload": {"to": "GUARDIAO", "text": "Independent fixture"}}
        packed, report = gpt_writer.apply_to_tower(self.raw, [self.item, independent], artifact_reader=self.reader)
        self.assertEqual(report["applied"], ["independent"])
        self.assertEqual(len(report["deferred"]), 1)
        posts = read_live_tower_bytes(packed)["files"]["evolution/board.json"]["value"]["posts"]
        self.assertEqual([row["text"] for row in posts], ["Independent fixture"])

    def test_pending_health_exposes_counts_and_age_without_private_identity(self):
        from datetime import datetime, timezone
        pending = [{"name": "private-identity", "createdTime": "2026-10-15T10:00:00Z", "payload": self.envelope}]
        report = {"deferred": [{"item": "private-identity"}]}
        result = gpt_writer._evidence_pending_health(pending, report, now=datetime(2026, 10, 15, 12, tzinfo=timezone.utc))
        self.assertEqual(result, {"pending": 1, "oldest_age_seconds": 7200, "attention_required": True})
        self.assertNotIn("private-identity", json.dumps(result))

    def test_public_unknown_batch_and_raw_catalog_admission_fail_closed(self):
        cases = [
            {**self.item, "_inbox_source": "GATEWAY"},
            {**self.item, "kind": "SOMETHING_NEW"},
            {**self.item, "kind": "BATCH", "payload": {"items": [self.envelope]}},
            {"kind": "BATCH", "payload": {"items": [{"kind": "BATCH", "payload": {"items": [self.envelope]}}]}},
            {"entity_kind": "artifact", "entity_name": "ARTIFACT_PACKAGE::forged", "expected_version": 0,
             "writer_role": "LEARNER", "changes": {"kind": docs.CONTRACT}},
            {**self.p, "_inbox_source": "DRIVE"},
        ]
        for item in cases:
            with self.subTest(kind=item.get("kind")):
                _, report = gpt_writer.apply_to_tower(self.raw, [item], artifact_reader=self.reader)
                self.assertFalse(report["applied"])
                self.assertTrue(report["rejected"])


class NativeSession:
    """Provider-shaped adapter fixture; no mocked persistence implementation."""
    def __init__(self):
        self.memory, self.requests = MemoryDocs(), []
    def get(self, url, params=None, timeout=None):
        self.requests.append(("get", url, params))
        if url == "https://www.googleapis.com/drive/v3/files":
            title = params["q"].split("'")[1]
            return Reply({"files": [{"id": fid} for fid in self.memory.lookup(title)]})
        identity = url.rsplit("/", 1)[-1]
        if url.startswith("https://docs.googleapis.com/"):
            file = self.memory.files[identity]
            return Reply({"documentId": identity, "revisionId": file["revision"], "tabs": [{"documentTab": {"body": {
                "content": [{"sectionBreak": {}}, {"paragraph": {"elements": [{"textRun": {"content": file["raw"].decode()}}]}}]}}}]})
        meta = {"id": self.memory.staging_folder_id if identity == "root" else identity,
                "mimeType": DriveInbox.FOLDER, "trashed": False, "permissions": [{"type": "user", "role": "owner"}]}
        if identity in self.memory.files:
            meta.update(mimeType=docs.DOC_MIME, parents=self.memory.files[identity]["parent_ids"], name=self.memory.files[identity]["title"])
        if identity == "CAMPAIGN_FOLDER" and not self.memory.destination_private:
            meta["permissions"] = [{"type": "anyone", "role": "reader"}]
        return Reply(meta)
    def post(self, url, json=None, timeout=None):
        self.requests.append(("post", url, json))
        if url.endswith(":batchUpdate"):
            fid = url.rsplit("/", 1)[-1].split(":")[0]
            assert json["requests"][0]["insertText"]["location"] == {"index": 1}
            self.memory.fill(fid, json["requests"][0]["insertText"]["text"], json["writeControl"]["requiredRevisionId"])
            return Reply({})
        return Reply({"documentId": self.memory.create(json["title"])})
    def patch(self, url, params=None, json=None, timeout=None):
        self.requests.append(("patch", url, params))
        assert params["removeParents"] == self.memory.staging_folder_id
        self.memory.move(url.rsplit("/", 1)[-1], params["addParents"])
        return Reply({})


class NativeAdapterTests(unittest.TestCase):
    def test_actual_adapter_uses_guarded_insert_then_move_and_exact_readback(self):
        session, journal = NativeSession(), {}
        adapter = docs.NativeDocsTransport(session, checkpoint=session.memory.checkpoint)
        prepared = docs.prepare_document(docs.canonical(package()), stable_id="native-fixture", folder_id="CAMPAIGN_FOLDER")
        result = docs.publish_document(prepared, adapter, journal=journal)
        self.assertEqual(result["stage"], "DELIVERED")
        self.assertEqual(docs.parse_package(session.memory.files[result["file_id"]]["raw"]), package())
        self.assertEqual(session.memory.calls.count("create"), 1)
        self.assertEqual(session.memory.calls.count("fill"), 1)
        self.assertEqual(session.memory.calls.count("move"), 1)
        docs.publish_document(prepared, adapter, journal=journal)
        self.assertEqual(session.memory.calls.count("fill"), 1)

    def test_public_folder_is_rejected_before_any_mutation(self):
        session = NativeSession()
        session.memory.destination_private = False
        adapter = docs.NativeDocsTransport(session, checkpoint=session.memory.checkpoint)
        prepared = docs.prepare_document(b"{}", stable_id="native-fixture", folder_id="CAMPAIGN_FOLDER")
        with self.assertRaises(docs.PackageError):
            docs.publish_document(prepared, adapter, journal={})
        self.assertFalse(any(method in {"post", "patch"} for method, _, _ in session.requests))


class RobotBoundaryTests(unittest.TestCase):
    setUp = WriterTests.setUp
    def test_existing_robot_reads_docs_applies_and_only_then_moves_proposal(self):
        fixture = self
        for conflict in (False, True):
            state = {"raw": self.raw, "writes": 0, "committed": False, "moved": False}
            class LocalTower(DriveTower):
                def __init__(self, **kwargs):
                    pass
                def download(self, **kwargs):
                    return state["raw"], docs.digest(state["raw"])
                def compare_and_swap(self, base, raw):
                    state["writes"] += 1
                    if conflict:
                        raise TowerConflict("fixture conflict")
                    fixture.assertEqual(base, docs.digest(state["raw"]))
                    state["raw"] = raw
                    revision = read_live_tower_bytes(raw)["revision"]
                    state["committed"] = True
                    return {"state_fingerprint": revision, "readback": "PASS"}
            class RobotDrive(EvidenceDrive):
                def get(self, url, params=None, timeout=None):
                    identity = url.rsplit("/", 1)[-1]
                    if identity == "files":
                        if "name = 'processed'" in params["q"]:
                            return Reply({"files": [{"id": "PROCESSED"}]})
                        return Reply({"files": [] if state["moved"] else [{
                            "id": "INBOX_DOC", "name": "fixture-doc-delivery", "mimeType": docs.DOC_MIME,
                            "parents": ["INBOX"], "createdTime": "2026-10-15T12:00:00Z"}]})
                    if url.endswith("/INBOX_DOC/export"):
                        return Reply(raw=docs.canonical(fixture.envelope) + b"\n")
                    if identity in {"INBOX", "PROCESSED", "INBOX_DOC"}:
                        return Reply({"id": identity, "trashed": False,
                                      "mimeType": docs.DOC_MIME if identity == "INBOX_DOC" else DriveInbox.FOLDER,
                                      "parents": (["INBOX"] if identity == "PROCESSED" else
                                                  (["PROCESSED"] if state["moved"] else ["INBOX"]))})
                    return super().get(url, params=params, timeout=timeout)
                def patch(self, url, params=None, json=None, timeout=None):
                    fixture.assertTrue(state["committed"], "Proposal consumed before canonical readback")
                    fixture.assertEqual(params["addParents"], "PROCESSED")
                    state["moved"] = True
                    return Reply({})
            remote = DriveInbox(session=RobotDrive(self.p), folder_id="INBOX")
            with tempfile.TemporaryDirectory() as tmp, \
                 patch.dict(os.environ, {"NEXO_HOME": tmp}, clear=True), \
                 patch("runtime.nexo_agent_api.drive_transport.DriveTower", LocalTower), \
                 patch("runtime.nexo_agent_api.drive_transport.DriveInbox", return_value=remote), \
                 patch("runtime.nexo_agent_api.operational_tick.tick_existing_writer", return_value={"status": "NO_OP"}), \
                 patch("builtins.print") as printed:
                self.assertEqual(gpt_writer.main(["robot"]), 3 if conflict else 0)
                self.assertEqual(state["moved"], not conflict)
                self.assertEqual(state["writes"], 3 if conflict else 1)
                # An OS-backed lock preserves the inode; verify RELEASE by reacquiring.
                from runtime.nexo_agent_api.drive_transport import writer_lock
                with writer_lock():
                    self.assertTrue((Path(tmp) / "tower.lock").exists())
                self.assertNotIn("Synthetic persisted evidence", str(printed.call_args_list))
                if not conflict:
                    self.assertEqual(gpt_writer.main(["robot"]), 0)
                    self.assertEqual(state["writes"], 1)


if __name__ == "__main__":
    unittest.main()
