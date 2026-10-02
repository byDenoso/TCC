"""Receipt, identity, and transport regressions for the persistence relay."""

import base64
import hashlib
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

try:
    from . import _relay_shared as shared
    from ._relay_shared import (
        ContentConflict,
        GitHubContents,
        ReadFailure,
        ReceiptDisposition,
        ReceiptLedgerUnavailable,
        StableIdConflict,
        StableIdValidationError,
        TerminalReceiptError,
        TerminalTransportError,
        WriterReceipts,
        relay_one,
        target_for_stable_id,
        validate_stable_id_collisions,
    )
except ImportError:  # unittest discovery with -s nexo_persist
    import _relay_shared as shared
    from _relay_shared import (
        ContentConflict,
        GitHubContents,
        ReadFailure,
        ReceiptDisposition,
        ReceiptLedgerUnavailable,
        StableIdConflict,
        StableIdValidationError,
        TerminalReceiptError,
        TerminalTransportError,
        WriterReceipts,
        relay_one,
        target_for_stable_id,
        validate_stable_id_collisions,
    )


TARGET = "inbox/scheduled-fixture.json"
BODY = '{"kind":"fixture","payload":{"value":"é"}}\n'
FINGERPRINT = hashlib.sha256(BODY.encode("utf-8")).hexdigest()


def meta(body, sha="file-sha"):
    return {"content": base64.b64encode(body.encode("utf-8")).decode("ascii"), "sha": sha}


def gh_ok(payload):
    return subprocess.CompletedProcess([], 0, json.dumps(payload), "")


def gh_error(status):
    return subprocess.CompletedProcess([], 1, "", f"gh: HTTP {status}: mocked response")


def gh_content(body, sha="file-sha"):
    encoded = base64.encodebytes(body.encode("utf-8")).decode("ascii")
    return {"content": encoded, "sha": sha}


class FakeContents:
    def __init__(self, gets=(), puts=()):
        self.gets = list(gets)
        self.put_results = list(puts)
        self.get_calls = []
        self.put_calls = []
        self.bodies = {}

    def get(self, target):
        self.get_calls.append(target)
        if self.gets:
            response = self.gets.pop(0)
            if response[0] == 200:
                self.bodies[target] = shared.decoded(response[1])
            elif response[0] == 404:
                self.bodies.pop(target, None)
            return response
        if target in self.bodies:
            return 200, meta(self.bodies[target])
        return 404, {}

    def put(self, target, body, sha=None):
        self.put_calls.append((target, body, sha))
        status, result = self.put_results.pop(0) if self.put_results else (200, {})
        if status in (200, 201):
            self.bodies[target] = body
        return status, result


