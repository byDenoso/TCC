from __future__ import annotations

import json
import copy
import tempfile
import unittest
from pathlib import Path

from runtime.nexo_agent_api import operation_receipts as receipts
from runtime.nexo_agent_api.gpt_writer import _emit_gateway_results, _gateway_results, apply_to_tower
from runtime.nexo_agent_api.live_tower import (
    build_live_tower_payload,
    materialize_live_tower,
    read_live_tower_bytes,
    verify_live_tower,
)


class OperationReceiptTests(unittest.TestCase):
    def receipt(self, *, outcome="APPLIED", retry_condition=None):
        return receipts.build_receipt(
            intent="gateway:stable-item",
            payload_sha256=receipts.payload_hash({"kind": "BOARD_POST", "_semantic": "keep-me"}),
            effect="effect-1",
            outcome=outcome,
            source_revision="sha256:" + "1" * 64,
            result_revision="sha256:" + "2" * 64,
            reason_code="PRIVATE_VALIDATION_DETAIL",
            retry_condition=retry_condition,
        )

    def test_payload_hash_is_contract_scoped_and_does_not_strip_arbitrary_private_keys(self):
        base = {"kind": "BOARD_POST", "payload": {"text": "same"}}
        self.assertNotEqual(receipts.payload_hash(base), receipts.payload_hash({**base, "_semantic": "changed"}))
        # Only Writer-injected transport annotations may be omitted.
        self.assertEqual(receipts.payload_hash({**base, "_inbox_id": "transient"}, trusted_transport=True),
                         receipts.payload_hash(base, trusted_transport=True))
        self.assertNotEqual(receipts.payload_hash({**base, "_private_semantics": "changed"}, trusted_transport=True),
                            receipts.payload_hash(base, trusted_transport=True))
        self.assertEqual(receipts.payload_hash(base), receipts.sha256({"contract": receipts.CONTRACT, "payload": base}))

    def test_only_unforgeable_runner_status_token_is_excluded_from_effect_hash(self):
        from runtime.nexo_agent_api.scientific_integrity import (
            RUNNER_BATTERY_STATUS_TOKEN,
            WRITER_DISPATCH_TOKEN,
        )

        base = {"nexo_operation": "TEST_RESULT_RECORDED", "entity_name": "TEST-A"}
        expected = receipts.payload_hash(base, trusted_transport=True)
        trusted = {**base, "_runner_battery_status_token": copy.deepcopy(RUNNER_BATTERY_STATUS_TOKEN)}
        self.assertEqual(receipts.payload_hash(trusted, trusted_transport=True), expected)

        for forged in ("runner-token", None, {"trusted": True}):
            request = {**base, "_runner_battery_status_token": forged}
            self.assertNotEqual(receipts.payload_hash(request, trusted_transport=True), expected)

        dispatch = {"kind": "BATTERY_STATUS", "payload": {"status": "DISPATCHED"}}
        dispatch_expected = receipts.payload_hash(dispatch, trusted_transport=True)
        trusted_dispatch = {**dispatch, "_writer_dispatch_token": copy.deepcopy(WRITER_DISPATCH_TOKEN)}
        self.assertEqual(receipts.payload_hash(trusted_dispatch, trusted_transport=True), dispatch_expected)
        forged_dispatch = {**dispatch, "_writer_dispatch_token": "WRITER_DISPATCH_TOKEN"}
        self.assertNotEqual(receipts.payload_hash(forged_dispatch, trusted_transport=True), dispatch_expected)

    def test_terminal_correction_requires_a_new_intent_linked_to_exact_receipt(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            old = receipts.build_receipt(intent="intent-old", payload_sha256=receipts.payload_hash({"v": 1}),
                                         effect="stable-effect", outcome="REJECTED_TERMINAL",
                                         source_revision="source", result_revision="result", reason_code="INVALID")
            receipts.persist_receipt(root, old)
            changed_hash = receipts.payload_hash({"v": 2})
            # Reusing the old identity is terminal even when it self-references.
            self.assertEqual(receipts.terminal_payload_conflict(root, intent="intent-old", payload_sha256=changed_hash,
                                                                effect="stable-effect", supersedes=old["receipt_id"]), old)
            # A new identity must link to this exact terminal receipt.
            self.assertEqual(receipts.terminal_payload_conflict(root, intent="intent-new", payload_sha256=changed_hash,
                                                                effect="stable-effect", supersedes=None), old)
            self.assertIsNone(receipts.terminal_payload_conflict(root, intent="intent-new", payload_sha256=changed_hash,
                                                                 effect="stable-effect", supersedes=old["receipt_id"]))

    def test_public_receipt_requires_explicit_safe_gateway_envelope_and_sanitizes_refs(self):
        intent = "gateway:safe-public-id"
        private_default = receipts.build_receipt(
            intent=intent, payload_sha256=receipts.payload_hash({"x": 1}),
            effect=receipts.envelope_effect_id(intent), outcome="APPLIED",
            source_revision="sha256:" + "1" * 64, result_revision="sha256:" + "2" * 64,
        )
        self.assertIsNone(receipts.public_receipt(private_default))

        unsafe_effect = receipts.build_receipt(
            intent=intent, payload_sha256=receipts.payload_hash({"x": 1}), effect="WORK::PRIVATE_ID",
            outcome="APPLIED", source_revision="sha256:" + "1" * 64,
            result_revision="sha256:" + "2" * 64, visibility="PUBLIC",
        )
        self.assertIsNone(receipts.public_receipt(unsafe_effect))

        public = receipts.build_receipt(
            intent=intent, payload_sha256=receipts.payload_hash({"x": 1}),
            effect=receipts.envelope_effect_id(intent), outcome="APPLIED",
            source_revision="sha256:" + "1" * 64, result_revision="sha256:" + "2" * 64,
            visibility="PUBLIC",
        )
        public["supersedes"] = "DRIVE::PRIVATE_RECEIPT_REFERENCE"
        exported = receipts.public_receipt(public)
        self.assertIsNotNone(exported)
        self.assertIsNone(exported["supersedes"])
        public["source_revision"] = "PRIVATE::REVISION_SENTINEL"
        self.assertIsNone(receipts.public_receipt(public))

    def test_corrupt_current_receipt_is_a_ledger_error_not_a_missing_receipt(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            target = root / "operations" / "receipts" / "broken.json"
            target.parent.mkdir(parents=True)
            target.write_text(json.dumps({"outcome": "APPLIED"}), encoding="utf-8")
            with self.assertRaisesRegex(receipts.OperationReceiptError, "LEDGER_INVALID"):
                receipts.load_receipts(root)

    def test_dependency_context_tracks_exact_depends_on_test_not_unrelated_tests(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            request = {"entity_kind": "test", "entity_name": "TEST-ROOT",
                       "changes": {"depends_on": ["TEST-DEPENDENCY"]}}
            before = receipts.dependency_context_revision(root, request, "DEPENDENCY_UNRESOLVED")
            unrelated = root / "entities" / "test" / "TEST-UNRELATED.json"
            unrelated.parent.mkdir(parents=True, exist_ok=True)
            unrelated.write_text(json.dumps({"id": "TEST-UNRELATED", "status": "READY"}), encoding="utf-8")
            self.assertEqual(receipts.dependency_context_revision(root, request, "DEPENDENCY_UNRESOLVED"), before)
            dependency = root / "entities" / "test" / "TEST-DEPENDENCY.json"
            dependency.write_text(json.dumps({"id": "TEST-DEPENDENCY", "status": "READY"}), encoding="utf-8")
            after = receipts.dependency_context_revision(root, request, "DEPENDENCY_UNRESOLVED")
            self.assertNotEqual(after, before)
            self.assertTrue(receipts.retry_allowed({"outcome": "DEFERRED_DEPENDENCY", "source_revision": before,
                                                    "retry_condition": {"kind": "SOURCE_REVISION_CHANGED"}}, after))

    def test_receipt_round_trips_in_the_private_live_tower_and_public_export_is_allowlisted(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "source"
            source.mkdir()
            (source / "CONTROL.json").write_text(json.dumps({"truth_owner": "TOWER_V06@GOOGLE_DRIVE_PRIVATE"}), encoding="utf-8")
            private = self.receipt(outcome="RETRYABLE_TRANSPORT",
                                   retry_condition={"kind": "OPERATOR_REAUTHORIZATION", "detail": "private credential diagnostics"})
            receipts.persist_receipt(source, private)
            canary_path = source / "operational" / "operational_canary.json"
            canary_path.parent.mkdir(parents=True)
            canary_path.write_text(json.dumps({"contract": "OPERATIONAL_CANARY_V1", "visibility": "PRIVATE",
                                               "secret_metric_detail": "must stay in Tower"}), encoding="utf-8")
            raw = json.dumps(build_live_tower_payload(source), ensure_ascii=False).encode("utf-8")
            bundle = read_live_tower_bytes(raw)
            self.assertIn("operations/receipts/" + private["receipt_id"] + ".json", bundle["files"])
            self.assertIn("operational/operational_canary.json", bundle["files"])
            self.assertEqual(verify_live_tower(bundle), bundle["state_fingerprint"])

            restored, _ = materialize_live_tower(raw, Path(temporary) / "restored")
            [loaded] = receipts.load_receipts(restored)
            self.assertEqual(loaded, private)
            self.assertIsNone(receipts.public_receipt(loaded))

            public_gateway = receipts.build_receipt(
                intent="gateway:stable-item",
                payload_sha256=receipts.payload_hash({"kind": "BOARD_POST", "_semantic": "keep-me"}),
                effect=receipts.envelope_effect_id("gateway:stable-item"),
                outcome="RETRYABLE_TRANSPORT",
                source_revision="sha256:" + "1" * 64,
                result_revision=None,
                reason_code="PRIVATE_VALIDATION_DETAIL",
                retry_condition={"kind": "OPERATOR_REAUTHORIZATION", "detail": "private credential diagnostics"},
                visibility="PUBLIC",
            )
            exported = receipts.public_receipt(public_gateway)
            self.assertIsNotNone(exported)
            self.assertEqual(exported["visibility"], "PUBLIC")
            self.assertEqual(exported["retry_condition"], {"kind": "OPERATOR_REAUTHORIZATION"})
            self.assertEqual(exported["intent_id"], "gateway:stable-item")
            self.assertEqual(exported["payload_sha256"], public_gateway["payload_sha256"])
            self.assertEqual(exported["effect_id"], receipts.envelope_effect_id("gateway:stable-item"))
            self.assertIsNone(exported["reason_code"])
            self.assertNotIn("detail", json.dumps(exported))
            self.assertNotIn("secret_metric_detail", json.dumps(exported))
            schema_path = Path(__file__).resolve().parents[1] / "runtime" / "nexo_agent_api" / "contracts" / "OPERATION_RECEIPT_V1.json"
            schema = json.loads(schema_path.read_text(encoding="utf-8"))
            self.assertEqual(set(exported), set(schema["required"]))
            self.assertEqual(set(exported), {
                "contract", "receipt_id", "intent_id", "payload_sha256", "effect_id", "stage", "outcome",
                "reason_code", "source_revision", "result_revision", "occurred_at", "observed_at", "visibility",
                "retry_condition", "supersedes",
            })

    def test_writer_gateway_export_keeps_only_public_envelope_identity(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "tower"
            root.mkdir()
            (root / "CONTROL.json").write_text(json.dumps({
                "truth_owner": "TOWER_V06@GOOGLE_DRIVE_PRIVATE",
            }), encoding="utf-8")
            gateway_id = "safe-gateway-123"
            private_request_id = "WORK::PRIVATE_EFFECT_REQUEST_SENTINEL"
            private_work_id = "WORK::PRIVATE_ENTITY_SENTINEL"
            drive_id = "DRIVE_FILE_PRIVATE_SENTINEL"
            unsafe_gateway_id = "private/path-sentinel"
            items = [
                {
                    "entity_kind": "work", "entity_name": private_work_id, "expected_version": 0,
                    "writer_role": "INVALID_ROLE", "event_type": "TEST_TERMINAL_MISSING_ENTITY",
                    "changes": {"status": "READY"}, "request_id": private_request_id,
                    "_inbox_source": "GATEWAY", "_inbox_name": "gw-" + gateway_id,
                    "_inbox_id": "gateway:" + gateway_id,
                },
                {
                    "entity_kind": "work", "entity_name": "WORK::DRIVE_PRIVATE_ENTITY_SENTINEL",
                    "expected_version": 0, "writer_role": "INVALID_ROLE",
                    "event_type": "TEST_TERMINAL_MISSING_ENTITY", "changes": {"status": "READY"},
                    "request_id": "DRIVE::PRIVATE_EFFECT_REQUEST_SENTINEL",
                    "_inbox_source": "DRIVE", "_inbox_name": drive_id,
                    # Even a gateway-looking inbox id cannot override private Drive provenance.
                    "_inbox_id": "gateway:drive-spoof-456",
                },
                {
                    "entity_kind": "work", "entity_name": "WORK::NONCANONICAL_ENTITY_SENTINEL",
                    "expected_version": 0, "writer_role": "INVALID_ROLE",
                    "event_type": "TEST_TERMINAL_MISSING_ENTITY", "changes": {"status": "READY"},
                    "request_id": "WORK::NONCANONICAL_EFFECT_SENTINEL",
                    "_inbox_source": "GATEWAY", "_inbox_name": "gw-" + unsafe_gateway_id,
                    "_inbox_id": "gateway:" + unsafe_gateway_id,
                },
            ]
            raw = json.dumps(build_live_tower_payload(root), ensure_ascii=False).encode("utf-8")
            _packed, report = apply_to_tower(raw, items)

            public_rows = report["public_operation_receipts"]
            self.assertEqual(len(public_rows), 1)
            [public_row] = public_rows
            self.assertEqual(public_row["visibility"], "PUBLIC")
            self.assertEqual(public_row["intent_id"], "gateway:" + gateway_id)
            self.assertEqual(public_row["effect_id"], receipts.envelope_effect_id("gateway:" + gateway_id))
            self.assertEqual(public_row["payload_sha256"], receipts.payload_hash(items[0], trusted_transport=True))

            private_rendered = json.dumps(report["operation_receipts"], ensure_ascii=False)
            self.assertIn(private_work_id, json.dumps(items, ensure_ascii=False))
            self.assertIn(drive_id, json.dumps(items, ensure_ascii=False))
            for secret in (private_request_id, "DRIVE::PRIVATE_EFFECT_REQUEST_SENTINEL", unsafe_gateway_id):
                self.assertIn(secret, private_rendered)
            for secret in (private_request_id, private_work_id, drive_id,
                           "DRIVE::PRIVATE_EFFECT_REQUEST_SENTINEL", unsafe_gateway_id):
                self.assertNotIn(secret, json.dumps(public_rows, ensure_ascii=False))

            gateway_ids = [gateway_id, "drive-spoof-456", unsafe_gateway_id]
            payload, reported, resolved = _gateway_results(report, gateway_ids)
            self.assertEqual(reported, [gateway_id])
            self.assertEqual(resolved, [gateway_id])
            self.assertEqual(len(payload["items"]), 1)
            [exported_item] = payload["items"]
            self.assertEqual(exported_item["id"], gateway_id)
            self.assertEqual(exported_item["intent_id"], "gateway:" + gateway_id)
            self.assertEqual(exported_item["receipts"], [public_row])
            rendered = json.dumps(payload, ensure_ascii=False)
            for secret in (private_request_id, private_work_id, drive_id,
                           "DRIVE::PRIVATE_EFFECT_REQUEST_SENTINEL", unsafe_gateway_id,
                           "WORK::PRIVATE_EFFECT_SENTINEL"):
                self.assertNotIn(secret, rendered)

            out_path = Path(temporary) / "gateway-results.json"
            output_path = Path(temporary) / "github-output.txt"
            emitted, emitted_resolved = _emit_gateway_results(
                report, gateway_ids, path=str(out_path), output=str(output_path),
            )
            self.assertEqual(emitted, [gateway_id])
            self.assertEqual(emitted_resolved, [gateway_id])
            self.assertEqual(json.loads(out_path.read_text(encoding="utf-8")), payload)
            self.assertEqual(output_path.read_text(encoding="utf-8"),
                             "gateway_reported=" + gateway_id + "\ngateway_resolved=" + gateway_id + "\n")

    def test_actual_public_projection_omits_private_receipt_and_canary_documents(self):
        from runtime.nexo_agent_api.public_projection import build_public_projection
        from runtime.nexo_agent_api.test_public_projection import _tower

        with tempfile.TemporaryDirectory() as temporary:
            root = _tower(Path(temporary))
            private = self.receipt(outcome="RETRYABLE_TRANSPORT",
                                   retry_condition={"kind": "OPERATOR_REAUTHORIZATION", "detail": "private credential diagnostics"})
            receipts.persist_receipt(root, private)
            canary_path = root / "operational" / "operational_canary.json"
            canary_path.parent.mkdir(parents=True)
            canary_path.write_text(json.dumps({"contract": "OPERATIONAL_CANARY_V1", "visibility": "PRIVATE",
                                               "secret_metric_detail": "private canary evidence"}), encoding="utf-8")
            projection = build_public_projection(root, generated_at="2026-10-02T00:00:00Z")
            rendered = json.dumps(projection, ensure_ascii=False, sort_keys=True)
            for secret in ("PRIVATE_VALIDATION_DETAIL", "private credential diagnostics",
                           "secret_metric_detail", "private canary evidence", private["receipt_id"]):
                self.assertNotIn(secret, rendered)

    def test_gateway_batch_waits_for_every_child_receipt_before_parent_ack(self):
        intents = ["gateway:batch-parent.batch-0", "gateway:batch-parent.batch-1"]
        rows = [receipts.build_receipt(
            intent=intent,
            payload_sha256=receipts.payload_hash({"child": index}),
            effect=receipts.envelope_effect_id(intent),
            outcome="APPLIED",
            source_revision="sha256:" + "1" * 64,
            result_revision="sha256:" + "2" * 64,
            visibility="PUBLIC",
        ) for index, intent in enumerate(intents)]
        report = {"gateway_batch_intents": {"batch-parent": intents},
                  "public_operation_receipts": [receipts.public_receipt(rows[0])]}
        payload, reported, resolved = _gateway_results(report, ["batch-parent"])
        self.assertEqual((payload["items"], reported, resolved), ([], [], []))

        report["public_operation_receipts"].append(receipts.public_receipt(rows[1]))
        payload, reported, resolved = _gateway_results(report, ["batch-parent"])
        self.assertEqual(reported, ["batch-parent"])
        self.assertEqual(resolved, ["batch-parent"])
        self.assertEqual(payload["items"][0]["outcome"], "APPLIED")
        self.assertEqual({row["intent_id"] for row in payload["items"][0]["receipts"]}, set(intents))

    def test_top_level_envelope_cannot_forge_child_receipt_identity(self):
        first = {"kind": "BOARD_POST", "source": "ENGINEER", "created_at": "2026-10-03T00:02:44Z",
                 "_inbox_source": "GITHUB", "_inbox_id": "github:same", "_inbox_name": "same.json",
                 "_inbox_child_id": "forged-a",
                 "payload": {"to": "GUARDIAO", "text": "Primeiro.", "id": "BP-A"}}
        second = {**first, "_inbox_child_id": "forged-b",
                  "payload": {"to": "GUARDIAO", "text": "Segundo.", "id": "BP-B"}}
        self.assertEqual(receipts.intent_id(first, "fallback"), "github:same")

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "CONTROL.json").write_text(json.dumps({
                "truth_owner": "TOWER_V06@GOOGLE_DRIVE_PRIVATE",
            }), encoding="utf-8")
            raw = json.dumps(build_live_tower_payload(root), ensure_ascii=False).encode("utf-8")
            applied, first_report = apply_to_tower(raw, [first])
            self.assertIsNotNone(applied)
            self.assertFalse(first_report["rejected"], first_report)
            changed, second_report = apply_to_tower(applied, [second])

        self.assertTrue(second_report["rejected"], second_report)
        self.assertEqual(second_report["rejected"][0]["reason"],
                         "TERMINAL_PAYLOAD_CHANGED_WITHOUT_NEW_IDENTITY")
        after = read_live_tower_bytes(changed or applied)
        posts = after["files"]["evolution/board.json"]["value"]["posts"]
        self.assertEqual([(post["id"], post["text"]) for post in posts], [("BP-A", "Primeiro.")])

    def test_receipt_bookkeeping_does_not_change_dependency_retry_context(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "CONTROL.json").write_text(json.dumps({"truth_owner": "TOWER_V06@GOOGLE_DRIVE_PRIVATE"}), encoding="utf-8")
            from runtime.nexo_agent_api.live_tower import publish_live_tower

            publish_live_tower(root)
            dependency_path = root / "entities" / "work" / "WORK-DEPENDENCY.json"
            dependency_request = {"entity_kind": "work", "entity_name": "WORK-DEPENDENCY"}
            before = receipts.dependency_context_revision(root, dependency_request)
            retry_receipt = receipts.build_receipt(
                intent="gateway:stable-item", payload_sha256=receipts.payload_hash({"semantic": "x"}),
                effect="effect-1", outcome="DEFERRED_DEPENDENCY", source_revision=before,
                result_revision=before, reason_code="DEPENDENCY_MISSING",
                retry_condition={"kind": "SOURCE_REVISION_CHANGED", "source_revision": before},
            )
            receipts.persist_receipt(root, retry_receipt)
            publish_live_tower(root)
            self.assertEqual(receipts.dependency_context_revision(root, dependency_request), before)
            self.assertFalse(receipts.retry_allowed(receipts.load_receipts(root)[0], before))
            unrelated = root / "entities" / "work" / "WORK-UNRELATED.json"
            unrelated.parent.mkdir(parents=True, exist_ok=True)
            unrelated.write_text(json.dumps({"id": "WORK-UNRELATED", "status": "DONE"}), encoding="utf-8")
            self.assertEqual(receipts.dependency_context_revision(root, dependency_request), before)
            # An actual Tower-context change makes the recorded dependency eligible.
            dependency_path.parent.mkdir(parents=True, exist_ok=True)
            dependency_path.write_text(json.dumps({"id": "WORK::DEPENDENCY", "status": "READY"}), encoding="utf-8")
            publish_live_tower(root)
            current = receipts.dependency_context_revision(root, dependency_request)
            self.assertTrue(receipts.retry_allowed(receipts.load_receipts(root)[0], current))

    def test_terminal_proposal_replay_repairs_confirmation_without_another_tower_write(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "CONTROL.json").write_text(json.dumps({"mode": "ACTIVE", "truth_owner": "TOWER_V06@GOOGLE_DRIVE_PRIVATE"}), encoding="utf-8")
            raw = json.dumps(build_live_tower_payload(root)).encode("utf-8")
            proposal = {"entity_kind": "work", "entity_name": "WORK::MISSING", "expected_version": 0,
                        "writer_role": "INVALID_ROLE", "event_type": "TEST_TERMINAL_MISSING_ENTITY",
                        "changes": {"status": "READY"}, "request_id": "effect-terminal-item",
                        "_inbox_id": "gateway:terminal-item", "_inbox_source": "GATEWAY", "_inbox_name": "gw-terminal-item"}
            first, first_report = apply_to_tower(raw, [proposal])
            self.assertIsNotNone(first)
            envelope_effect = receipts.envelope_effect_id("gateway:terminal-item")
            first_envelope = next(row for row in first_report["public_operation_receipts"]
                                  if row["effect_id"] == envelope_effect)
            self.assertEqual(first_envelope["outcome"], "REJECTED_TERMINAL")
            second, second_report = apply_to_tower(first, [proposal])
            self.assertIsNone(second)
            self.assertEqual(second_report["handled"], ["gw-terminal-item"])
            second_envelope = next(row for row in second_report["public_operation_receipts"]
                                   if row["effect_id"] == envelope_effect)
            self.assertEqual(second_envelope["outcome"], "REJECTED_TERMINAL")
            self.assertNotEqual(second_envelope["observed_at"], first_envelope["observed_at"])
            self.assertEqual(second_envelope["occurred_at"], first_envelope["occurred_at"])


if __name__ == "__main__":
    unittest.main()
