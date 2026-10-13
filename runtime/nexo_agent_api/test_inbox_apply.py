from __future__ import annotations

import contextlib
import argparse
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from runtime.nexo_agent_api import operation_receipts
from runtime.nexo_agent_api.inbox_apply import ProposalError, proposal_to_requests
from runtime.nexo_agent_api.tower_paths import entity_path


class InboxApplyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        path = entity_path(self.root, "test", "T-1")
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps({"id": "T-1", "entity_version": 3, "status": "READY",
                                    "semantic": {"domain_id": "science", "topic_id": "x"}}))

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_result_proposal_keeps_semantic_and_bumps_from_current_version(self):
        item = {"kind": "MUTATION_PROPOSAL", "created_at": "2026-09-24T00:00:00Z",
                "payload": {"test_id": "T-1", "result": {"veredito": "inconclusive", "estatísticas": {"sigma": 1.2}},
                            "semantic": {"result_meaning": "Nada robusto."}}}
        [request] = proposal_to_requests(item, self.root)
        self.assertEqual(request["expected_version"], 3)
        self.assertEqual(request["changes"]["verdict"], "INCONCLUSIVE")
        self.assertEqual(request["changes"]["statistics"], {"sigma": 1.2})
        self.assertEqual(request["changes"]["semantic"]["topic_id"], "x")
        self.assertEqual(request["changes"]["semantic"]["result_meaning"], "Nada robusto.")

    def test_duplicate_gateway_result_is_handled_without_repacking_or_event(self):
        from runtime.nexo_agent_api.gpt_writer import apply_to_tower
        from runtime.nexo_agent_api.live_tower import LIVE_TOWER_NAME, publish_live_tower

        item = {
            "kind": "MUTATION_PROPOSAL",
            "created_at": "2026-09-26T12:10:01Z",
            "_inbox_source": "GATEWAY",
            "_inbox_name": "gw-tcc-first",
            "_inbox_id": "gateway:tcc-first",
            "payload": {
                "test_id": "T-1",
                "result": {"verdict": "INCONCLUSIVE", "summary": "Resultado congelado.",
                           "statistics": {"n": 5}},
                "semantic": {"result_meaning": "O resultado continuou inconclusivo."},
                "limitations": ["Amostra congelada."],
                "reproducibility": {"attempts": [{"attempt": 1, "status": "DONE"}]},
            },
        }
        [first_request] = proposal_to_requests(item, self.root)
        current = json.loads(entity_path(self.root, "test", "T-1").read_text())
        current.update(first_request["changes"])
        current["entity_version"] = 9
        entity_path(self.root, "test", "T-1").write_text(json.dumps(current))
        (self.root / "CONTROL.json").write_text(json.dumps({
            "truth_owner": "TOWER_V06@GOOGLE_DRIVE_PRIVATE",
            "write_model": "IN_PLACE_FILE_REVISION_CAS_READBACK",
        }))
        publish_live_tower(self.root)
        tower_raw = (self.root / LIVE_TOWER_NAME).read_bytes()
        duplicate = {**item, "created_at": "2026-09-26T12:24:00Z",
                     "_inbox_name": "gw-tcc-duplicate", "_inbox_id": "gateway:tcc-duplicate"}

        with patch("runtime.nexo_agent_api.evolution.contest_chain_reconcile_requests", return_value=[]), \
             patch("runtime.nexo_agent_api.evolution.maintenance_reconcile_requests", return_value=[]), \
             patch("runtime.nexo_agent_api.evolution.incident_reconcile_requests", return_value=[]), \
             patch("runtime.nexo_agent_api.execution_recovery.reconcile_requests", return_value=[]), \
             patch("runtime.nexo_agent_api.execution_recovery.ensure_handoffs", return_value=0):
            packed, report = apply_to_tower(tower_raw, [duplicate])

        # This fixture wrote the terminal result by hand, before the Writer
        # had a durable effect receipt. A different gateway identity cannot
        # claim that legacy state as an already-applied effect.
        self.assertIsNotNone(packed)
        self.assertEqual(report["status"], "READY_TO_UPLOAD")
        self.assertEqual(report["handled"], [])
        self.assertEqual(report["applied"], [])
        self.assertEqual(report["deferred"][0]["outcome"], "DEFERRED_DEPENDENCY")
        self.assertEqual({row["outcome"] for row in report["public_operation_receipts"]},
                         {"DEFERRED_DEPENDENCY"})
        self.assertEqual(report["receipts"], [])

    def test_conflicting_result_identity_is_recorded_once_and_retry_is_handled(self):
        from runtime.nexo_agent_api.gpt_writer import apply_to_tower
        from runtime.nexo_agent_api.live_tower import LIVE_TOWER_NAME, publish_live_tower, read_live_tower_bytes

        current_path = entity_path(self.root, "test", "T-1")
        current = json.loads(current_path.read_text())
        current.update({
            "entity_version": 8,
            "status": "DONE", "state": "DONE", "verdict": "PROMOTED",
            "result_summary": "Resultado original.", "executed_by": "CHATGPT_TASK_EXECUTOR",
            "executed_at": "2026-09-26T12:10:01Z", "inbox_ref": "gateway:tcc-stable",
        })
        current_path.write_text(json.dumps(current))
        (self.root / "CONTROL.json").write_text(json.dumps({
            "truth_owner": "TOWER_V06@GOOGLE_DRIVE_PRIVATE",
            "write_model": "IN_PLACE_FILE_REVISION_CAS_READBACK",
        }))
        publish_live_tower(self.root)
        raw = (self.root / LIVE_TOWER_NAME).read_bytes()
        conflict = {
            "kind": "MUTATION_PROPOSAL", "created_at": "2026-09-26T12:10:01Z",
            "_inbox_source": "GATEWAY", "_inbox_name": "gw-tcc-stable",
            "_inbox_id": "gateway:tcc-stable",
            "payload": {"test_id": "T-1", "result": {
                "verdict": "REJECTED", "summary": "Conteúdo conflitante."}},
        }

        patches = (
            patch("runtime.nexo_agent_api.evolution.contest_chain_reconcile_requests", return_value=[]),
            patch("runtime.nexo_agent_api.evolution.maintenance_reconcile_requests", return_value=[]),
            patch("runtime.nexo_agent_api.evolution.incident_reconcile_requests", return_value=[]),
            patch("runtime.nexo_agent_api.execution_recovery.reconcile_requests", return_value=[]),
            patch("runtime.nexo_agent_api.execution_recovery.ensure_handoffs", return_value=0),
        )
        with patches[0], patches[1], patches[2], patches[3], patches[4]:
            packed, first = apply_to_tower(raw, [conflict])
        self.assertIsNotNone(packed)
        self.assertEqual(first["handled"], ["gw-tcc-stable"])
        self.assertEqual(first["rejected"][0]["reason"], "INBOX_RESULT_IDENTITY_CONFLICT")
        stored = read_live_tower_bytes(packed)
        artifacts = [entry["value"] for name, entry in stored["files"].items()
                     if name.startswith("entities/artifact/")]
        self.assertEqual(len(artifacts), 1)
        self.assertEqual(artifacts[0]["kind"], "UNAPPLIED_MUTATION_PROPOSAL")

        patches = (
            patch("runtime.nexo_agent_api.evolution.contest_chain_reconcile_requests", return_value=[]),
            patch("runtime.nexo_agent_api.evolution.maintenance_reconcile_requests", return_value=[]),
            patch("runtime.nexo_agent_api.evolution.incident_reconcile_requests", return_value=[]),
            patch("runtime.nexo_agent_api.execution_recovery.reconcile_requests", return_value=[]),
            patch("runtime.nexo_agent_api.execution_recovery.ensure_handoffs", return_value=0),
        )
        with patches[0], patches[1], patches[2], patches[3], patches[4]:
            replay, second = apply_to_tower(packed, [conflict])
        self.assertIsNone(replay)
        self.assertEqual(second["handled"], ["gw-tcc-stable"])
        [summary] = second["public_operation_receipts"]
        self.assertEqual(summary["effect_id"], operation_receipts.envelope_effect_id("gateway:tcc-stable"))
        self.assertEqual(summary["outcome"], "REJECTED_TERMINAL")

    def test_incomplete_proposals_are_completed_not_rejected(self):
        # result without a plain reading -> provisional reading, still recorded on the test
        [request] = proposal_to_requests({"kind": "MUTATION_PROPOSAL", "payload": {"test_id": "T-1", "result": {}}}, self.root)
        self.assertEqual(request["entity_kind"], "test")
        self.assertEqual(request["changes"]["semantic"]["result_meaning_source"], "WRITER_PROVISIONAL")
        # result for a test that does not exist -> the test is registered first, then the result
        requests = proposal_to_requests({"kind": "MUTATION_PROPOSAL", "payload": {"test_id": "NOPE", "result": {"verdict": "PASS"}}}, self.root)
        tests = [r for r in requests if r.get("entity_kind") == "test"]
        self.assertEqual([r["entity_name"] for r in tests], ["NOPE", "NOPE"])
        self.assertEqual(tests[-1]["changes"]["verdict"], "PASS")
        # hypothesis without frozen criteria -> DRAFT, never READY, never dropped
        requests = proposal_to_requests({"kind": "HYPOTHESIS_PROPOSAL", "payload": {"display_name": "Teste de exemplo", "domain": "science", "test_id": "H-1", "semantic": {"domain_id": "science"}}}, self.root)
        self.assertEqual(requests[0]["changes"]["status"], "DRAFT")

    def test_generic_shapes_are_understood(self):
        # no kind, batch under "results", verdict at top level, meaning only in verdict_plain
        item = {"payload": {"results": [{"test_id": "T-1", "veredito": "PASS", "semantic": {"verdict_plain": "Passou."}}]}}
        [request] = proposal_to_requests(item, self.root)
        self.assertEqual(request["entity_kind"], "test")
        self.assertEqual(request["changes"]["verdict"], "PASS")
        self.assertEqual(request["changes"]["semantic"]["result_meaning"], "Passou.")

    def test_unknown_kind_is_recorded(self):
        [request] = proposal_to_requests({"kind": "SOMETHING_NEW", "payload": {"x": 1}}, self.root)
        self.assertEqual(request["changes"]["kind"], "INBOX_RECORD")

    def test_signal_is_recorded_as_artifact(self):
        [request] = proposal_to_requests({"kind": "LEARNING_SIGNAL", "payload": {"signals": []}, "_inbox_name": "a b"}, self.root)
        self.assertEqual(request["entity_kind"], "artifact")
        self.assertEqual(request["entity_name"], "LEARNING_SIGNAL::A-B")

    @staticmethod
    def _operational_receipt_item(**payload_changes):
        payload = {
            "contract": "NEXO_OPERATIONAL_RECEIPT_V1",
            "receipt_id": "drive-actions-12345-1",
            "pipeline": "DRIVE_GITHUB_ACTIONS_WRITER_TOWER_V1",
            "status": "PASS",
            "scope": "ENGINEERING_OPERATIONAL_ONLY",
            "scientific_result_eligible": False,
            "repository": "byDenoso/Pantheon",
            "commit_sha": "a" * 40,
            "run_ref": "actions/runs/12345",
            "run_attempt": 1,
            "role_session": {
                "contract": "NEXO_ROLE_SESSION_V1",
                "session_id": "drive-operational-control-v1",
                "role": "EXECUTOR",
                "work_id": "OPERATIONAL-CONTROL-DRIVE-SUM-V1",
                "mcp_endpoint": "https://nexo-one-two.vercel.app/api/mcp",
                "mcp_tool": "get_role_session",
                "prompt_sha256": "47fe9079dc26f58ef206be163edb963c572199e923218bc79984172787520484",
                "context_sha256": "c" * 64,
            },
            "input": {
                "source_storage": "GOOGLE_DRIVE_PRIVATE",
                "file_id": "1Cr7L6bbVlOqB0HUvYett0xkhRS-NWRWr",
                "version": "0B9ZwoXbzaIA-dURSU09VT3BkanJvNlBlSDN5RjZUTUFOYnVRPQ",
                "sha256": "3d87520f2b1bffb5c337e3d13d568ebe63d6aa09ad9cfa7dd2ed1a444d659988",
                "scope": "DRIVE_BYTES_REVERIFIED_IN_SECRET_FREE_JOB",
            },
            "result": {"count": 3, "sum": 6, "mean": 2, "known_result_matched": True},
            "decision": "OPERATIONAL_CONTROL_PASS",
            "result_sha256": "c" * 64,
            "executed_at": "2026-10-03T16:00:00Z",
        }
        payload.update(payload_changes)
        return {
            "kind": "OPERATIONAL_RECEIPT",
            "source": "WRITER_ROBOT",
            "created_at": payload["executed_at"],
            "_inbox_source": "RUNNER_OBSERVATION",
            "_inbox_name": "operational-receipt-" + payload["receipt_id"],
            "_inbox_id": "runner:" + payload["receipt_id"],
            "payload": payload,
        }

    def test_operational_receipt_is_idempotent_artifact_not_scientific_test(self):
        from runtime.nexo_agent_api.tower_apply import apply_requests

        before = json.loads(entity_path(self.root, "test", "T-1").read_text())
        [request] = proposal_to_requests(self._operational_receipt_item(), self.root)
        self.assertEqual(request["entity_kind"], "artifact")
        self.assertEqual(request["changes"]["kind"], "OPERATIONAL_RECEIPT")
        self.assertFalse(request["changes"]["payload"]["scientific_result_eligible"])
        [first] = apply_requests(self.root, [request])
        self.assertTrue(first["accepted"], first)
        [replay] = apply_requests(self.root, [request])
        self.assertTrue(replay["accepted"], replay)
        self.assertEqual(replay["status"], "NO_OP")
        self.assertEqual(before, json.loads(entity_path(self.root, "test", "T-1").read_text()))
        stored = json.loads(entity_path(
            self.root, "artifact", "OPERATIONAL_RECEIPT::OPERATIONAL-RECEIPT-DRIVE-ACTIONS-12345-1"
        ).read_text())
        self.assertEqual(stored["payload"]["status"], "PASS")
        self.assertNotIn("verdict", stored)

    def test_operational_receipt_rejects_untrusted_source_and_science_eligibility(self):
        untrusted = self._operational_receipt_item()
        untrusted["_inbox_source"] = "GATEWAY"
        with self.assertRaisesRegex(ProposalError, "REQUIRES_RUNNER_OBSERVATION"):
            proposal_to_requests(untrusted, self.root)
        for key, value in (("source", "GATEWAY"),
                           ("_inbox_name", "battery-update-0"),
                           ("_inbox_id", "runner:battery:0")):
            wrong_route = self._operational_receipt_item()
            wrong_route[key] = value
            with self.subTest(key=key), self.assertRaisesRegex(
                    ProposalError, "REQUIRES_RUNNER_OBSERVATION"):
                proposal_to_requests(wrong_route, self.root)
        with self.assertRaisesRegex(ProposalError, "IDENTITY_INVALID"):
            proposal_to_requests(self._operational_receipt_item(
                scientific_result_eligible=True), self.root)
        bad_session = self._operational_receipt_item()["payload"]["role_session"]
        bad_session["role"] = "LEARNER"
        with self.assertRaisesRegex(ProposalError, "ROLE_SESSION_INVALID"):
            proposal_to_requests(self._operational_receipt_item(
                role_session=bad_session), self.root)

    def test_writer_loader_stamps_runner_source_and_stable_identity(self):
        from runtime.nexo_agent_api.gpt_writer import _runner_operational_updates

        item = self._operational_receipt_item()
        external = {key: value for key, value in item.items() if not key.startswith("_inbox_")}
        path = self.root / "operational-updates.json"
        path.write_text(json.dumps([external]), encoding="utf-8")
        [loaded] = _runner_operational_updates(str(path))
        self.assertEqual(loaded["_inbox_source"], "RUNNER_OBSERVATION")
        self.assertEqual(loaded["_inbox_id"], "runner:drive-actions-12345-1")
        [request] = proposal_to_requests(loaded, self.root)
        self.assertEqual(request["entity_kind"], "artifact")
        path.write_text(json.dumps([{**external, "_inbox_source": "GATEWAY"}]), encoding="utf-8")
        self.assertEqual(_runner_operational_updates(str(path)), [])
        external["kind"] = "MUTATION_PROPOSAL"
        path.write_text(json.dumps([external]), encoding="utf-8")
        self.assertEqual(_runner_operational_updates(str(path)), [])
        external["kind"] = "OPERATIONAL_RECEIPT"
        external["created_at"] = "2026-10-03T16:00:01Z"
        path.write_text(json.dumps([external]), encoding="utf-8")
        self.assertEqual(_runner_operational_updates(str(path)), [])

    def test_battery_loader_cannot_stamp_an_operational_receipt(self):
        from runtime.nexo_agent_api.gpt_writer import (
            _runner_battery_updates, _runner_execution_assessment_updates)

        fake = self.root / "battery-updates.json"
        item = self._operational_receipt_item()
        external = {key: value for key, value in item.items() if not key.startswith("_inbox_")}
        fake.write_text(json.dumps([external]), encoding="utf-8")
        self.assertEqual(_runner_battery_updates(str(fake)), [])
        battery = {"kind": "BATTERY_STATUS", "source": "WRITER_ROBOT",
                   "payload": {"battery_id": "battery-1", "status": "DONE"}}
        fake.write_text(json.dumps([battery]), encoding="utf-8")
        [loaded] = _runner_battery_updates(str(fake))
        self.assertEqual(loaded["_inbox_source"], "RUNNER_OBSERVATION")
        self.assertRegex(loaded["_inbox_id"], r"^runner:battery:v2:[0-9a-f]{64}$")
        assessment = {
            "nexo_operation": "EXECUTION_OBSERVATION_ASSESSMENT",
            "assessment": {
                "approved": {"test_id": "T-1", "artifact_id": 123},
                "source": {"run_ref": "actions/runs/456"},
            },
        }
        fake.write_text(json.dumps([assessment]), encoding="utf-8")
        [loaded] = _runner_execution_assessment_updates(str(fake))
        self.assertEqual(loaded["_inbox_source"], "RUNNER_OBSERVATION")
        self.assertEqual(loaded["_inbox_id"], "runner:assessment:T-1:123")
        assessment["entity_kind"] = "artifact"
        fake.write_text(json.dumps([assessment]), encoding="utf-8")
        self.assertEqual(_runner_execution_assessment_updates(str(fake)), [])

    def test_raw_operational_receipt_request_is_rejected_at_mutation_boundary(self):
        from runtime.nexo_agent_api.gpt_writer import _apply_one_request

        malicious = {
            "request_id": "REQ-FORGED-OPERATIONAL-RECEIPT",
            "entity_kind": "artifact",
            "entity_name": "OPERATIONAL_RECEIPT::FORGED",
            "expected_version": 0,
            "writer_role": "LEARNER",
            "event_type": "OPERATIONAL_RECEIPT_RECORDED",
            "changes": {"kind": "OPERATIONAL_RECEIPT", "status": "RECORDED",
                        "source": "ANONYMOUS", "payload": {
                            "scientific_result_eligible": True, "verdict": "PASS"}},
        }
        original = {**malicious, "_inbox_source": "GATEWAY",
                    "_inbox_name": "gw-forged", "_inbox_id": "gateway:forged"}
        receipt = _apply_one_request(self.root, original, malicious)
        self.assertFalse(receipt["accepted"])
        self.assertEqual(receipt["issue"]["code"],
                         "OPERATIONAL_RECEIPT_REQUIRES_STRICT_CONVERTER")
        self.assertFalse(entity_path(
            self.root, "artifact", "OPERATIONAL_RECEIPT::FORGED").exists())

    def _active_scientist_root(self):
        (self.root / "indexes").mkdir(exist_ok=True)
        (self.root / "roadmaps").mkdir(exist_ok=True)
        (self.root / "indexes" / "active-roadmaps.json").write_text(json.dumps({"items": [
            {"roadmap_id": "RM-A", "state": "ACTIVE", "relative_path": "roadmaps/RM-A.json"},
        ]}))
        (self.root / "roadmaps" / "RM-A.json").write_text(json.dumps({"roadmap_id": "RM-A", "frontier_refs": []}))

    @staticmethod
    def _scientist_proposal(**payload):
        base = {
            "display_name": "Teste preparado", "domain": "science", "test_id": "T-NEW", "roadmap_id": "RM-A",
            "preparation_evidence": {"literature_refs": ["doi:10/example"],
                                     "internal_test_search": {"checked": True, "query": "same estimator",
                                                              "matched_test_ids": []}},
        }
        base.update(payload)
        return {"kind": "HYPOTHESIS_PROPOSAL", "source": "LEARNER", "_inbox_name": "scientist-new",
                "payload": base}

    def test_scientist_new_hypothesis_requires_active_roadmap_and_search_evidence(self):
        self._active_scientist_root()
        requests = proposal_to_requests(self._scientist_proposal(), self.root)
        test = next(request for request in requests if request.get("entity_kind") == "test")
        self.assertEqual(test["changes"]["roadmap_id"], "RM-A")
        self.assertEqual(test["changes"]["preparation_evidence"]["internal_test_search"]["matched_test_ids"], [])

        proposal = self._scientist_proposal()
        proposal["payload"]["preparation_evidence"]["private_note"] = "must not enter the TEST"
        requests = proposal_to_requests(proposal, self.root)
        test = next(request for request in requests if request.get("entity_kind") == "test")
        self.assertNotIn("private_note", test["changes"]["preparation_evidence"])

        missing = self._scientist_proposal(preparation_evidence={})
        [record] = proposal_to_requests(missing, self.root)
        self.assertEqual(record["changes"]["kind"], "UNAPPLIED_HYPOTHESIS_PROPOSAL")
        self.assertEqual(record["changes"]["payload"]["_not_applied_reason"],
                         "SCIENTIST_LITERATURE_AND_INTERNAL_SEARCH_REQUIRED")

        inactive = self._scientist_proposal(roadmap_id="RM-OTHER")
        [record] = proposal_to_requests(inactive, self.root)
        self.assertEqual(record["changes"]["payload"]["_not_applied_reason"], "SCIENTIST_ROADMAP_NOT_ACTIVE")

    def test_scientist_duplicate_requires_purposeful_replication(self):
        self._active_scientist_root()
        entity_path(self.root, "test", "T-OLD").write_text(json.dumps({"id": "T-OLD", "entity_version": 1}))
        evidence = {"literature_refs": ["doi:10/example"],
                    "internal_test_search": {"checked": True, "query": "same estimator",
                                             "matched_test_ids": ["T-OLD"]}}
        [record] = proposal_to_requests(self._scientist_proposal(preparation_evidence=evidence), self.root)
        self.assertEqual(record["changes"]["payload"]["_not_applied_reason"],
                         "SCIENTIST_DUPLICATE_WITHOUT_REPLICATION_PURPOSE")
        evidence["replication"] = {"justified": True, "purpose": "independent catalogue",
                                   "independence_axis": "DATA", "compares_to_test_ids": ["T-OLD"]}
        requests = proposal_to_requests(self._scientist_proposal(preparation_evidence=evidence), self.root)
        self.assertTrue(any(request.get("entity_kind") == "test" for request in requests))

        invalid = dict(evidence)
        invalid["replication"] = {"justified": True, "purpose": ["not", "text"],
                                  "independence_axis": "DATA", "compares_to_test_ids": ["T-OLD"]}
        [record] = proposal_to_requests(self._scientist_proposal(test_id="T-BAD-SHAPE",
                                                                  preparation_evidence=invalid), self.root)
        self.assertEqual(record["changes"]["payload"]["_not_applied_reason"],
                         "SCIENTIST_DUPLICATE_WITHOUT_REPLICATION_PURPOSE")

        unknown = dict(evidence)
        unknown["replication"] = {"justified": True, "purpose": "independent catalogue",
                                  "independence_axis": "DATA",
                                  "compares_to_test_ids": ["T-OLD", "T-UNKNOWN"]}
        [record] = proposal_to_requests(self._scientist_proposal(test_id="T-BAD-REF",
                                                                  preparation_evidence=unknown), self.root)
        self.assertEqual(record["changes"]["payload"]["_not_applied_reason"],
                         "SCIENTIST_REPLICATION_REFERENCE_INVALID")

    def test_legacy_and_non_scientist_producers_need_no_new_preparation_fields(self):
        self._active_scientist_root()
        for index, source in enumerate((None, "WRITER_ROBOT", "CONVERSA", "EXECUTOR")):
            proposal = self._scientist_proposal(test_id=f"T-COMPAT-{index}")
            proposal.pop("source", None)
            if source:
                proposal["source"] = source
            proposal["payload"].pop("preparation_evidence")
            requests = proposal_to_requests(proposal, self.root)
            self.assertTrue(any(request.get("entity_name") == f"T-COMPAT-{index}" for request in requests), source)

    def test_waiting_recovery_does_not_create_a_global_hypothesis_barrier(self):
        self._active_scientist_root()
        path = entity_path(self.root, "work", "WORK::RECOVERY")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"id": "WORK::RECOVERY", "status": "WAIT_DEPENDENCY",
                                    "next_action": "WAIT_FOR_EXTERNAL_RELEASE",
                                    "recovery": {"policy": "EXECUTION_RECOVERY_V1", "target_role": "LEARNER",
                                                 "ownership_state": "ACCEPTED"}}))
        requests = proposal_to_requests(self._scientist_proposal(), self.root)
        self.assertTrue(any(request.get("entity_kind") == "test" for request in requests))

    def test_scientist_gate_does_not_reopen_or_refreeze_existing_test(self):
        # Existing-test enrichment returns before the new-science admission gate.
        [request] = proposal_to_requests({"kind": "HYPOTHESIS_PROPOSAL", "source": "LEARNER",
                                          "payload": {"test_id": "T-1", "method": "existing correction"}}, self.root)
        self.assertEqual(request["event_type"], "TEST_ENRICHED")
        self.assertEqual(request["entity_name"], "T-1")

    def test_private_drive_handoff_becomes_a_canonical_handoff_operation(self):
        handoff = {
            "request_id": "REQ-PRIVATE-INBOX-001",
            "from_role": "ADVISOR",
            "to_role": "EXECUTOR",
            "handoff_type": "RESEARCH_READY",
            "entity_ref": "WORK::DARK-ENERGY",
            "thread_id": "THR::DARK-ENERGY",
            "summary_plain": "Uma fonte nova ajuda a comparar duas explicações para a energia escura.",
            "why_it_matters": "A comparação pode mostrar qual hipótese merece o próximo teste.",
            "next_action": "Compare as previsões da fonte com o teste já planejado.",
        }

        [request] = proposal_to_requests({"kind": "HANDOFF", "_inbox_source": "DRIVE", "payload": handoff}, self.root)

        self.assertEqual(request["nexo_operation"], "HANDOFF_CREATE")
        self.assertEqual(request["handoff"], handoff)

    def test_public_handoff_proposal_stays_in_inbox(self):
        with self.assertRaisesRegex(ProposalError, "PRIVATE_HANDOFF_REQUIRES_DRIVE_INBOX"):
            proposal_to_requests({
                "kind": "HANDOFF",
                "_inbox_source": "GITHUB",
                "payload": {"request_id": "REQ-PUBLIC-HANDOFF"},
            }, self.root)

    def test_declared_drive_source_cannot_authorize_a_private_handoff(self):
        with self.assertRaisesRegex(ProposalError, "PRIVATE_HANDOFF_REQUIRES_DRIVE_INBOX"):
            proposal_to_requests({
                "kind": "HANDOFF",
                "source": "DRIVE",
                "payload": {"request_id": "REQ-SPOOFED-PRIVATE-HANDOFF"},
            }, self.root)

    def test_private_drive_handoff_transition_becomes_a_canonical_transition_operation(self):
        transition = {"handoff_id": "HO-EXISTING", "state": "ACK", "writer_role": "EXECUTOR"}

        [request] = proposal_to_requests({
            "kind": "HANDOFF_TRANSITION",
            "_inbox_source": "DRIVE",
            "payload": transition,
        }, self.root)

        self.assertEqual(request["nexo_operation"], "HANDOFF_TRANSITION")
        self.assertEqual(request["_inbox_source"], "DRIVE")
        self.assertEqual(request["transition"], transition)

    def test_public_handoff_transition_stays_in_inbox(self):
        with self.assertRaisesRegex(ProposalError, "PRIVATE_HANDOFF_REQUIRES_DRIVE_INBOX"):
            proposal_to_requests({
                "kind": "HANDOFF_TRANSITION",
                "_inbox_source": "GATEWAY",
                "payload": {"handoff_id": "HO-EXISTING", "state": "ACK", "writer_role": "EXECUTOR"},
            }, self.root)




class HandoffProtocolCIRegressionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "entities" / "work").mkdir(parents=True)

    def tearDown(self):
        self.tmp.cleanup()

    def test_idempotent_send_recipient_transition_and_citations(self):
        from runtime.nexo_agent_api import AgentService, TowerAgentIssue

        service = AgentService(self.root)
        envelope = {
            "request_id": "REQ-CI-HANDOFF-001",
            "from_role": "ADVISOR",
            "to_role": "EXECUTOR",
            "handoff_type": "RESEARCH_READY",
            "entity_ref": "WORK::DE-CI",
            "thread_id": "THR::DE-CI",
            "summary_plain": "Uma fonte primária relevante foi ligada ao objetivo atual.",
            "why_it_matters": "Ela altera a prioridade do próximo teste discriminante, não o resultado científico.",
            "next_action": "Executar o teste já congelado usando a fonte citada como entrada observacional.",
            "objective_ref": "OBJ::DARK-ENERGY-NATURE",
            "evidence_refs": [{"ref": "TEST::DE-CI", "kind": "TEST"}],
            "source_links": [{
                "label": "Original survey release",
                "url": "https://example.org/survey",
                "access_date": "2026-09-27",
                "publisher": "Example Survey",
                "authors": ["A. Author"],
                "date": "2026-09-26",
                "supports": "Sustenta a medição observacional usada como entrada.",
                "uncertainty": "Não determina o veredito científico.",
                "next_test_impact": "Prioriza o próximo discriminante sem reescrever critérios.",
            }],
        }
        first = service.emit_handoff(**envelope)
        replay = service.emit_handoff(**envelope)
        self.assertEqual(first["event_id"], replay["event_id"])
        self.assertEqual(len(list((self.root / "events").rglob("*.json"))), 1)

        with self.assertRaises(TowerAgentIssue) as wrong:
            service.transition_handoff(first["handoff_id"], state="ACK", writer_role="LEARNER")
        self.assertEqual(wrong.exception.code, "HANDOFF_WRITER_MISMATCH")

        ack = service.transition_handoff(first["handoff_id"], state="ACK", writer_role="EXECUTOR")
        done = service.transition_handoff(first["handoff_id"], state="DONE", writer_role="EXECUTOR")
        self.assertEqual(ack["source_links"][0]["url"], "https://example.org/survey")
        self.assertEqual(done["evidence_refs"], envelope["evidence_refs"])
        self.assertEqual(service.inbox_for("EXECUTOR"), [])

    def test_human_fields_reject_internal_codes_but_keep_structured_refs_private(self):
        from runtime.nexo_agent_api import AgentService, TowerAgentIssue

        service = AgentService(self.root)
        base = {
            "request_id": "REQ-CI-LANGUAGE-001",
            "from_role": "ADVISOR",
            "to_role": "EXECUTOR",
            "handoff_type": "RESEARCH_READY",
            "entity_ref": "WORK::DE-LANGUAGE",
            "thread_id": "THR::DE-LANGUAGE",
            "summary_plain": "Uma nova medição pública pode ajudar a separar duas explicações para a energia escura.",
            "why_it_matters": "Ela permite comparar previsões diferentes sem mudar as regras já definidas para o teste.",
            "next_action": "Use a fonte citada no próximo teste já planejado e registre o efeito observado.",
            "confidence_plain": "Confiança moderada porque a fonte mede a quantidade necessária, mas ainda não decide qual explicação é correta.",
            "evidence_refs": [{"ref": "TEST::DE-LANGUAGE", "kind": "TEST"}],
        }
        created = service.emit_handoff(**base)
        self.assertEqual(created["evidence_refs"], [{"ref": "TEST::DE-LANGUAGE", "kind": "TEST"}])
        self.assertNotIn("TEST::DE-LANGUAGE", created["summary_plain"])

        bad = dict(base, request_id="REQ-CI-LANGUAGE-RAW-REF",
                   summary_plain="Use TEST::DE-LANGUAGE e aguarde o readback.")
        with self.assertRaises(TowerAgentIssue) as leaked:
            service.emit_handoff(**bad)
        self.assertIn(
            leaked.exception.code,
            {"HANDOFF_PLAIN_FIELD_LEAKS_INTERNAL_REF", "HANDOFF_PLAIN_FIELD_MACHINE_LANGUAGE"},
        )

        bad_confidence = dict(base, request_id="REQ-CI-LANGUAGE-CONFIDENCE", confidence_plain="HIGH")
        with self.assertRaises(TowerAgentIssue) as machine_confidence:
            service.emit_handoff(**bad_confidence)
        self.assertEqual(machine_confidence.exception.code, "HANDOFF_PLAIN_FIELD_MACHINE_LANGUAGE")

        bad_field = dict(base, request_id="REQ-CI-LANGUAGE-FIELD",
                         next_action="Atualize o topic_id antes de continuar.")
        with self.assertRaises(TowerAgentIssue) as field_name:
            service.emit_handoff(**bad_field)
        self.assertEqual(field_name.exception.code, "HANDOFF_PLAIN_FIELD_LEAKS_INTERNAL_REF")

    def test_same_request_id_with_different_content_is_rejected(self):
        from runtime.nexo_agent_api import AgentService, TowerAgentIssue

        service = AgentService(self.root)
        base = {
            "request_id": "REQ-CI-HANDOFF-CONFLICT",
            "from_role": "EXECUTOR",
            "to_role": "LEARNER",
            "handoff_type": "RESULT_READY",
            "entity_ref": "WORK::CI",
            "thread_id": "THR::CI",
            "summary_plain": "O resultado canônico está pronto.",
            "why_it_matters": "A aprendizagem depende deste resultado persistido.",
            "next_action": "Registrar a lição vinculada ao resultado.",
        }
        service.emit_handoff(**base)
        changed = dict(base, next_action="Executar uma ação materialmente diferente.")
        with self.assertRaises(TowerAgentIssue) as conflict:
            service.emit_handoff(**changed)
        self.assertEqual(conflict.exception.code, "HANDOFF_REQUEST_ID_CONFLICT")