class WriterReceiptTests(unittest.TestCase):
    def test_acked_legacy_string_and_dict_require_exact_canonical_hash(self):
        for value in (FINGERPRINT, {"fingerprint": "sha256:" + FINGERPRINT}):
            receipts = WriterReceipts(acked={TARGET: value})
            self.assertTrue(receipts.confirmed(TARGET, BODY))
            self.assertEqual(receipts.disposition(TARGET, BODY), ReceiptDisposition.MATCH)

    def test_durable_only_receipt_confirms_exact_bytes_without_destination_write(self):
        receipts = WriterReceipts(receipts={TARGET: {"fingerprint": FINGERPRINT}})
        transport = FakeContents()
        self.assertEqual(
            relay_one(transport, receipts, TARGET, BODY),
            "already_relayed_and_receipted",
        )
        self.assertEqual(transport.get_calls, [])
        self.assertEqual(transport.put_calls, [])

    def test_receipt_hash_mismatch_is_conflict_and_never_redelivered(self):
        receipts = WriterReceipts(receipts={TARGET: {"fingerprint": "0" * 64}})
        transport = FakeContents()
        with self.assertRaises(ContentConflict):
            relay_one(transport, receipts, TARGET, BODY)
        self.assertEqual(transport.put_calls, [])

    def test_ack_and_durable_receipt_disagreement_is_conflict(self):
        receipts = WriterReceipts(
            acked={TARGET: FINGERPRINT},
            receipts={TARGET: {"fingerprint": "0" * 64}},
        )
        with self.assertRaises(ContentConflict):
            relay_one(FakeContents(), receipts, TARGET, BODY)

    def test_terminal_rejection_blocks_even_matching_receipt_from_redelivery(self):
        receipts = WriterReceipts(
            receipts={TARGET: {"fingerprint": FINGERPRINT, "status": "REJECTED_TERMINAL"}}
        )
        transport = FakeContents()
        with self.assertRaises(TerminalReceiptError):
            relay_one(transport, receipts, TARGET, BODY)
        self.assertEqual(transport.put_calls, [])

    def test_top_level_rejection_ledger_blocks_delivery(self):
        receipts = WriterReceipts(rejected={TARGET: {"reason": "terminal"}})
        transport = FakeContents()
        with self.assertRaises(TerminalReceiptError):
            relay_one(transport, receipts, TARGET, BODY)
        self.assertEqual(transport.put_calls, [])

    def test_nested_terminal_effect_rejection_blocks_envelope_replay(self):
        receipts = WriterReceipts(
            receipts={
                TARGET: {
                    "fingerprint": FINGERPRINT,
                    "effects": [{"status": "REJECTED_TERMINAL", "effect": "ack"}],
                }
            }
        )
        transport = FakeContents()
        with self.assertRaises(TerminalReceiptError):
            relay_one(transport, receipts, TARGET, BODY)
        self.assertEqual(transport.put_calls, [])

    def test_unavailable_ledger_is_not_treated_as_absence(self):
        receipts = WriterReceipts(available=False, error="HTTP 403")
        transport = FakeContents()
        with self.assertRaises(ReceiptLedgerUnavailable):
            relay_one(transport, receipts, TARGET, BODY)
        self.assertEqual(transport.put_calls, [])
        self.assertEqual(transport.get_calls, [])

    def test_replay_after_writer_ack_does_not_put_twice(self):
        receipts = WriterReceipts()
        transport = FakeContents(gets=[(404, {})], puts=[(201, {})])
        self.assertEqual(relay_one(transport, receipts, TARGET, BODY), "relayed")
        receipts.acked[TARGET] = FINGERPRINT
        self.assertEqual(
            relay_one(transport, receipts, TARGET, BODY),
            "already_relayed_and_receipted",
        )
        self.assertEqual(len(transport.put_calls), 1)

    def test_missing_ledger_is_distinct_from_read_failure(self):
        client = GitHubContents("owner/repo", branch="main")
        responses = [
            subprocess.CompletedProcess([], 1, "", "HTTP 404 Not Found"),
            subprocess.CompletedProcess([], 0, '{"full_name":"owner/repo"}', ""),
        ]
        with patch.object(shared.subprocess, "run", side_effect=responses):
            receipts = WriterReceipts.load(client=client)
        self.assertTrue(receipts.available)
        self.assertEqual(receipts.disposition(TARGET, BODY), ReceiptDisposition.ABSENT)

    def test_private_repo_masked_as_404_is_not_treated_as_empty_ledger(self):
        client = GitHubContents("owner/private", branch="main")
        requests = []

        def mocked_gh(args, **kwargs):
            endpoint = args[2]
            requests.append(endpoint)
            if endpoint == f"repos/owner/private/contents/{shared.ACK_PATH}?ref=main":
                return subprocess.CompletedProcess([], 1, "", "HTTP 404 Not Found")
            if endpoint == "repos/owner/private":
                return subprocess.CompletedProcess([], 1, "", "HTTP 404 Not Found")
            if endpoint == "repos/byDenoso/Pantheon":
                # The default ledger repository is accessible, but it is not
                # the repository whose contents request returned 404.
                return subprocess.CompletedProcess([], 0, '{"full_name":"byDenoso/Pantheon"}', "")
            raise AssertionError(f"unexpected mocked GitHub endpoint: {endpoint}")

        with patch.object(shared.subprocess, "run", side_effect=mocked_gh):
            receipts = WriterReceipts.load(client=client)
        self.assertFalse(receipts.available)
        self.assertEqual(receipts.disposition(TARGET, BODY), ReceiptDisposition.UNAVAILABLE)
        self.assertEqual(requests, [
            f"repos/owner/private/contents/{shared.ACK_PATH}?ref=main",
            "repos/owner/private",
        ])

    def test_auth_failure_loading_ledger_is_unavailable_and_cannot_write(self):
        client = GitHubContents("owner/repo", branch="main")
        response = subprocess.CompletedProcess([], 1, "", "HTTP 403 Resource not accessible")
        with patch.object(shared.subprocess, "run", return_value=response):
            receipts = WriterReceipts.load(client=client)
        self.assertFalse(receipts.available)
        transport = FakeContents()
        with self.assertRaises(ReceiptLedgerUnavailable):
            relay_one(transport, receipts, TARGET, BODY)
        self.assertEqual(transport.put_calls, [])

    def test_real_contents_transport_loads_durable_receipt_from_canonical_bytes(self):
        document = {"acked": {}, "receipts": {TARGET: {"fingerprint": FINGERPRINT}}}
        content = base64.encodebytes(json.dumps(document).encode("utf-8")).decode("ascii")
        self.assertIn("\n", content)
        client = GitHubContents("byDenoso/Pantheon", branch="main")
        destination = GitHubContents("owner/inbox")
        response = subprocess.CompletedProcess([], 0, json.dumps({"content": content}), "")
        with patch.object(shared.subprocess, "run", return_value=response) as run:
            receipts = WriterReceipts.load(client=client)
            outcome = relay_one(destination, receipts, TARGET, BODY)
        self.assertEqual(outcome, "already_relayed_and_receipted")
        self.assertTrue(receipts.confirmed(TARGET, BODY))
        args = run.call_args.args[0]
        self.assertEqual(args[:3], ["gh", "api", f"repos/byDenoso/Pantheon/contents/{shared.ACK_PATH}?ref=main"])
        self.assertEqual(run.call_count, 1)  # the durable receipt avoids destination I/O

    def test_real_contents_transport_hash_mismatch_fails_before_destination_io(self):
        document = {"acked": {}, "receipts": {TARGET: {"fingerprint": "0" * 64}}}
        response = gh_ok({"content": base64.b64encode(json.dumps(document).encode()).decode("ascii")})
        with patch.object(shared.subprocess, "run", return_value=response) as run:
            receipts = WriterReceipts.load(client=GitHubContents("byDenoso/Pantheon", branch="main"))
            with self.assertRaises(ContentConflict):
                relay_one(GitHubContents("owner/inbox"), receipts, TARGET, BODY)
        self.assertEqual(run.call_count, 1)

    def test_real_contents_transport_replay_after_ack_does_not_put_twice(self):
        empty = {"acked": {}, "receipts": {}}
        ledger_response = gh_ok({"content": base64.b64encode(json.dumps(empty).encode()).decode("ascii")})
        responses = [ledger_response, gh_error(404), gh_ok({"content": "ignored"}), gh_ok(gh_content(BODY))]
        with patch.object(shared.subprocess, "run", side_effect=responses) as run:
            receipts = WriterReceipts.load(client=GitHubContents("byDenoso/Pantheon", branch="main"))
            self.assertEqual(
                relay_one(GitHubContents("owner/inbox"), receipts, TARGET, BODY),
                "relayed",
            )
            receipts.acked[TARGET] = FINGERPRINT  # Writer's later durable acknowledgement
            self.assertEqual(
                relay_one(GitHubContents("owner/inbox"), receipts, TARGET, BODY),
                "already_relayed_and_receipted",
            )
        self.assertEqual(run.call_count, 4)
        put_calls = [call for call in run.call_args_list if "--method" in call.args[0]]
        self.assertEqual(len(put_calls), 1)


