"""Drive Inbox transport regressions; no credentials or live Drive access."""
from __future__ import annotations

import json
import os
import re
import unittest
from unittest.mock import patch

from runtime.nexo_agent_api.drive_transport import DriveInbox, TowerTransportError

API = "https://www.googleapis.com/drive/v3/files"
FOLDER = "application/vnd.google-apps.folder"


class Response:
    def __init__(self, payload=None, body=b"", status=200):
        self.status_code = status
        self.content = body
        self.text = body.decode("utf-8", "replace")
        self.payload = payload

    def json(self):
        return self.payload


def folder(identity="INBOX", name="NEXO_INBOX", parents=()):
    return {"id": identity, "name": name, "mimeType": FOLDER,
            "parents": list(parents), "trashed": False}


def proposal(identity="P1", parent="INBOX"):
    return {"id": identity, "name": identity + ".json", "mimeType": "application/json",
            "parents": [parent], "trashed": False, "createdTime": identity}


class FakeInboxDrive:
    """Minimal provider model, including Drive fields-mask and pagination behavior."""
    def __init__(self, folders=None, files=None):
        self.folders = [folder()] if folders is None else folders
        self.files = files or []
        self.calls = []
        self.metadata_status = {}
        self.ignore_move = False
        self.page_limit = 200

    def get(self, url, params=None, timeout=None):
        params = dict(params or {})
        self.calls.append(("GET", url, params))
        if url == API:
            q = params["q"]
            if "mimeType !=" in q:
                rows = self.files
            else:
                match = re.search(r"name = '((?:\\.|[^'])*)'", q)
                name = re.sub(r"\\(.)", r"\1", match[1])
                rows = [row for row in self.folders if row["name"] == name]
            parent = re.search(r"'((?:\\.|[^'])*)' in parents", q)
            if parent:
                identity = re.sub(r"\\(.)", r"\1", parent[1])
                rows = [row for row in rows if identity in row["parents"]]
            rows = [row for row in rows if not row.get("trashed")]
            offset = int(params.get("pageToken", 0))
            size = min(params["pageSize"], self.page_limit)
            result = {"files": [dict(row) for row in rows[offset:offset + size]]}
            if offset + size < len(rows) and "nextPageToken" in params["fields"]:
                result["nextPageToken"] = str(offset + size)
            return Response(result)
        identity = url.removeprefix(API + "/")
        if params.get("alt") == "media":
            return Response(body=json.dumps({"kind": "BOARD_POST", "payload": {"text": identity}}).encode())
        if identity in self.metadata_status:
            return Response(status=self.metadata_status[identity])
        rows = [row for row in self.folders + self.files if row["id"] == identity]
        return Response(dict(rows[0])) if rows else Response(status=404)

    def post(self, url, json=None, params=None, timeout=None):
        self.calls.append(("POST", url, dict(params or {})))
        row = folder("PROCESSED", json["name"], json["parents"])
        self.folders.append(row)
        return Response(dict(row))

    def patch(self, url, params=None, json=None, timeout=None):
        params = dict(params or {})
        self.calls.append(("PATCH", url, params))
        row = next(row for row in self.files if url == API + "/" + row["id"])
        if not self.ignore_move:
            row["parents"] = [p for p in row["parents"] if p != params["removeParents"]]
            row["parents"].append(params["addParents"])
        return Response(dict(row))

    def mutations(self):
        return [call for call in self.calls if call[0] in {"POST", "PATCH"}]


class DriveInboxTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {"NEXO_INBOX_FOLDER_ID": ""})
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_pending_reads_every_page_beyond_200(self):
        drive = FakeInboxDrive(files=[proposal(f"P{i:03}") for i in range(205)])
        items = DriveInbox(session=drive).pending()
        self.assertEqual([item["id"] for item in items], [f"P{i:03}" for i in range(205)])
        self.assertEqual(items[-1]["payload"]["payload"]["text"], "P204")
        pages = [p for method, url, p in drive.calls if url == API and "mimeType !=" in p.get("q", "")]
        self.assertEqual([p.get("pageToken") for p in pages], [None, "200"])

    def test_ambiguous_inbox_fails_before_reading_content(self):
        drive = FakeInboxDrive(folders=[folder("A"), folder("B")], files=[proposal(parent="A")])
        with self.assertRaisesRegex(RuntimeError, "INBOX_FOLDER_AMBIGUOUS"):
            DriveInbox(session=drive).pending()
        self.assertFalse(any(p.get("alt") == "media" for _, _, p in drive.calls))

    def test_ambiguity_on_later_page_is_detected(self):
        drive = FakeInboxDrive(folders=[folder("FIRST"), folder("SECOND")])
        drive.page_limit = 1
        with self.assertRaisesRegex(RuntimeError, "INBOX_FOLDER_AMBIGUOUS"):
            DriveInbox(session=drive).pending()
        self.assertEqual([p.get("pageToken") for _, _, p in drive.calls], [None, "1"])

    def test_missing_inbox_is_an_explicit_failure(self):
        drive = FakeInboxDrive(folders=[])
        with self.assertRaisesRegex(RuntimeError, "INBOX_FOLDER_NOT_FOUND"):
            DriveInbox(session=drive).pending()

    def test_missing_inbox_never_searches_global_processed_or_mutates(self):
        drive = FakeInboxDrive(folders=[folder("OTHER", "processed")], files=[proposal()])
        with self.assertRaisesRegex(RuntimeError, "INBOX_FOLDER_NOT_FOUND"):
            DriveInbox(session=drive).mark_processed("P1")
        self.assertEqual(drive.mutations(), [])
        self.assertFalse(any("name = 'processed'" in p.get("q", "") for _, _, p in drive.calls))

    def test_single_folder_and_empty_folder_remain_healthy(self):
        self.assertEqual(DriveInbox(session=FakeInboxDrive()).pending(), [])
        items = DriveInbox(session=FakeInboxDrive(files=[proposal()])).pending()
        self.assertEqual(items[0]["payload"]["kind"], "BOARD_POST")

    def test_pin_bypasses_name_search_and_selects_exact_folder(self):
        drive = FakeInboxDrive(folders=[folder("A"), folder("B")], files=[proposal("PA", "A"), proposal("PB", "B")])
        items = DriveInbox(session=drive, folder_id="B").pending()
        self.assertEqual([row["id"] for row in items], ["PB"])
        self.assertFalse(any("name =" in p.get("q", "") for _, _, p in drive.calls))

    def test_environment_pin_is_honored_by_existing_constructor(self):
        drive = FakeInboxDrive(folders=[folder("A"), folder("B")], files=[proposal(parent="B")])
        with patch.dict(os.environ, {"NEXO_INBOX_FOLDER_ID": " B "}):
            self.assertEqual(len(DriveInbox(session=drive).pending()), 1)

    def test_explicit_pin_overrides_environment(self):
        drive = FakeInboxDrive(folders=[folder("A"), folder("B")], files=[proposal(parent="B")])
        with patch.dict(os.environ, {"NEXO_INBOX_FOLDER_ID": "A"}):
            self.assertEqual(len(DriveInbox(session=drive, folder_id="B").pending()), 1)

    def test_pin_rejects_non_folder_or_trashed_target_without_fallback(self):
        for invalid in [{**folder(), "mimeType": "application/json"}, {**folder(), "trashed": True}]:
            with self.subTest(invalid=invalid):
                drive = FakeInboxDrive(folders=[invalid, folder("FALLBACK")])
                with self.assertRaisesRegex(RuntimeError, "INBOX_FOLDER_INVALID"):
                    DriveInbox(session=drive, folder_id="INBOX").pending()
                self.assertFalse(any(url == API for _, url, _ in drive.calls))

    def test_unavailable_pin_never_falls_back_or_retries(self):
        for status in (403, 404):
            with self.subTest(status=status):
                drive = FakeInboxDrive()
                drive.metadata_status["PIN"] = status
                with self.assertRaises(RuntimeError):
                    DriveInbox(session=drive, folder_id="PIN").pending()
                self.assertEqual(len(drive.calls), 1)
                if status == 403:
                    with self.assertRaises(TowerTransportError) as caught:
                        DriveInbox(session=drive, folder_id="PIN").pending()
                    self.assertEqual(caught.exception.retry_condition, "OPERATOR_REAUTHORIZATION")

    def test_processed_folder_ambiguity_prevents_mutation(self):
        drive = FakeInboxDrive(folders=[folder(), folder("P1", "processed", ["INBOX"]), folder("P2", "processed", ["INBOX"])], files=[proposal("ITEM")])
        with self.assertRaisesRegex(RuntimeError, "INBOX_FOLDER_AMBIGUOUS"):
            DriveInbox(session=drive).mark_processed("ITEM")
        self.assertEqual(drive.mutations(), [])

    def test_processed_rejects_file_outside_selected_inbox_before_mutation(self):
        drive = FakeInboxDrive(files=[proposal(parent="OTHER")])
        with self.assertRaisesRegex(RuntimeError, "INBOX_ITEM_PARENT_MISMATCH"):
            DriveInbox(session=drive).mark_processed("P1")
        self.assertEqual(drive.mutations(), [])

    def test_processed_folder_moved_after_listing_is_rejected_before_patch(self):
        class MovedDestination(FakeInboxDrive):
            def get(self, url, params=None, timeout=None):
                if url == API + "/PROCESSED":
                    self.folders[1]["parents"] = ["OTHER"]
                return super().get(url, params=params, timeout=timeout)

        drive = MovedDestination(folders=[folder(), folder("PROCESSED", "processed", ["INBOX"])], files=[proposal()])
        with self.assertRaisesRegex(RuntimeError, "INBOX_PROCESSED_FOLDER_INVALID"):
            DriveInbox(session=drive).mark_processed("P1")
        self.assertEqual(drive.mutations(), [])

    def test_acknowledgement_keeps_folder_identity_after_name_changes(self):
        drive = FakeInboxDrive(files=[proposal()])
        inbox = DriveInbox(session=drive)
        inbox.pending()
        drive.folders[0]["name"] = "RENAMED"
        drive.folders.append(folder("NEW-SAME-NAME"))
        inbox.mark_processed("P1")
        move = next(call for call in drive.calls if call[0] == "PATCH")
        self.assertEqual(move[2]["removeParents"], "INBOX")
        self.assertEqual(drive.files[0]["parents"], ["PROCESSED"])

    def test_acknowledgement_confirms_move_and_supports_shared_drives(self):
        drive = FakeInboxDrive(files=[proposal()])
        DriveInbox(session=drive).mark_processed("P1")
        self.assertEqual(drive.files[0]["parents"], ["PROCESSED"])
        for _, _, params in drive.mutations():
            self.assertEqual(params.get("supportsAllDrives"), "true")
        self.assertEqual(drive.calls[-1][0:2], ("GET", API + "/P1"))

    def test_failed_move_readback_is_reported(self):
        drive = FakeInboxDrive(files=[proposal()])
        drive.ignore_move = True
        with self.assertRaisesRegex(RuntimeError, "INBOX_MARK_READBACK_MISMATCH"):
            DriveInbox(session=drive).mark_processed("P1")

    def test_query_escapes_folder_name(self):
        name = "NEXO 'INBOX' \\ team"
        drive = FakeInboxDrive(folders=[folder(name=name)])
        self.assertEqual(DriveInbox(name=name, session=drive).pending(), [])
        query = next(p["q"] for _, url, p in drive.calls if url == API)
        self.assertIn("name = 'NEXO \\'INBOX\\' \\\\ team'", query)

    def test_empty_page_with_token_is_followed(self):
        class Pages:
            def __init__(self):
                self.calls = []

            def get(self, url, params=None, timeout=None):
                self.calls.append(dict(params))
                return Response({"files": [{"id": "LAST"}]} if params.get("pageToken") else {"files": [], "nextPageToken": "next"})

        drive = Pages()
        self.assertEqual(DriveInbox(session=drive)._query("test"), [{"id": "LAST"}])
        self.assertEqual(len(drive.calls), 2)

    def test_incomplete_search_is_not_treated_as_empty(self):
        class Incomplete:
            def get(self, *args, **kwargs):
                return Response({"files": [], "incompleteSearch": True})

        with self.assertRaisesRegex(RuntimeError, "INBOX_LIST_INCOMPLETE"):
            DriveInbox(session=Incomplete())._query("test")

    def test_repeating_page_token_fails_instead_of_looping(self):
        class Repeated:
            def __init__(self):
                self.calls = 0

            def get(self, *args, **kwargs):
                self.calls += 1
                if self.calls > 3:
                    raise AssertionError("pagination did not stop")
                return Response({"files": [], "nextPageToken": "same"})

        drive = Repeated()
        with self.assertRaisesRegex(RuntimeError, "INBOX_LIST_REPEATED_PAGE_TOKEN"):
            DriveInbox(session=drive)._query("test")
        self.assertEqual(drive.calls, 2)


if __name__ == "__main__":
    unittest.main()