class HandoffCLIPersistenceTests(unittest.TestCase):
    def recovery_tower(self):
        from runtime.nexo_agent_api import AgentService, materialize_role_views
        from runtime.nexo_agent_api.live_tower import LIVE_TOWER_NAME, publish_live_tower

        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name) / "source"
        for relative in ("entities/work", "manifests", "snapshot"):
            (root / relative).mkdir(parents=True, exist_ok=True)
        (root / "CONTROL.json").write_text(json.dumps({
            "truth_owner": "TOWER_V06@GOOGLE_DRIVE_PRIVATE",
            "write_model": "IN_PLACE_FILE_REVISION_CAS_READBACK",
        }), encoding="utf-8")
        (root / "snapshot/latest.json").write_text(json.dumps({"event_cursor": None}), encoding="utf-8")
        (root / "manifests/capabilities.json").write_text(json.dumps({"capabilities": {}}), encoding="utf-8")
        (root / "manifests/artifacts.json").write_text(json.dumps({"artifacts": {}}), encoding="utf-8")
        work = {
            "id": "WORK::RECOVERY-VIEW",
            "entity_version": 4,
            "kind": "DEPENDENCY_RECOVERY",
            "status": "BLOCKED",
            "owner_role": "ADVISOR",
            "test_id": "TEST::RECOVERY-VIEW",
            "thread_id": "THR::RECOVERY-VIEW",
            "recovery": {
                "policy": "EXECUTION_RECOVERY_V1",
                "fingerprint": "frozen-view-inputs",
                "target_role": "EXECUTOR",
                "ownership_state": "ASSIGNED_UNACCEPTED",
                "reasons": ["RECIPE_BINDING_MISSING"],
                "validation": {"eligible": False},
            },
        }
        entity_path(root, "work", work["id"]).write_text(json.dumps(work), encoding="utf-8")
        created = AgentService(root).emit_handoff(
            request_id="REQ-RECOVERY-VIEW-1",
            from_role="ADVISOR",
            to_role="EXECUTOR",
            handoff_type="BLOCKER_RECOVERY",
            entity_ref=work["id"],
            thread_id=work["thread_id"],
            summary_plain="O insumo verificável ainda precisa ser preparado.",
            why_it_matters="A preparação permite executar o desenho já congelado.",
            next_action="Validar a recuperação sem alterar a definição científica.",
        )
        materialize_role_views(root)
        publish_live_tower(root)
        return (root / LIVE_TOWER_NAME).read_bytes(), created, work

    def apply_handoff(self, raw, *, state, writer_role="EXECUTOR", inbox_id=None):
        from runtime.nexo_agent_api.gpt_writer import apply_to_tower

        item = {
            "kind": "HANDOFF_TRANSITION",
            "_inbox_source": "DRIVE",
            "payload": {
                "handoff_id": self.created["handoff_id"],
                "state": state,
                "writer_role": writer_role,
            },
        }
        if inbox_id is not None:
            item["_inbox_id"] = inbox_id
        with patch("runtime.nexo_agent_api.evolution.contest_chain_reconcile_requests", return_value=[]), \
             patch("runtime.nexo_agent_api.evolution.maintenance_reconcile_requests", return_value=[]), \
             patch("runtime.nexo_agent_api.evolution.incident_reconcile_requests", return_value=[]), \
             patch("runtime.nexo_agent_api.execution_recovery.reconcile_requests", return_value=[]), \
             patch("runtime.nexo_agent_api.execution_recovery.ensure_handoffs", return_value=0):
            return apply_to_tower(raw, [item])

    @staticmethod
    def tower_values(raw):
        from runtime.nexo_agent_api.live_tower import read_live_tower_bytes

        files = read_live_tower_bytes(raw)["files"]
        events = [entry["value"] for name, entry in files.items() if name.startswith("events/")]
        return {
            "work": files["entities/work/WORK::RECOVERY-VIEW.json"]["value"],
            "bootstrap": files["bootstrap/executor.json"]["value"],
            "events": events,
        }

    def test_recovery_ack_refreshes_work_inbox_and_event_cursor_before_pack(self):
        raw, self.created, original_work = self.recovery_tower()

        packed, report = self.apply_handoff(raw, state="ACK")

        self.assertIsNotNone(packed)
        self.assertEqual(report["rejected"], [])
        values = self.tower_values(packed)
        ack = next(event for event in values["events"] if event.get("state") == "ACK")
        self.assertEqual(values["work"]["owner_role"], "EXECUTOR")
        self.assertEqual(values["work"]["entity_version"], original_work["entity_version"] + 1)
        self.assertEqual(ack["entity_version"], values["work"]["entity_version"])
        self.assertEqual(ack["work_envelope"], values["work"])
        self.assertEqual(values["bootstrap"]["event_cursor"], ack["event_id"])
        self.assertEqual(values["bootstrap"]["inbox"], [ack])

    def test_recovery_ack_replay_is_idempotent_and_keeps_bootstrap_coherent(self):
        raw, self.created, _ = self.recovery_tower()
        packed, _ = self.apply_handoff(raw, state="ACK")
        before = self.tower_values(packed)

        replay, report = self.apply_handoff(packed, state="ACK")

        self.assertIsNone(replay)
        self.assertEqual(report["status"], "NO_OP")
        self.assertEqual(report["rejected"], [])
        self.assertEqual(len(before["events"]), 3)
        self.assertEqual(before["work"]["entity_version"], 5)
        ack = next(event for event in before["events"] if event.get("state") == "ACK")
        self.assertEqual(before["bootstrap"]["event_cursor"], ack["event_id"])
        self.assertEqual(before["bootstrap"]["inbox"][0]["state"], "ACK")

    def test_rejected_recovery_transitions_do_not_change_work_events_or_bootstrap(self):
        raw, self.created, _ = self.recovery_tower()
        initial = self.tower_values(raw)

        mismatch, report = self.apply_handoff(raw, state="ACK", writer_role="LEARNER")
        self.assertIsNotNone(mismatch)  # The terminal rejection itself is durable Tower state.
        self.assertEqual(report["status"], "READY_TO_UPLOAD")
        self.assertNotEqual(report["before"], report["after"])
        self.assertEqual(report["receipts"][0]["issue"]["code"], "HANDOFF_WRITER_MISMATCH")
        self.assertEqual(self.tower_values(mismatch), initial)

        failed, report = self.apply_handoff(raw, state="FAILED")
        self.assertIsNotNone(failed)
        self.assertEqual(report["rejected"], [])
        before_illegal = self.tower_values(failed)
        illegal, report = self.apply_handoff(
            failed, state="ACK", inbox_id="handoff-ack-after-failed-new-intent")
        self.assertIsNotNone(illegal)  # Again, only the durable operation receipt ledger changes.
        self.assertEqual(report["status"], "READY_TO_UPLOAD")
        self.assertNotEqual(report["before"], report["after"])
        self.assertEqual(report["rejected"][0]["reason"], "HANDOFF_ILLEGAL_TRANSITION")
        self.assertEqual(report["public_operation_receipts"], [])
        self.assertTrue(any(row["outcome"] == "REJECTED_TERMINAL" and row["visibility"] == "PRIVATE"
                            for row in report["operation_receipts"]))
        self.assertEqual(self.tower_values(illegal), before_illegal)

    def test_unattended_writer_applies_private_handoff_acknowledgement(self):
        from runtime.nexo_agent_api import AgentService
        from runtime.nexo_agent_api.gpt_writer import apply_to_tower
        from runtime.nexo_agent_api.live_tower import LIVE_TOWER_NAME, publish_live_tower, read_live_tower_bytes

        handoff = {
            "request_id": "REQ-ROBOT-ACK-001",
            "from_role": "ADVISOR",
            "to_role": "EXECUTOR",
            "handoff_type": "RESEARCH_READY",
            "entity_ref": "WORK::DARK-ENERGY",
            "thread_id": "THR::DARK-ENERGY",
            "summary_plain": "Uma fonte nova ajuda a comparar duas explicações para a energia escura.",
            "why_it_matters": "A comparação pode mostrar qual hipótese merece o próximo teste.",
            "next_action": "Compare as previsões da fonte com o teste já planejado.",
        }
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source"
            source.mkdir()
            (source / "CONTROL.json").write_text(json.dumps({
                "truth_owner": "TOWER_V06@GOOGLE_DRIVE_PRIVATE",
                "write_model": "IN_PLACE_FILE_REVISION_CAS_READBACK",
            }), encoding="utf-8")
            created = AgentService(source).emit_handoff(**handoff)
            publish_live_tower(source)
            tower_raw = (source / LIVE_TOWER_NAME).read_bytes()

        packed, report = apply_to_tower(tower_raw, [{
            "kind": "HANDOFF_TRANSITION",
            "_inbox_source": "DRIVE",
            "payload": {"handoff_id": created["handoff_id"], "state": "ACK", "writer_role": "EXECUTOR"},
        }])

        self.assertIsNotNone(packed)
        self.assertEqual(report["rejected"], [])
        stored = read_live_tower_bytes(packed)
        events = [entry["value"] for name, entry in stored["files"].items() if name.startswith("events/")]
        self.assertEqual([event["state"] for event in events], ["PENDING", "ACK"])

    def test_gpt_writer_lists_only_the_recipient_handoff_inbox(self):
        from runtime.nexo_agent_api import AgentService
        from runtime.nexo_agent_api.gpt_writer import main
        from runtime.nexo_agent_api.live_tower import LIVE_TOWER_NAME, publish_live_tower

        handoff = {
            "request_id": "REQ-ROLE-INBOX-001",
            "from_role": "ADVISOR",
            "to_role": "EXECUTOR",
            "handoff_type": "RESEARCH_READY",
            "entity_ref": "WORK::DARK-ENERGY",
            "thread_id": "THR::DARK-ENERGY",
            "summary_plain": "Uma fonte nova ajuda a comparar duas explicações para a energia escura.",
            "why_it_matters": "A comparação pode mostrar qual hipótese merece o próximo teste.",
            "next_action": "Compare as previsões da fonte com o teste já planejado.",
        }
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source"
            source.mkdir()
            (source / "CONTROL.json").write_text(json.dumps({
                "truth_owner": "TOWER_V06@GOOGLE_DRIVE_PRIVATE",
                "write_model": "IN_PLACE_FILE_REVISION_CAS_READBACK",
            }), encoding="utf-8")
            AgentService(source).emit_handoff(**handoff)
            publish_live_tower(source)
            tower_file = Path(tmp) / "tower.json"
            tower_file.write_bytes((source / LIVE_TOWER_NAME).read_bytes())
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                code = main(["handoff", str(tower_file), "list", "EXECUTOR"])

        self.assertEqual(code, 0)
        result = json.loads(output.getvalue())
        self.assertEqual(result["role"], "EXECUTOR")
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["items"][0]["request_id"], "REQ-ROLE-INBOX-001")
        self.assertEqual(result["items"][0]["next_action"], handoff["next_action"])

    def test_unattended_writer_persists_drive_handoff_into_the_live_tower(self):
        from runtime.nexo_agent_api.gpt_writer import apply_to_tower
        from runtime.nexo_agent_api.live_tower import LIVE_TOWER_NAME, publish_live_tower, read_live_tower_bytes

        handoff = {
            "request_id": "REQ-ROBOT-HANDOFF-001",
            "from_role": "ADVISOR",
            "to_role": "EXECUTOR",
            "handoff_type": "RESEARCH_READY",
            "entity_ref": "WORK::DARK-ENERGY",
            "thread_id": "THR::DARK-ENERGY",
            "summary_plain": "Uma fonte nova ajuda a comparar duas explicações para a energia escura.",
            "why_it_matters": "A comparação pode mostrar qual hipótese merece o próximo teste.",
            "next_action": "Compare as previsões da fonte com o teste já planejado.",
        }
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source"
            source.mkdir()
            (source / "CONTROL.json").write_text(json.dumps({
                "truth_owner": "TOWER_V06@GOOGLE_DRIVE_PRIVATE",
                "write_model": "IN_PLACE_FILE_REVISION_CAS_READBACK",
            }), encoding="utf-8")
            publish_live_tower(source)
            tower_raw = (source / LIVE_TOWER_NAME).read_bytes()

        packed, report = apply_to_tower(tower_raw, [{"kind": "HANDOFF", "_inbox_source": "DRIVE", "payload": handoff}])

        self.assertIsNotNone(packed)
        self.assertEqual(report["status"], "READY_TO_UPLOAD")
        self.assertEqual(report["rejected"], [])
        self.assertEqual(report["receipts"][0]["request_id"], handoff["request_id"])
        stored = read_live_tower_bytes(packed)
        events = [entry["value"] for name, entry in stored["files"].items() if name.startswith("events/")]
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["event_type"], "HANDOFF_CREATED")
        self.assertEqual(events[0]["to_role"], "EXECUTOR")

    def test_public_inbox_cannot_spoof_drive_source_or_be_marked_processed(self):
        from scripts import nexo_tower

        item = {
            "id": "github:private-handoff.json",
            "name": "private-handoff.json",
            "source": "GITHUB",
            "payload": {
                "kind": "HANDOFF",
                "source": "DRIVE",
                "payload": {"request_id": "REQ-SPOOFED-HANDOFF"},
            },
        }
        calls = {"apply": 0, "mark": []}

        class FakeDriveTower:
            def download(self):
                return b"raw", "BASE-HEAD"

        def fake_materialize(raw, dest):
            Path(dest).mkdir(parents=True, exist_ok=True)
            return Path(dest), {}

        output = io.StringIO()
        with patch.object(nexo_tower, "_collect_inbox", lambda github: [item]), \
             patch.object(nexo_tower, "DriveTower", FakeDriveTower), \
             patch.object(nexo_tower, "materialize_live_tower", fake_materialize), \
             patch.object(nexo_tower, "cmd_apply", lambda args: calls.__setitem__("apply", calls["apply"] + 1) or 0), \
             patch.object(nexo_tower, "_mark", lambda github, ids: calls["mark"].extend(ids)), \
             contextlib.redirect_stdout(output):
            code = nexo_tower._inbox_apply(object(), argparse.Namespace(dry_run=False))

        self.assertEqual(code, 0)
        self.assertEqual(calls["apply"], 0)
        self.assertEqual(calls["mark"], [])
        result = json.loads(output.getvalue())
        self.assertEqual(result["status"], "NOTHING_APPLICABLE")
        self.assertEqual(result["skipped"][0]["reason"], "PRIVATE_HANDOFF_REQUIRES_DRIVE_INBOX")

    def test_cli_inbox_composes_same_snapshot_board_posts_before_apply(self):
        from scripts import nexo_tower
        from runtime.nexo_agent_api.live_tower import build_live_tower_payload

        created_at = "2026-10-03T00:02:44Z"
        items = [
            {"id": "github:first.json", "name": "first.json", "source": "GITHUB",
             "payload": {"kind": "BOARD_POST", "source": "ENGINEER", "created_at": created_at,
                         "payload": {"to": "GUARDIAO", "text": "Primeiro CLI."}}},
            {"id": "github:second.json", "name": "second.json", "source": "GITHUB",
             "payload": {"kind": "BOARD_POST", "source": "ENGINEER", "created_at": created_at,
                         "payload": {"to": "GUARDIAO", "text": "Segundo CLI."}}},
        ]
        captured = {}
        with tempfile.TemporaryDirectory() as work:
            root = Path(work) / "tower"
            root.mkdir()
            (root / "CONTROL.json").write_text(json.dumps({
                "truth_owner": "TOWER_V06@GOOGLE_DRIVE_PRIVATE",
            }), encoding="utf-8")
            raw = json.dumps(build_live_tower_payload(root), ensure_ascii=False).encode("utf-8")

            class FakeDriveTower:
                def download(self):
                    return raw, "BASE-HEAD"

            def fake_apply(args):
                captured["requests"] = json.loads(Path(args.requests[0]).read_text(encoding="utf-8"))
                return 0

            with patch.object(nexo_tower, "_collect_inbox", lambda github: items), \
                 patch.object(nexo_tower, "DriveTower", FakeDriveTower), \
                 patch.object(nexo_tower, "cmd_apply", fake_apply), \
                 patch.object(nexo_tower, "_mark", lambda github, ids: None):
                code = nexo_tower._inbox_apply(object(), argparse.Namespace(dry_run=False))

        self.assertEqual(code, 0)
        requests = captured["requests"]
        self.assertEqual(len(requests), 2)
        self.assertEqual(len(requests[0]["merge"]["posts"]), 1)
        self.assertEqual(len(requests[1]["merge"]["posts"]), 2)
        self.assertEqual([post["text"] for post in requests[1]["merge"]["posts"][-2:]],
                         ["Primeiro CLI.", "Segundo CLI."])

    def test_create_handoff_uses_writer_lock_cas_readback_and_atlas_notification(self):
        from scripts import nexo_tower

        calls = {"lock": 0, "cas": 0, "notify": []}

        class FakeLock:
            def __enter__(self):
                calls["lock"] += 1
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

        class FakeDriveTower:
            def __init__(self, write=False):
                self.write = write

            def download(self):
                return b"raw-before", "BASE-HEAD"

            def compare_and_swap(self, base, packed):
                self_base = base
                assert self.write is True
                assert self_base == "BASE-HEAD"
                assert packed == b"raw-after"
                calls["cas"] += 1
                return {
                    "status": "PASS",
                    "state_fingerprint": "sha256:after",
                    "head_revision_id": "HEAD-AFTER",
                    "readback": "PASS",
                }

        def fake_materialize(raw, dest):
            self.assertEqual(raw, b"raw-before")
            Path(dest).mkdir(parents=True, exist_ok=True)
            return Path(dest), {"tower_revision": "sha256:before"}

        def fake_publish(root):
            (Path(root) / nexo_tower.LIVE_TOWER_NAME).write_bytes(b"raw-after")
            return {"status": "PASS", "revision": "sha256:after"}

        def fake_verify(raw):
            if raw == b"raw-before":
                return "sha256:before"
            if raw == b"raw-after":
                return "sha256:after"
            raise AssertionError(raw)

        with tempfile.TemporaryDirectory() as tmp:
            envelope = Path(tmp) / "handoff.json"
            envelope.write_text(json.dumps({
                "request_id": "REQ-CLI-HANDOFF-001",
                "from_role": "EXECUTOR",
                "to_role": "LEARNER",
                "handoff_type": "RESULT_READY",
                "entity_ref": "WORK::SCIENCE-CLI",
                "thread_id": "THR::SCIENCE::CLI",
                "summary_plain": "O resultado persistido está pronto para aprendizagem.",
                "why_it_matters": "A próxima automação pode continuar sem reconstruir o contexto.",
                "next_action": "Ler o resultado canônico e registrar a lição correspondente.",
                "evidence_refs": [{"ref": "TEST::SCIENCE-CLI", "kind": "TEST"}],
                "source_links": [{
                    "label": "Primary paper",
                    "url": "https://example.org/paper",
                    "access_date": "2026-09-27",
                    "publisher": "Example Collaboration",
                    "authors": ["A. Author"],
                    "date": "2026-09-26",
                    "supports": "Sustenta apenas a entrada observacional citada.",
                    "uncertainty": "Não é um resultado do NEXO.",
                    "next_test_impact": "Informa o próximo teste discriminante sem mudar critérios congelados.",
                }],
            }), encoding="utf-8")
            args = type("Args", (), {
                "action": "create",
                "envelope": str(envelope),
                "dry_run": False,
                "retries": 0,
            })()

            output = io.StringIO()
            with patch.object(nexo_tower, "DriveTower", FakeDriveTower), \
                 patch.object(nexo_tower, "writer_lock", lambda: FakeLock()), \
                 patch.object(nexo_tower, "materialize_live_tower", fake_materialize), \
                 patch.object(nexo_tower, "read_live_tower_bytes", lambda raw: raw), \
                 patch.object(nexo_tower, "verify_live_tower", fake_verify), \
                 patch("runtime.nexo_agent_api.live_tower.publish_live_tower", fake_publish), \
                 patch.object(nexo_tower, "_notify_atlas", lambda fingerprint: calls["notify"].append(fingerprint) or "DISPATCHED_TEST"), \
                 contextlib.redirect_stdout(output):
                code = nexo_tower.cmd_handoff(args)

        self.assertEqual(code, 0)
        self.assertEqual(calls["lock"], 1)
        self.assertEqual(calls["cas"], 1)
        self.assertEqual(calls["notify"], ["sha256:after"])
        payload = json.loads(output.getvalue())
        self.assertEqual(payload["status"], "PASS")
        self.assertEqual(payload["write"]["readback"], "PASS")
        self.assertEqual(payload["after"], "sha256:after")
        self.assertEqual(payload["handoff"]["request_id"], "REQ-CLI-HANDOFF-001")
        self.assertEqual(payload["handoff"]["source_links"][0]["access_date"], "2026-09-27")

    def test_apply_handoff_operation_uses_the_canonical_writer_path(self):
        from scripts import nexo_tower

        calls = {"lock": 0, "cas": 0, "notify": []}

        class FakeLock:
            def __enter__(self):
                calls["lock"] += 1
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

        class FakeDriveTower:
            def __init__(self, write=False):
                self.write = write

            def download(self):
                return b"raw-before", "BASE-HEAD"

            def compare_and_swap(self, base, packed):
                assert self.write is True
                assert base == "BASE-HEAD"
                assert packed == b"raw-after"
                calls["cas"] += 1
                return {"status": "PASS", "state_fingerprint": "sha256:after", "readback": "PASS"}

        def fake_materialize(raw, dest):
            self.assertEqual(raw, b"raw-before")
            Path(dest).mkdir(parents=True, exist_ok=True)
            return Path(dest), {"tower_revision": "sha256:before"}

        def fake_publish(root):
            (Path(root) / nexo_tower.LIVE_TOWER_NAME).write_bytes(b"raw-after")
            return {"status": "PASS", "state_fingerprint": "sha256:after", "readback": "PASS"}

        def fake_verify(raw):
            return {b"raw-before": "sha256:before", b"raw-after": "sha256:after"}[raw]

        handoff = {
            "request_id": "REQ-CLI-INBOX-HANDOFF-001",
            "from_role": "ADVISOR",
            "to_role": "EXECUTOR",
            "handoff_type": "RESEARCH_READY",
            "entity_ref": "WORK::DARK-ENERGY",
            "thread_id": "THR::DARK-ENERGY",
            "summary_plain": "Uma fonte nova ajuda a comparar duas explicações para a energia escura.",
            "why_it_matters": "A comparação pode mostrar qual hipótese merece o próximo teste.",
            "next_action": "Compare as previsões da fonte com o teste já planejado.",
        }
        output = io.StringIO()
        with tempfile.TemporaryDirectory() as tmp:
            request_file = Path(tmp) / "handoff.json"
            request_file.write_text(json.dumps({"nexo_operation": "HANDOFF_CREATE", "_inbox_source": "DRIVE",
                                                "handoff": handoff}), encoding="utf-8")
            args = argparse.Namespace(requests=[str(request_file)], retries=0, dry_run=False)
            with patch.object(nexo_tower, "DriveTower", FakeDriveTower), \
                 patch.object(nexo_tower, "writer_lock", lambda: FakeLock()), \
                 patch.object(nexo_tower, "materialize_live_tower", fake_materialize), \
                 patch.object(nexo_tower, "read_live_tower_bytes", lambda raw: raw), \
                 patch.object(nexo_tower, "verify_live_tower", fake_verify), \
                 patch("runtime.nexo_agent_api.live_tower.publish_live_tower", fake_publish), \
                 patch.object(nexo_tower, "_notify_atlas", lambda fingerprint: calls["notify"].append(fingerprint) or "DISPATCHED_TEST"), \
                 contextlib.redirect_stdout(output):
                code = nexo_tower.cmd_apply(args)

        self.assertEqual(code, 0)
        self.assertEqual(calls["lock"], 1)
        self.assertEqual(calls["cas"], 1)
        self.assertEqual(calls["notify"], ["sha256:after"])
        result = json.loads(output.getvalue())
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["write"]["readback"], "PASS")
        self.assertEqual(result["receipts"][0]["request_id"], handoff["request_id"])