class GitHubCommandTransportTests(unittest.TestCase):
    def test_actual_gh_transport_recovers_409_winner(self):
        responses = [gh_error(404), gh_error(409), gh_ok(gh_content(BODY))]
        with patch.object(shared.subprocess, "run", side_effect=responses) as run:
            outcome = relay_one(GitHubContents("owner/inbox"), WriterReceipts(), TARGET, BODY)
        self.assertEqual(outcome, "recovered_after_uncertain_write")
        self.assertEqual(run.call_count, 3)

    def test_actual_gh_transport_recovers_timeout_after_commit(self):
        responses = [
            gh_error(404),
            subprocess.TimeoutExpired(cmd="gh api", timeout=30),
            gh_ok(gh_content(BODY)),
        ]
        with patch.object(shared.subprocess, "run", side_effect=responses) as run:
            outcome = relay_one(GitHubContents("owner/inbox"), WriterReceipts(), TARGET, BODY)
        self.assertEqual(outcome, "recovered_after_uncertain_write")
        self.assertEqual(run.call_count, 3)

    def test_actual_gh_transport_retries_timeout_only_after_missing_readback(self):
        responses = [
            gh_error(404),
            subprocess.TimeoutExpired(cmd="gh api", timeout=30),
            gh_error(404),
            gh_ok({"content": "ignored"}),
            gh_ok(gh_content(BODY)),
        ]
        with patch.object(shared.subprocess, "run", side_effect=responses) as run:
            outcome = relay_one(
                GitHubContents("owner/inbox"), WriterReceipts(), TARGET, BODY, sleep=lambda _: None
            )
        self.assertEqual(outcome, "relayed")
        self.assertEqual(run.call_count, 5)

    def test_actual_gh_transport_auth_rejection_is_terminal_without_retry(self):
        responses = [gh_error(404), gh_error(403)]
        with patch.object(shared.subprocess, "run", side_effect=responses) as run:
            with self.assertRaises(TerminalTransportError):
                relay_one(GitHubContents("owner/inbox"), WriterReceipts(), TARGET, BODY)
        self.assertEqual(run.call_count, 2)


