"""Sanitized end-to-end regression for the staged NEXO Writer path.

The GitHub Contents API boundary is in-memory; request serialization, relay
readback, Writer materialization, battery reservation, runner result handling,
transition guards, receipts, and the public projection use the real runtime.
"""
from __future__ import annotations

import base64
import copy
import hashlib
import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

from nexo_persist import _relay_shared as relay
from runtime.nexo_agent_api import operation_receipts, scientific_integrity
from runtime.nexo_agent_api import evolution
from runtime.nexo_agent_api.gpt_writer import apply_to_tower
from runtime.nexo_agent_api.inbox_apply import proposal_to_requests
from runtime.nexo_agent_api.live_tower import (
    materialize_live_tower,
    read_live_tower_bytes,
    verify_live_tower,
)
from runtime.nexo_agent_api.public_projection import build_public_projection, verify_projection
from runtime.nexo_agent_api import tower_apply
from runtime.nexo_agent_api.tower_paths import entity_path
from tests import test_execution_phase_reconciliation as phase_fixture

END = phase_fixture.END
RUN_REF = phase_fixture.RUN_REF
TEST_ID = phase_fixture.TEST_ID


class _FakeGitHubContents:
    """Small GitHub Contents transport fake; no credentials or external calls."""

    def __init__(self) -> None:
        self.files: dict[str, tuple[str, str]] = {}

    def get(self, path: str) -> tuple[int, dict]:
        stored = self.files.get(path)
        if stored is None:
            return 404, {}
        body, sha = stored
        # GitHub may wrap the base64 returned by Contents API at 76 columns.
        content = base64.encodebytes(body.encode("utf-8")).decode("ascii")
        return 200, {"content": content, "sha": sha}

    def put(self, path: str, body: str, sha: str | None = None) -> tuple[int, dict]:
        previous = self.files.get(path)
        if sha is not None and (previous is None or previous[1] != sha):
            return 409, {"message": "content changed"}
        new_sha = hashlib.sha1(body.encode("utf-8")).hexdigest()
        self.files[path] = (body, new_sha)
        return (200 if previous else 201), {"content": {"sha": new_sha}}


