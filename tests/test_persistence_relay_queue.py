"""Offline regression for queued push delivery; no scientific workload is created."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from nexo_persist.relay import WriterReceipts, collect_changed, load_request, relay_one
from test_persistence_relay import meta

ROOT = Path(__file__).resolve().parents[1]


class Inbox:
    def __init__(self):
        self.bodies = {}
        self.writes = []

    def get(self, target):
        return (200, meta(self.bodies[target])) if target in self.bodies else (404, {})

    def put(self, target, body, sha=None):
        self.bodies[target] = body
        self.writes.append((target, sha))
        # Simulate a committed write whose transport response is lost.
        return 503, {}


class QueuedRelayTests(unittest.TestCase):
    def test_workflow_preserves_pending_pushes_and_event_checkout(self):
        workflow = (ROOT / ".github/workflows/nexo-scheduled-persistence-relay.yml").read_text()
        block = workflow.split("\nconcurrency:\n", 1)[1].split("\njobs:", 1)[0]
        self.assertIn("  group: nexo-scheduled-persistence-relay\n", block)
        self.assertIn("  cancel-in-progress: false\n", block)
        self.assertIn("  queue: max\n", block)
        self.assertIn("          ref: ${{ github.sha }}\n", workflow)
        self.assertIn("          fetch-depth: 0\n", workflow)
        self.assertIn("        if: always()\n", workflow)

    def test_three_waiting_pushes_deliver_event_versions_and_retry_without_duplicate(self):
        inbox = Inbox()
        with tempfile.TemporaryDirectory() as directory:
            old_cwd = Path.cwd()
            os.chdir(directory)
            try:
                def git(*args):
                    return subprocess.check_output(["git", *args], text=True).strip()
                git("init", "-q")
                git("config", "user.name", "Offline test")
                git("config", "user.email", "offline@example.invalid")
                Path("README").write_text("offline fixture")
                git("add", ".")
                git("commit", "-qm", "initial")
                before = git("rev-parse", "HEAD")
                requests = Path("nexo_persist/requests")
                requests.mkdir(parents=True)
                events = []
                # All three pushes exist before the first queued run starts.
                # The same source filename changes: checkout must use each event SHA.
                for number in range(3):
                    request = {"stable_id": f"offline-{number}", "envelope": {
                        "kind": "offline_fixture", "payload": {"number": number}}}
                    (requests / "request.json").write_text(json.dumps(request))
                    git("add", ".")
                    git("commit", "-qm", f"push {number}")
                    sha = git("rev-parse", "HEAD")
                    events.append((before, sha))
                    before = sha
                receipts = WriterReceipts({})
                expected = {}
                for before, sha in events:
                    git("checkout", "-q", "--detach", sha)
                    with patch.dict(os.environ, EVENT="push", BEFORE=before, GITHUB_SHA=sha):
                        changed = collect_changed()
                        self.assertEqual(changed, ["nexo_persist/requests/request.json"])
                        target, body = load_request(changed[0])
                        expected[target] = body
                        self.assertEqual(relay_one(inbox, receipts, target, body, sleep=lambda _: None),
                                         "recovered_after_uncertain_write")
                        receipts.acked[target] = hashlib.sha256(body.encode()).hexdigest()
                        self.assertEqual(relay_one(inbox, receipts, target, body, sleep=lambda _: None),
                                         "already_relayed_and_receipted")
                self.assertEqual(inbox.bodies, expected)
                self.assertEqual(len(inbox.bodies), 3)
                self.assertEqual(len(inbox.writes), 3)
            finally:
                os.chdir(old_cwd)


if __name__ == "__main__":
    unittest.main()