if __name__ == "__main__":
    unittest.main()


class SiteFormatTests(unittest.TestCase):
    def test_new_hypothesis_inherits_roadmap_context_but_not_sibling_hypothesis(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sib = entity_path(root, "test", "S-1")
            sib.parent.mkdir(parents=True)
            sib.write_text(json.dumps({"id": "S-1", "campaign_id": "CAMP-X", "hypothesis_id": "HYP-X",
                                       "semantic": {"topic_id": "science.cosmology.dark_matter.nature"}}))
            (root / "roadmaps").mkdir()
            (root / "roadmaps" / "RM-X.json").write_text(json.dumps({"frontier_refs": ["S-1"]}))
            requests = proposal_to_requests({"kind": "HYPOTHESIS_PROPOSAL", "payload": {"display_name": "Teste de exemplo", "domain": "science", 
                "test_id": "H-2", "roadmap_id": "RM-X", "question": "Does X happen?",
                "success_criteria": "a", "kill_criteria": "b"}}, root)
            test = requests[0]["changes"]
            self.assertEqual(test["campaign_id"], "CAMP-X")
            self.assertEqual(test["hypothesis_id"], "HYP-H-2")  # nunca a hipótese do irmão
            self.assertEqual(test["roadmap_test_id"], "H-2")
            self.assertEqual(test["semantic"]["subdomain_id"], "science.cosmology.dark_matter")
            self.assertEqual(test["semantic"]["question_plain"], "Does X happen?")
            [merge] = [r for r in requests if "document" in r]
            self.assertEqual(merge["merge"]["frontier_refs"], ["S-1", "H-2"])
            [hyp] = [r for r in requests if r.get("entity_kind") == "hypothesis"]
            self.assertEqual(hyp["entity_name"], "HYP-H-2")
            self.assertEqual(hyp["changes"]["falsification_criterion"], "b")


class RedactTests(unittest.TestCase):
    def test_backfill_redacts_names_in_legacy_fields_but_not_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = entity_path(root, "campaign", "CAMP-OLY-JOAO-1")
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps({"id": "CAMP-OLY-JOAO-1", "entity_version": 2, "subject_code": "JOA",
                                        "title": "Campanha do Joao", "meta": {"display_name": "JOAO SILVA", "source_ref": "x/joao.csv"}}))
            [req] = proposal_to_requests({"kind": "SEMANTIC_BACKFILL", "payload": {"items": [
                {"id": "CAMP-OLY-JOAO-1", "entity_kind": "campaign", "redact_names": ["Joao", "Silva"]}]}}, root)
            self.assertEqual(req["changes"]["title"], "Campanha do JOA")
            self.assertEqual(req["changes"]["meta"], {"display_name": "JOA JOA", "source_ref": "x/JOA.csv"})
            self.assertNotIn("id", req["changes"])