class NexoOperationalPipelineTests(unittest.TestCase):
    def test_frozen_criterion_fixture_closes_operational_cycle_and_replays(self) -> None:
        self._exercise_contest_cycle(attack_positive=True)

    def test_successful_transport_with_inconclusive_attack_cannot_confirm(self) -> None:
        self._exercise_contest_cycle(attack_positive=False)

    def _exercise_contest_cycle(self, *, attack_positive: bool) -> None:
        """Exercise Writer mechanics, not scientific validation of data or independence.

        Positive observations below satisfy the unchanged fixture criterion. The
        transport-only control has ok=True but no conclusive scientific result.
        Neither branch runs a real campaign or establishes a scientific claim.
        """
        fixture = phase_fixture.ExecutionPhaseReconciliationTests()
        fixture.setUp()
        try:
            transport = _FakeGitHubContents()
            observations = [0.1, -0.3]
            self.assertEqual(fixture.test["success_criteria"], "abs(mean) < 1")
            self.assertEqual(fixture.test["kill_criteria"], "abs(mean) >= 1")

            def criterion_result(values):
                mean = sum(values) / len(values)
                passed = abs(mean) < 1
                return {"verdict": "PROMOTED" if passed else "REJECTED",
                        "decision": "PASS" if passed else "FAIL",
                        "statistics": {"mean": mean, "sample_size": len(values)},
                        "summary": "Isolated fixture criterion; no real scientific claim."}

            phase_fixture._save(fixture.root, "entities/evidence/cycle-sample-b.json",
                                {"id": "cycle-sample-b", "source": "synthetic-fixture-only",
                                 "seed": 23, "observations": observations})
            raw = fixture._initial_bundle()

            def deliver(stable_id, item, source):
                nonlocal raw
                _, delivered = self._stage(transport, fixture.temp_root, stable_id, item, source)
                raw, report = self._apply_writer_item(raw, delivered, "APPLIED")
                self.assertFalse(report["rejected"], report)
                return delivered, report

            deliver("cycle-reserve", fixture._battery_items(), "WRITER_ROBOT")
            deliver("cycle-running", fixture._running_item(), "RUNNER_OBSERVATION")
            with tempfile.TemporaryDirectory() as temp:
                root, _ = materialize_live_tower(raw, Path(temp) / "parent")
                completed = fixture._completed_item(root)
            completed["payload"]["results"][0]["result"] = criterion_result([0.2, 0.4])
            deliver("cycle-result", completed, "RUNNER_OBSERVATION")
            parent = phase_fixture._entity_from_bundle(raw)
            self.assertNotEqual(parent.get("review_state"), "CONFIRMED")

            # Provenance is an explicit isolated input, present before the attack freezes.
            attack_id = "CYCLE-INDEPENDENT-ATTACK"
            declaration = {"axis": "data", "evidence_refs": ["entities/evidence/cycle-sample-b.json"],
                           "frozen_at": END, "on_pass": "CONFIRMED", "on_fail": "REFUTED"}
            attack = {key: copy.deepcopy(value) for key, value in fixture.test.items()
                      if key not in {"id", "entity_version", "status", "state", "prereg_hash"}}
            attack.update(test_id=attack_id, frozen_at=END, dataset_and_selection="Independent generated sample B",
                          recipe_params={"seed": 23}, independence=declaration,
                          data_binding={"status": "BOUND", "inputs": [{"name": "sample", "kind": "generated",
                          "generator": "fixture-v1", "seed": 23, "sha256": "b" * 64}]})
            contest = {"kind": "CONTEST", "source": "REFEREE_1", "created_at": END,
                       "payload": {"test_id": TEST_ID, "reason": "Independent synthetic control", "contest_test": attack}}
            deliver("cycle-contest", contest, "GATEWAY")
            frozen_attack = phase_fixture._entity_from_bundle(raw, attack_id)
            self.assertEqual(frozen_attack["independence"], declaration)
            self.assertEqual(frozen_attack["prereg_hash"], evolution.prereg_hash(attack_id, frozen_attack))

            reserve = {"kind": "TEST_BATTERY", "created_at": END,
                       "payload": {"battery_id": "bat-cycle-attack", "tests": [
                           {"test_id": attack_id, "recipe": "audit_recipe", "params": {"seed": 23}}]}}
            deliver("cycle-attack-reserve", reserve, "WRITER_ROBOT")
            running = {"kind": "BATTERY_STATUS", "created_at": END,
                       "payload": {"battery_id": "bat-cycle-attack", "status": "RUNNING",
                                   "run_ref": "actions/runs/124", "started_tests": {attack_id: END}}}
            deliver("cycle-attack-running", running, "RUNNER_OBSERVATION")
            with tempfile.TemporaryDirectory() as temp:
                root, _ = materialize_live_tower(raw, Path(temp) / "attack")
                battery = next(b for b in scientific_integrity.batteries(root) if b["id"] == "bat-cycle-attack")
                spec = battery["tests"][0]
                self.assertTrue(scientific_integrity.independence(parent, frozen_attack, root)["eligible"])
            attack_end = "2026-09-30T10:02:00Z"
            attack_result = criterion_result(observations) if attack_positive else {
                "verdict": "INCONCLUSIVE", "decision": "SYNTHETIC_ONLY",
                "summary": "Operational success only; criterion outcome is unavailable."}
            result = {"kind": "BATTERY_STATUS", "created_at": attack_end,
                      "payload": {"battery_id": "bat-cycle-attack", "status": "DONE", "run_ref": "actions/runs/124",
                                  "completed_at": attack_end, "conclusion": "success", "results": [{
                                      "test_id": attack_id, "attempt_id": spec["attempt_id"],
                                      "recipe_sha256": spec["recipe_sha256"], "executed_at": attack_end, "ok": True,
                                      "result": attack_result}]}}
            result_item, result_report = deliver("cycle-attack-result", result, "RUNNER_OBSERVATION")
            final_parent = phase_fixture._entity_from_bundle(raw)
            final_attack = phase_fixture._entity_from_bundle(raw, attack_id)
            expected_review = "CONFIRMED" if attack_positive else "CONTESTED"
            self.assertEqual(final_parent["review_state"], expected_review)
            if attack_positive:
                self.assertEqual(final_parent["mechanical_contest_verdict"]["contest_test_id"], attack_id)
                self.assertTrue(final_parent["review_validation"]["eligible"])
                self.assertEqual(final_parent["review_validation"]["scope"],
                                 "FROZEN_DECLARATION_AND_RESOLVED_PROVENANCE_NOT_SCIENTIFIC_PROOF")
            else:
                self.assertEqual(final_attack["verdict"], "INCONCLUSIVE")
                self.assertEqual(final_attack["decision"], "SYNTHETIC_ONLY")
                self.assertNotIn("mechanical_contest_verdict", final_parent)
                self.assertNotEqual(final_parent.get("review_state"), "CONFIRMED")

            # Replay exactly the delivered result after a lost ACK, including its
            # stable intent and payload. A matching persisted receipt must be used:
            # no new Tower revision, semantic effect, or duplicate contest.
            _, replay_item = self._stage(
                transport, fixture.temp_root, "cycle-attack-result", result,
                "RUNNER_OBSERVATION", expected_relay_result="redelivered_missing_writer_receipt")
            self.assertEqual(replay_item, result_item)
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                replay_packed, replay_report = apply_to_tower(raw, [replay_item])
            self.assertIsNone(replay_packed, replay_report)
            revision = verify_live_tower(read_live_tower_bytes(raw))
            self.assertEqual(replay_report["before"], revision)
            self.assertEqual(replay_report["after"], revision)
            self.assertEqual(replay_report["handled"], ["cycle-attack-result"])
            self.assertEqual(replay_report["public_operation_receipts"], [])
            effect_id = operation_receipts.envelope_effect_id(result_item["_inbox_id"])
            original_receipt = next(r for r in result_report["operation_receipts"]
                                    if r["effect_id"] == effect_id)
            replay_receipt = next(r for r in replay_report["operation_receipts"]
                                  if r["effect_id"] == effect_id)
            self.assertEqual(replay_receipt["outcome"], "ALREADY_APPLIED")
            for field in ("effect_id", "intent_id", "payload_sha256", "occurred_at"):
                self.assertEqual(replay_receipt[field], original_receipt[field], field)
            self.assertEqual(len(final_parent["contests"]), 1)
            for before, after in [(fixture.test, final_parent), (frozen_attack, final_attack)]:
                for field in scientific_integrity.FROZEN:
                    self.assertEqual(before.get(field), after.get(field), field)
                self.assertEqual(before["prereg_hash"], after["prereg_hash"])
                self.assertEqual(after["execution_phase"], "COMPLETED")
            with tempfile.TemporaryDirectory() as temp:
                root, _ = materialize_live_tower(raw, Path(temp) / "consolidated")
                self.assertEqual(evolution.contest_chain_reconcile_requests(root), [])
                if attack_positive:
                    self.assertFalse(evolution.contest_requests(contest, contest["payload"], root, proposal_to_requests))
                projection = build_public_projection(root, tower_revision=verify_live_tower(read_live_tower_bytes(raw)), generated_at=attack_end)
                self.assertTrue(verify_projection(projection)[0])
                published = next(t for t in projection["tests"] if t["id"] == TEST_ID)
                self.assertEqual(published["review_state"], expected_review)
                self.assertEqual(published["claim_boundary"], fixture.test["claim_boundary"])
        finally:
            fixture.tearDown()

    def _stage(self, transport: _FakeGitHubContents, staging_root: Path,
               stable_id: str, item: dict, source: str,
               expected_relay_result: str = "relayed") -> tuple[bytes, dict]:
        envelope = {key: value for key, value in item.items() if not key.startswith("_inbox_")}
        request_path = staging_root / "nexo_persist" / "requests" / f"{stable_id}.json"
        request_path.parent.mkdir(parents=True, exist_ok=True)
        request_path.write_text(json.dumps({"stable_id": stable_id, "envelope": envelope}), encoding="utf-8")

        target, canonical_body = relay.load_request(request_path)
        self.assertEqual(target, f"inbox/scheduled-{stable_id}.json")
        self.assertEqual(
            canonical_body,
            json.dumps(envelope, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n",
        )
        self.assertEqual(
            relay.relay_one(transport, relay.WriterReceipts(), target, canonical_body, sleep=lambda _: None),
            expected_relay_result,
        )

        status, metadata = transport.get(target)
        self.assertEqual(status, 200)
        # Build the Writer input only from the bytes read back from the fake API.
        delivered = relay.decoded(metadata)
        self.assertEqual(delivered, canonical_body)
        writer_item = json.loads(delivered)
        writer_item.update(
            _inbox_id=f"gateway:{stable_id}",
            _inbox_name=f"gw-{stable_id}" if source == "GATEWAY" else stable_id,
            _inbox_source=source,
        )
        return canonical_body.encode("utf-8"), writer_item

    @staticmethod
    def _real_effect_requests(tower_raw: bytes, item: dict) -> list[dict]:
        """Read expected effects through the real converter on a disposable Tower copy."""
        if item.get("event_type"):
            return [item]
        with tempfile.TemporaryDirectory(prefix="nexo-pipeline-effects-") as temporary:
            root, _ = materialize_live_tower(tower_raw, Path(temporary) / "expected-effects")
            return proposal_to_requests(item, root)

    def _apply_writer_item(self, tower_raw: bytes, item: dict, expected_outcome: str) -> tuple[bytes, dict]:
        expected_effects = self._real_effect_requests(tower_raw, item)
        self.assertTrue(expected_effects)
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            packed, report = apply_to_tower(tower_raw, [item])
        self.assertIsNotNone(packed, report)
        assert packed is not None

        effect_receipts = report["operation_receipts"]
        by_effect = {row["effect_id"]: row for row in effect_receipts}
        self.assertEqual(len(by_effect), len(effect_receipts), effect_receipts)
        expected_ids = {request["request_id"] for request in expected_effects}
        self.assertTrue(expected_ids.issubset(by_effect), report)
        label = item.get("_inbox_name") or item.get("request_id") or "item-0"
        intent = operation_receipts.intent_id(item, str(label))
        envelope_effect = operation_receipts.envelope_effect_id(intent)
        self.assertIn(envelope_effect, by_effect)
        self.assertEqual(
            by_effect[envelope_effect]["payload_sha256"],
            operation_receipts.payload_hash(item, trusted_transport=True),
        )

        bundle = read_live_tower_bytes(packed)
        persisted = {
            entry["value"]["receipt_id"]: entry["value"]
            for entry in bundle["files"].values()
            if isinstance(entry.get("value"), dict)
            and entry["value"].get("contract") == operation_receipts.CONTRACT
        }
        for request in expected_effects:
            receipt = by_effect[request["request_id"]]
            self.assertEqual(receipt["intent_id"], intent)
            self.assertEqual(
                receipt["payload_sha256"],
                operation_receipts.payload_hash(request, trusted_transport=True),
            )
            self.assertRegex(receipt["source_revision"], r"^sha256:[0-9a-f]{64}$")
            self.assertRegex(receipt["result_revision"], r"^sha256:[0-9a-f]{64}$")
            self.assertEqual(receipt["outcome"], expected_outcome)
            self.assertEqual(receipt["visibility"], "PRIVATE")
            self.assertEqual(persisted.get(receipt["receipt_id"]), receipt)
        self.assertEqual(by_effect[envelope_effect]["outcome"], expected_outcome)
        self.assertEqual(persisted.get(by_effect[envelope_effect]["receipt_id"]), by_effect[envelope_effect])

        self.assertEqual(report["before"], verify_live_tower(read_live_tower_bytes(tower_raw)))
        self.assertEqual(report["after"], verify_live_tower(bundle))
        return packed, report

    def test_stale_terminal_phase_rolls_back_runner_done_and_continues_good_item(self) -> None:
        fixture = phase_fixture.ExecutionPhaseReconciliationTests()
        fixture.setUp()
        try:
            transport = _FakeGitHubContents()
            tower_raw = fixture._initial_bundle()
            battery_id = fixture._battery_items()["payload"]["battery_id"]
            _, battery_item = self._stage(
                transport, fixture.temp_root, "stale-version-battery", fixture._battery_items(), "WRITER_ROBOT"
            )
            tower_raw, battery_report = self._apply_writer_item(tower_raw, battery_item, "APPLIED")
            self.assertFalse(battery_report["rejected"], battery_report)
            _, running_item = self._stage(
                transport, fixture.temp_root, "stale-version-running", fixture._running_item(), "RUNNER_OBSERVATION"
            )
            tower_raw, running_report = self._apply_writer_item(tower_raw, running_item, "APPLIED")
            self.assertFalse(running_report["rejected"], running_report)

            with tempfile.TemporaryDirectory(prefix="nexo-stale-phase-source-") as temporary:
                runner_root, _ = materialize_live_tower(tower_raw, Path(temporary) / "running")
                completed = fixture._completed_item(runner_root)
            _, runner_item = self._stage(
                transport, fixture.temp_root, "stale-version-result", completed, "RUNNER_OBSERVATION"
            )
            expected_requests = self._real_effect_requests(tower_raw, runner_item)
            phase_request = next(request for request in expected_requests
                                 if request.get("entity_kind") == "test")

            independent_item = {
                "request_id": "REQ-INDEPENDENT-GOOD-DOCUMENT",
                "document": "indexes/stale-phase-independent-check.json",
                "merge": {"marker": "independent-good-item-applied"},
                "_inbox_id": "gateway:independent-good",
                "_inbox_name": "independent-good",
                "_inbox_source": "GATEWAY",
            }
            original_apply_document = tower_apply.apply_document
            bumped_version = False

            def apply_document_with_intervening_version_change(root, request):
                nonlocal bumped_version
                receipt = original_apply_document(root, request)
                terminal_battery = any(
                    row.get("id") == battery_id and row.get("status") == "DONE"
                    for row in (request.get("merge") or {}).get("batteries", [])
                    if isinstance(row, dict)
                ) if request.get("document") == "evolution/batteries.json" else False
                if receipt.get("accepted") and terminal_battery:
                    path = entity_path(root, "test", TEST_ID)
                    value = json.loads(path.read_text(encoding="utf-8"))
                    value["entity_version"] = int(value.get("entity_version") or 0) + 1
                    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True), encoding="utf-8")
                    bumped_version = True
                return receipt

            with mock.patch.object(tower_apply, "apply_document", side_effect=apply_document_with_intervening_version_change):
                packed, report = apply_to_tower(tower_raw, [runner_item, independent_item])
            self.assertTrue(bumped_version)
            self.assertIsNotNone(packed, report)
            self.assertTrue(any(row.get("item") == "stale-version-result"
                                and "EXECUTION_PHASE_SOURCE_VERSION_INVALID" in str(row.get("reason"))
                                for row in report["rejected"]), report)
            self.assertNotIn("stale-version-result", report["applied"])
            self.assertIn("independent-good", report["applied"])

            assert packed is not None
            bundle = read_live_tower_bytes(packed)
            with tempfile.TemporaryDirectory(prefix="nexo-stale-phase-readback-") as temporary:
                readback, _ = materialize_live_tower(packed, Path(temporary) / "rollback-readback")
                battery = scientific_integrity.batteries(readback)[0]
                test = scientific_integrity.entity(readback, TEST_ID)
                probe = json.loads((readback / "indexes/stale-phase-independent-check.json").read_text(encoding="utf-8"))
            self.assertEqual(battery["status"], "RUNNING")
            self.assertEqual(test["status"], test["execution_phase"], "RUNNING")
            self.assertEqual(probe["marker"], "independent-good-item-applied")
            phase_receipt = next(row for row in report["operation_receipts"]
                                 if row["effect_id"] == phase_request["request_id"])
            self.assertEqual(phase_receipt["outcome"], "REJECTED_TERMINAL")
            self.assertEqual(phase_receipt["reason_code"], "EXECUTION_PHASE_SOURCE_VERSION_INVALID")
            self.assertEqual(report["after"], verify_live_tower(bundle))
        finally:
            fixture.tearDown()

    def test_staged_request_reservation_runner_result_review_guard_and_projection(self) -> None:
        fixture = phase_fixture.ExecutionPhaseReconciliationTests()
        fixture.setUp()
        try:
            transport = _FakeGitHubContents()
            tower_raw = fixture._initial_bundle()
            initial_test = dict(fixture.test)
            previous_revision = verify_live_tower(read_live_tower_bytes(tower_raw))
            reports = []

            # Real recipe-only battery admission creates the immutable attempt reservation.
            staged_bytes, battery_item = self._stage(
                transport, fixture.temp_root, "stage-battery", fixture._battery_items(), "WRITER_ROBOT"
            )
            battery_tower, battery_report = self._apply_writer_item(tower_raw, battery_item, "APPLIED")
            self.assertEqual(json.loads(staged_bytes)["kind"], "TEST_BATTERY")
            self.assertEqual(battery_report["before"], previous_revision)
            previous_revision = battery_report["after"]
            reports.append(battery_report)
            tower_raw = battery_tower

            with tempfile.TemporaryDirectory(prefix="nexo-pipeline-reservation-") as temporary:
                reserved_root, _ = materialize_live_tower(tower_raw, Path(temporary) / "reserved")
                reserved_test = scientific_integrity.entity(reserved_root, TEST_ID)
                battery = scientific_integrity.batteries(reserved_root)[0]
            self.assertEqual(battery["status"], "QUEUED")
            self.assertEqual(reserved_test["execution_phase"], "QUEUED")
            self.assertEqual(reserved_test["attempt_id"], battery["tests"][0]["attempt_id"])

            # The Writer's private dispatch mark carries an in-memory capability,
            # not a serializable inbox claim. Exercise the same item shape emitted
            # by gpt_writer and require durable effect receipts plus canonical readback.
            dispatch_item = {
                "kind": "BATTERY_STATUS",
                "source": "WRITER_ROBOT",
                # Dispatch conversion stamps `dispatch_requested_at` from the
                # envelope clock; keep the expected and Writer conversions
                # byte-identical instead of depending on wall-clock seconds.
                "created_at": END,
                "_inbox_name": f"robot-dispatch-{battery['id']}",
                "_writer_dispatch_token": scientific_integrity.WRITER_DISPATCH_TOKEN,
                "payload": {
                    "battery_id": battery["id"],
                    "status": "DISPATCHED",
                    "run_ref": "github-actions",
                },
            }
            dispatch_tower, dispatch_report = self._apply_writer_item(tower_raw, dispatch_item, "APPLIED")
            self.assertEqual(dispatch_report["before"], previous_revision)
            previous_revision = dispatch_report["after"]
            reports.append(dispatch_report)
            with tempfile.TemporaryDirectory(prefix="nexo-pipeline-dispatch-ack-") as temporary:
                dispatch_root, _ = materialize_live_tower(dispatch_tower, Path(temporary) / "dispatch-ack")
                pending_test = scientific_integrity.entity(dispatch_root, TEST_ID)
                pending_battery = scientific_integrity.batteries(dispatch_root)[0]
            self.assertEqual(pending_battery["status"], "DISPATCH_PENDING")
            self.assertEqual(pending_battery["dispatch_confirmation"], "PENDING_EXTERNAL_ACK")
            self.assertEqual(pending_test["execution_phase"], "DISPATCH_PENDING")
            self.assertNotIn("_writer_dispatch_token", json.dumps(dispatch_report))
            tower_raw = dispatch_tower

            # The runner observation advances the same captured reservation to RUNNING.
            _, running_item = self._stage(
                transport, fixture.temp_root, "stage-running", fixture._running_item(), "RUNNER_OBSERVATION"
            )
            running_tower, running_report = self._apply_writer_item(tower_raw, running_item, "APPLIED")
            self.assertEqual(running_report["before"], previous_revision)
            previous_revision = running_report["after"]
            reports.append(running_report)
            tower_raw = running_tower

            with tempfile.TemporaryDirectory(prefix="nexo-pipeline-runner-artifact-") as temporary:
                runner_root, _ = materialize_live_tower(tower_raw, Path(temporary) / "runner-observation")
                runner_artifact = fixture._completed_item(runner_root)
            _, result_item = self._stage(
                transport, fixture.temp_root, "sanitized-completed", runner_artifact, "RUNNER_OBSERVATION"
            )
            result_tower, result_report = self._apply_writer_item(tower_raw, result_item, "APPLIED")
            self.assertEqual(result_report["before"], previous_revision)
            previous_revision = result_report["after"]
            reports.append(result_report)
            tower_raw = result_tower

            # The same delivered semantic envelope is safely replayed after a lost ACK.
            with tempfile.TemporaryDirectory(prefix="nexo-pipeline-result-replay-") as temporary:
                replay_root, _ = materialize_live_tower(tower_raw, Path(temporary) / "replay-source")
                replay_artifact = fixture._completed_item(replay_root)
            _, replay_item = self._stage(
                transport, fixture.temp_root, "sanitized-completed", replay_artifact,
                "RUNNER_OBSERVATION", expected_relay_result="redelivered_missing_writer_receipt",
            )
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                replay_packed, replay_report = apply_to_tower(tower_raw, [replay_item])
            self.assertIsNone(replay_packed)
            self.assertEqual(replay_report["handled"], ["sanitized-completed"])
            self.assertEqual(replay_report["public_operation_receipts"], [])
            envelope_effect = operation_receipts.envelope_effect_id(replay_item["_inbox_id"])
            replay_receipt = next(row for row in replay_report["operation_receipts"]
                                  if row["effect_id"] == envelope_effect)
            result_receipt = next(row for row in result_report["operation_receipts"]
                                  if row["effect_id"] == envelope_effect)
            self.assertEqual(replay_receipt["visibility"], "PRIVATE")
            self.assertEqual(replay_receipt["effect_id"], operation_receipts.envelope_effect_id(replay_item["_inbox_id"]))
            self.assertEqual(replay_receipt["payload_sha256"], operation_receipts.payload_hash(replay_item, trusted_transport=True))
            self.assertEqual(replay_receipt["outcome"], "ALREADY_APPLIED")
            self.assertEqual(replay_receipt["occurred_at"], result_receipt["occurred_at"])
            self.assertNotEqual(replay_receipt["observed_at"], result_receipt["observed_at"])
            from runtime.nexo_agent_api.gpt_writer import _gateway_results
            private_gateway_payload, reported, resolved = _gateway_results(replay_report, ["sanitized-completed"])
            self.assertEqual(private_gateway_payload["items"], [])
            self.assertEqual(reported, [])
            self.assertEqual(resolved, [])

            # A positive review assertion without an attack receipt must be rejected by the real guard.
            with tempfile.TemporaryDirectory(prefix="nexo-pipeline-review-guard-") as temporary:
                review_root, _ = materialize_live_tower(tower_raw, Path(temporary) / "review-source")
                terminal_test = scientific_integrity.entity(review_root, TEST_ID)
            review_attempt = {
                "kind": "TEST_REVIEW_REQUEST",
                "payload": {"test_id": TEST_ID, "review_state": "CONFIRMED"},
                "request_id": "REQ-REVIEW-UNPROVEN-PHASE2",
                "entity_kind": "test",
                "entity_name": TEST_ID,
                "expected_version": terminal_test["entity_version"],
                "writer_role": "DAILY",
                "event_type": "VERDICT_REVIEW_RECORDED",
                "changes": {"review_state": "CONFIRMED"},
            }
            _, review_item = self._stage(
                transport, fixture.temp_root, "stage-unproven-review", review_attempt, "GATEWAY"
            )
            guarded_tower, guard_report = self._apply_writer_item(
                tower_raw, review_item, "REJECTED_TERMINAL"
            )
            self.assertEqual(guard_report["before"], previous_revision)
            self.assertEqual(guard_report["rejected"][0]["reason"], "REVIEW_EVIDENCE_REQUIRED")
            self.assertEqual(guard_report["public_operation_receipts"][0]["outcome"], "REJECTED_TERMINAL")
            self.assertIsNone(guard_report["public_operation_receipts"][0]["reason_code"])
            self.assertEqual(guard_report["after"], verify_live_tower(read_live_tower_bytes(guarded_tower)))
            tower_raw = guarded_tower

            final_bundle = read_live_tower_bytes(tower_raw)
            final_test = final_bundle["files"][f"entities/test/{TEST_ID}.json"]["value"]
            self.assertEqual(final_test["status"], "DONE")
            self.assertEqual(final_test["execution_phase"], "COMPLETED")
            self.assertEqual(final_test["executed_at"], END)
            self.assertEqual(final_test["attempt_id"], reserved_test["attempt_id"])
            self.assertEqual(final_test["execution_recipe_sha256"], reserved_test["execution_recipe_sha256"])
            self.assertNotIn("review_state", final_test)
            self.assertEqual(final_test["verdict"], "INCONCLUSIVE")
            self.assertEqual(final_test["decision"], "SYNTHETIC_ONLY")
            for field in scientific_integrity.FROZEN:
                self.assertEqual(final_test.get(field), initial_test.get(field), field)
            self.assertEqual(final_test["prereg_hash"], initial_test["prereg_hash"])
            self.assertEqual(final_test["claim_boundary"], initial_test["claim_boundary"])

            # Each Writer revision flows into the next stage; no replay or live Tower is involved.
            self.assertEqual([row["before"] for row in reports], [
                verify_live_tower(read_live_tower_bytes(fixture._initial_bundle())),
                reports[0]["after"], reports[1]["after"], reports[2]["after"],
            ])
            self.assertEqual(reports[-1]["after"], guard_report["before"])

            with tempfile.TemporaryDirectory(prefix="nexo-pipeline-public-projection-") as temporary:
                projected_root, _ = materialize_live_tower(tower_raw, Path(temporary) / "public-source")
                projection = build_public_projection(
                    projected_root,
                    tower_revision=verify_live_tower(final_bundle),
                    generated_at=END,
                )
            self.assertTrue(verify_projection(projection)[0])
            projected_test = next(test for test in projection["tests"] if test["id"] == TEST_ID)
            self.assertEqual(projected_test["status"], "DONE")
            self.assertEqual(projected_test["verdict"], "INCONCLUSIVE")
            self.assertEqual(projected_test["question"], initial_test["question"])
            self.assertEqual(projected_test["claim_boundary"], initial_test["claim_boundary"])
            self.assertEqual(projected_test["prereg"]["hash"], initial_test["prereg_hash"])
            self.assertIsNone(projected_test.get("review"))
            self.assertEqual(projected_test["execution"]["run_ref"], RUN_REF)
            public_blob = json.dumps(projection, ensure_ascii=False, sort_keys=True)
            self.assertNotIn("REVIEW_EVIDENCE_REQUIRED", public_blob)
            self.assertNotIn("operations/receipts", public_blob)

            # A legacy terminal Tower without a durable effect receipt is not ACKed as success.
            legacy_raw = fixture._successful_writer_bundle()
            with tempfile.TemporaryDirectory(prefix="nexo-pipeline-legacy-terminal-") as temporary:
                legacy_root, _ = materialize_live_tower(legacy_raw, Path(temporary) / "legacy")
                self.assertEqual(operation_receipts.load_receipts(legacy_root), [])
                legacy_artifact = fixture._completed_item(legacy_root)
            _, legacy_item = self._stage(
                transport, fixture.temp_root, "legacy-no-result-receipt", legacy_artifact,
                "RUNNER_OBSERVATION",
            )
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                legacy_packed, legacy_report = apply_to_tower(legacy_raw, [legacy_item])
            self.assertIsNotNone(legacy_packed)
            self.assertEqual(legacy_report["handled"], [])
            self.assertEqual(legacy_report["deferred"][0]["outcome"], "DEFERRED_DEPENDENCY")
            legacy_deferred = next(
                row for row in legacy_report["operation_receipts"]
                if row["effect_id"] == operation_receipts.envelope_effect_id(legacy_item["_inbox_id"])
            )
            self.assertEqual(legacy_deferred["outcome"], "DEFERRED_DEPENDENCY")
            self.assertEqual(legacy_deferred["reason_code"], "LEGACY_EFFECT_RESULT_UNVERIFIED")
        finally:
            fixture.tearDown()


if __name__ == "__main__":
    unittest.main()