class TransportAndReadbackTests(unittest.TestCase):
    def test_409_winner_is_recovered_by_matching_readback(self):
        transport = FakeContents(gets=[(404, {}), (200, meta(BODY))], puts=[(409, {})])
        self.assertEqual(
            relay_one(transport, WriterReceipts(), TARGET, BODY),
            "recovered_after_uncertain_write",
        )
        self.assertEqual(len(transport.put_calls), 1)

    def test_timeout_after_commit_is_recovered_by_readback(self):
        transport = FakeContents(gets=[(404, {}), (200, meta(BODY))], puts=[(0, {})])
        self.assertEqual(
            relay_one(transport, WriterReceipts(), TARGET, BODY),
            "recovered_after_uncertain_write",
        )
        self.assertEqual(len(transport.put_calls), 1)

    def test_timeout_before_commit_retries_only_after_successful_missing_readback(self):
        transport = FakeContents(
            gets=[(404, {}), (404, {}), (200, meta(BODY))],
            puts=[(0, {}), (201, {})],
        )
        self.assertEqual(relay_one(transport, WriterReceipts(), TARGET, BODY, sleep=lambda _: None), "relayed")
        self.assertEqual(len(transport.put_calls), 2)

    def test_destination_read_auth_failure_is_terminal_without_write(self):
        for status in (401, 403):
            transport = FakeContents(gets=[(status, {})])
            with self.subTest(status=status), self.assertRaises(TerminalTransportError):
                relay_one(transport, WriterReceipts(), TARGET, BODY)
            self.assertEqual(transport.put_calls, [])

    def test_destination_read_server_error_or_timeout_is_not_absence(self):
        for status in (0, 503):
            transport = FakeContents(gets=[(status, {})])
            with self.subTest(status=status), self.assertRaises(ReadFailure):
                relay_one(transport, WriterReceipts(), TARGET, BODY)
            self.assertEqual(transport.put_calls, [])

    def test_write_auth_failure_is_terminal_without_escalation_or_retry(self):
        for status in (401, 403):
            transport = FakeContents(gets=[(404, {})], puts=[(status, {})])
            with self.subTest(status=status), self.assertRaises(TerminalTransportError):
                relay_one(transport, WriterReceipts(), TARGET, BODY)
            self.assertEqual(len(transport.put_calls), 1)

    def test_destination_with_same_id_and_different_bytes_is_conflict(self):
        transport = FakeContents(gets=[(200, meta('{"kind":"other"}\n'))])
        with self.assertRaises(ContentConflict):
            relay_one(transport, WriterReceipts(), TARGET, BODY)
        self.assertEqual(transport.put_calls, [])


class StableIdTests(unittest.TestCase):
    def test_legacy_ids_keep_the_existing_target_mapping(self):
        self.assertEqual(target_for_stable_id("Old_Request_1"), "inbox/scheduled-old-request-1.json")

    def test_truncated_or_normalised_identity_collision_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            first = Path(directory) / "one.json"
            second = Path(directory) / "two.json"
            first.write_text(json.dumps({"stable_id": "A_B", "kind": "x", "payload": {}}), encoding="utf-8")
            second.write_text(json.dumps({"stable_id": "a-b", "kind": "x", "payload": {}}), encoding="utf-8")
            with self.assertRaises(StableIdConflict):
                validate_stable_id_collisions([first, second])

    def test_long_legacy_prefix_collision_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            first = Path(directory) / "one.json"
            second = Path(directory) / "two.json"
            first.write_text(json.dumps({"stable_id": "a" * 60 + "x", "kind": "x", "payload": {}}), encoding="utf-8")
            second.write_text(json.dumps({"stable_id": "a" * 60 + "y", "kind": "x", "payload": {}}), encoding="utf-8")
            with self.assertRaises(StableIdConflict):
                validate_stable_id_collisions([first, second])

    def test_non_string_or_unusable_stable_id_is_rejected(self):
        with self.assertRaises(StableIdValidationError):
            target_for_stable_id(123)
        with self.assertRaises(StableIdValidationError):
            target_for_stable_id("!!!")


if __name__ == "__main__":
    unittest.main()