class CampaignSemanticBackfillTests(unittest.TestCase):
    def test_new_roadmap_charter_keeps_public_plain_language(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            [request] = proposal_to_requests({"kind": "ROADMAP_CHARTER", "created_at": "2026-09-27T00:00:00Z", "payload": {
                "roadmap_id": "RM-NEW-CAMPAIGN",
                "title": "Pergunta sobre o Universo",
                "question": "Can the public data distinguish the competing models?",
                "semantic": {
                    "question_plain": "Os dados públicos conseguem distinguir os modelos em disputa?",
                    "why_it_matters": "A resposta mostra se novas observações podem testar essas explicações.",
                },
            }}, root)

            self.assertEqual(request["document"], "roadmaps/RM-NEW-CAMPAIGN.json")
            self.assertEqual(request["merge"]["title"], "Pergunta sobre o Universo")
            self.assertEqual(
                request["merge"]["semantic"]["question_plain"],
                "Os dados públicos conseguem distinguir os modelos em disputa?",
            )

    def test_campaign_backfill_updates_roadmap_copy_without_replacing_science_question(self):
        from runtime.nexo_agent_api.tower_apply import apply_document

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            roadmaps = root / "roadmaps"
            roadmaps.mkdir()
            path = roadmaps / "RM-DARK-ENERGY.json"
            original_question = "Is late-time acceleration consistent with Lambda?"
            path.write_text(json.dumps({
                "roadmap_id": "RM-DARK-ENERGY",
                "campaign_id": "CAMP-DARK-ENERGY",
                "title": "Nature of dark energy",
                "question": original_question,
                "semantic": {"domain_id": "science"},
            }), encoding="utf-8")

            [request] = proposal_to_requests({"kind": "SEMANTIC_BACKFILL", "payload": {"items": [{
                "id": "CAMP-DARK-ENERGY",
                "entity_kind": "campaign",
                "roadmap_id": "RM-DARK-ENERGY",
                "title": "Natureza da energia escura",
                "overwrite": True,
                "semantic": {
                    "question_plain": "A aceleração recente do Universo é compatível com uma constante cosmológica?",
                    "why_it_matters": "A resposta ajuda a distinguir uma constante de explicações que mudam com o tempo.",
                },
            }]}}, root)

            self.assertEqual(request["document"], "roadmaps/RM-DARK-ENERGY.json")
            receipt = apply_document(root, request)
            self.assertTrue(receipt["accepted"])
            self.assertEqual(receipt["readback"], "PASS")

            saved = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(saved["title"], "Natureza da energia escura")
            self.assertEqual(saved["question"], original_question)
            self.assertEqual(saved["semantic"]["domain_id"], "science")
            self.assertEqual(
                saved["semantic"]["question_plain"],
                "A aceleração recente do Universo é compatível com uma constante cosmológica?",
            )
