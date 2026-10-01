"""Offline recovery fixtures; no credentials, network, or scientific computation."""
import copy
import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from runtime.nexo_agent_api import evolution as e, execution_recovery as r, scientific_integrity as s
from runtime.nexo_agent_api.gpt_writer import apply_to_tower
from runtime.nexo_agent_api.live_tower import build_live_tower_payload, read_live_tower_bytes, materialize_live_tower
from runtime.nexo_agent_api.tower_apply import apply_requests
from runtime.nexo_agent_api.tower_paths import entity_path
from tests.test_scientific_integrity import fixture, save, NOW


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "tower"
        self.recipes = Path(self.tmp.name) / "recipes"
        self.env = patch.dict(os.environ, {"NEXO_RECIPE_ROOT": str(self.recipes)})
        self.env.start()
        save(self.root, "CONTROL.json", {"mode": "ACTIVE", "truth_owner": "TOWER_V06@GOOGLE_DRIVE_PRIVATE"})
        self.test = fixture()
        self.install("audit_recipe")
        self.put(self.test)

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def install(self, name):
        save(self.recipes, "smoke/" + name + ".json", {})
        (self.recipes / (name + ".py")).write_text("result = 1\n")

    def put(self, test):
        save(self.root, entity_path(self.root, "test", test["id"]).relative_to(self.root).as_posix(), test)

    def apply(self):
        raw = json.dumps(build_live_tower_payload(self.root)).encode()
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            result, report = apply_to_tower(raw, [])
        return read_live_tower_bytes(result or raw), report

    def reconcile(self):
        with redirect_stderr(io.StringIO()):
            receipts = apply_requests(self.root, r.reconcile_requests(self.root))
        self.assertTrue(all(x.get("accepted") for x in receipts), receipts)
        return receipts

    def works(self):
        return r._entities(self.root, "work")

    def test_legacy_ready_becomes_owned_repair_without_scientific_changes(self):
        self.test.pop("recipe"); self.test.pop("recipe_params"); self.test.pop("data_binding")
        self.put(self.test)
        before = {k: self.test.get(k) for k in s.FROZEN}
        output, report = self.apply()
        self.assertFalse(report["rejected"], report)
        test = output["files"][entity_path(self.root, "test", "TEST-A").relative_to(self.root).as_posix()]["value"]
        work = next(v["value"] for p, v in output["files"].items() if p.startswith("entities/work/"))
        self.assertEqual(test["status"], "CHECKPOINTED")
        self.assertTrue(test["recovery_required"])
        self.assertFalse(test["readiness"]["eligible"])
        self.assertEqual({k: test.get(k) for k in s.FROZEN}, before)
        self.assertEqual(work["owner_role"], "ADVISOR")
        self.assertEqual(work["recovery"]["ownership_state"], "ASSIGNED_UNACCEPTED")
        self.assertEqual(report["execution_recovery"]["handoffs_created"], 1)
        events = [v["value"] for p, v in output["files"].items() if p.startswith("events/") and v.get("value", {}).get("handoff_type") == "BLOCKER_RECOVERY"]
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["state"], "PENDING")

    def test_legacy_blocked_verdict_is_operational_and_recoverable(self):
        self.test.pop("data_binding")
        self.test.update(status="BLOCKED_INPUT", state="BLOCKED_INPUT", verdict="BLOCKED_INPUT")
        self.put(self.test)
        self.reconcile()
        current = s.entity(self.root, "TEST-A")
        self.assertEqual(current["status"], "CHECKPOINTED")
        self.assertTrue(current["recovery_required"])
        self.assertIsNone(current.get("verdict"))
        self.assertTrue(self.works())

    def test_nonstandard_blocked_state_enters_recovery(self):
        self.test.pop("data_binding")
        self.test.update(status=None, state="BLOCKED_SCIENTIFIC_CONTRACT")
        self.put(self.test)
        self.reconcile()
        current = s.entity(self.root, "TEST-A")
        self.assertEqual(current["status"], "CHECKPOINTED")
        self.assertTrue(current["recovery_required"])
        self.assertTrue(self.works())

    def test_replay_reuses_same_fingerprint_owner_and_route(self):
        self.test.pop("data_binding"); self.put(self.test)
        first, _ = self.apply()
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            result, report = apply_to_tower(json.dumps(first).encode(), [])
        self.assertIsNone(result)
        self.assertEqual(report["execution_recovery"], {"mutations": 0, "handoffs_created": 0})

    def test_existing_owner_is_preserved_and_no_acceptance_is_invented(self):
        self.test.pop("data_binding"); self.put(self.test)
        save(self.root, "entities/work/existing.json", {"id": "existing", "test_id": "TEST-A", "owner_role": "EXECUTOR", "status": "CHECKPOINTED"})
        self.reconcile()
        work = next(w for w in self.works() if w.get("kind") == "DEPENDENCY_RECOVERY")
        self.assertEqual(work["owner_role"], "EXECUTOR")
        self.assertEqual(work["recovery"]["owner_source"], "EXISTING_WORK_OWNER")
        self.assertNotIn("acceptance_source", work["recovery"])

    def artifact(self, name, payload):
        save(self.root, "entities/artifact/" + name + ".json", {"id": name, "kind": "DATA_BINDING", "payload": payload})

    def test_recover_only_unique_hash_validated_frozen_binding(self):
        binding = self.test.pop("data_binding"); self.put(self.test)
        self.artifact("record", {**binding, "test_id": "TEST-A", "prereg_hash": self.test["prereg_hash"]})
        self.reconcile()
        current = s.entity(self.root, "TEST-A")
        self.assertEqual(current["data_binding"], binding)
        self.assertEqual(current["binding_recovery_refs"], ["record"])
        self.assertEqual(current["status"], "READY")
        self.assertEqual(self.works(), [])

    def test_old_bound_label_without_provenance_cannot_supply_inputs(self):
        self.test.pop("data_binding"); self.put(self.test)
        self.artifact("record", {"test_id": "TEST-A", "status": "BOUND", "inputs": [{"name": "data", "url": "https://example.org"}]})
        self.reconcile()
        self.assertNotIn("data_binding", s.entity(self.root, "TEST-A"))
        self.assertEqual(self.works()[0]["recovery"]["candidate_artifact_refs"], ["record"])

    def test_valid_input_without_frozen_commitment_is_only_a_candidate(self):
        binding = self.test.pop("data_binding"); self.put(self.test)
        self.artifact("record", {**binding, "test_id": "TEST-A"})
        self.reconcile()
        self.assertNotIn("data_binding", s.entity(self.root, "TEST-A"))

    def test_conflicting_bindings_never_pick_a_convenient_source(self):
        binding = self.test.pop("data_binding"); self.put(self.test)
        self.artifact("a", {**binding, "test_id": "TEST-A", "prereg_hash": self.test["prereg_hash"]})
        other = copy.deepcopy(binding); other["inputs"][0]["seed"] = 18
        self.artifact("b", {**other, "test_id": "TEST-A", "prereg_hash": self.test["prereg_hash"]})
        self.reconcile()
        self.assertNotIn("data_binding", s.entity(self.root, "TEST-A"))
        self.assertIn("CONFLICTING_RECORDED_DATA_BINDING", self.works()[0]["recovery"]["reasons"])

    def test_historical_conflicts_do_not_invalidate_canonical_binding(self):
        binding = copy.deepcopy(self.test["data_binding"])
        self.artifact("a", {**binding, "test_id": "TEST-A", "prereg_hash": self.test["prereg_hash"]})
        binding["inputs"][0]["seed"] = 18
        self.artifact("b", {**binding, "test_id": "TEST-A", "prereg_hash": self.test["prereg_hash"]})
        self.reconcile()
        self.assertEqual(s.entity(self.root, "TEST-A")["status"], "READY")
        self.assertEqual(self.works(), [])

    def test_same_error_on_distinct_scientific_tests_is_not_collapsed(self):
        self.test.pop("data_binding"); self.put(self.test)
        other = fixture("TEST-B"); other.pop("data_binding"); self.put(other)
        self.reconcile()
        self.assertEqual(len(self.works()), 2)
        self.assertEqual(len({w["recovery"]["fingerprint"] for w in self.works()}), 2)

    def test_resolved_repair_closes_only_after_readiness(self):
        binding = self.test.pop("data_binding"); self.put(self.test); self.reconcile()
        current = s.entity(self.root, "TEST-A"); current["data_binding"] = binding; self.put(current)
        self.reconcile()
        self.assertEqual(s.entity(self.root, "TEST-A")["status"], "READY")
        self.assertEqual(self.works()[0]["status"], "DONE")
        self.assertEqual(self.works()[0]["completion_evidence"]["kind"], "READINESS_VALIDATED")

    def test_existing_scientific_blocker_is_not_erased(self):
        self.test["blocker"] = "A frozen methodological decision remains unresolved"
        self.test["status"] = self.test["state"] = "BLOCKED_INPUT"; self.put(self.test)
        self.reconcile(); self.reconcile()
        self.assertEqual(s.entity(self.root, "TEST-A")["blocker"], self.test["blocker"])

    def test_automatic_completion_can_reopen_but_manual_retirement_cannot(self):
        binding = self.test.pop("data_binding"); self.put(self.test); self.reconcile()
        current = s.entity(self.root, "TEST-A"); current["data_binding"] = binding; self.put(current); self.reconcile()
        self.assertEqual(self.works()[0]["status"], "DONE")
        (self.recipes / "audit_recipe.py").unlink()
        self.reconcile()
        self.assertEqual(self.works()[0]["status"], "WAIT_DEPENDENCY")
        self.assertEqual(self.works()[0]["recovery"]["route_generation"], 2)
        work = self.works()[0]; work["status"] = "REJECTED"
        save(self.root, entity_path(self.root, "work", work["id"]).relative_to(self.root).as_posix(), work)
        self.reconcile()
        self.assertEqual(self.works()[0]["status"], "REJECTED")

    def test_completed_repair_supersedes_offer_without_fabricating_acceptance(self):
        binding = self.test.pop("data_binding"); self.put(self.test); self.reconcile(); r.ensure_handoffs(self.root)
        current = s.entity(self.root, "TEST-A"); current["data_binding"] = binding; self.put(current); self.reconcile()
        r.ensure_handoffs(self.root)
        from runtime.nexo_agent_api.handoff import _latest_by_handoff
        events = list(_latest_by_handoff(self.root).values())
        self.assertEqual(events[0]["state"], "SUPERSEDED")
        self.assertNotIn("acceptance_source", self.works()[0]["recovery"])

    def test_route_cycle_has_new_identity_and_preserves_current_owner(self):
        self.test.pop("data_binding"); self.test.pop("recipe"); self.test.pop("recipe_params"); self.put(self.test)
        self.reconcile(); r.ensure_handoffs(self.root)
        current = s.entity(self.root, "TEST-A"); current.update(recipe="audit_recipe", recipe_params={"seed": 17}); self.put(current)
        self.reconcile(); r.ensure_handoffs(self.root)
        (self.recipes / "audit_recipe.py").unlink()
        self.reconcile(); r.ensure_handoffs(self.root)
        from runtime.nexo_agent_api import AgentService
        from runtime.nexo_agent_api.handoff import _latest_by_handoff
        events = list(_latest_by_handoff(self.root).values())
        self.assertEqual(len(events), 3)
        inbox = AgentService(self.root).inbox_for("ADVISOR")
        self.assertEqual(len(inbox), 1)
        self.assertEqual(inbox[0]["work_envelope"]["recovery"]["route_generation"], 3)
        self.assertEqual(self.works()[0]["owner_role"], "ADVISOR")

    def test_reserved_terminal_and_private_tests_are_not_reclassified(self):
        for name, changes in [("terminal", {"status": "DONE", "verdict": "INCONCLUSIVE"}), ("private", {"private": True}), ("queued", {"status": "QUEUED"})]:
            test = fixture(name); test.update(changes); test.pop("data_binding"); self.put(test)
        self.reconcile()
        self.assertEqual(self.works(), [])

    def test_stale_cas_rejects_repair_request(self):
        self.test.pop("data_binding"); self.put(self.test)
        requests = r.reconcile_requests(self.root)
        current = copy.deepcopy(self.test); current["entity_version"] = 2; self.put(current)
        test_request = next(x for x in requests if x["entity_kind"] == "test")
        with redirect_stderr(io.StringIO()):
            receipts = apply_requests(self.root, [test_request])
        self.assertFalse(receipts[0]["accepted"])

    def test_private_recovery_details_never_enter_public_status(self):
        self.test.pop("data_binding"); self.put(self.test); self.reconcile()
        self.assertIn("execution_recovery", e.evolution_status(self.root))
        self.assertNotIn("execution_recovery", e.evolution_status(self.root, public=True))

    def test_route_failure_rolls_back_repairs_but_keeps_independent_proposal(self):
        self.test.pop("data_binding"); self.put(self.test)
        raw = json.dumps(build_live_tower_payload(self.root)).encode()
        proposal = {"kind": "BOARD_POST", "source": "EXECUTOR", "payload": {"to": "ALL", "text": "Verificação operacional em andamento."}}
        with patch.object(r, "ensure_handoffs", side_effect=RuntimeError("isolated route failure")), \
                redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            result, report = apply_to_tower(raw, [proposal])
        output = read_live_tower_bytes(result)
        self.assertTrue(output["files"][e.BOARD_DOC]["value"]["posts"])
        self.assertFalse(any(p.startswith("entities/work/") for p in output["files"]))
        self.assertEqual(report["rejected"][0]["item"], "execution-recovery")

    def test_cancelled_repair_is_not_reopened(self):
        self.test.pop("data_binding"); self.put(self.test); self.reconcile()
        work = self.works()[0]; work["status"] = "CANCELLED"
        save(self.root, entity_path(self.root, "work", work["id"]).relative_to(self.root).as_posix(), work)
        self.reconcile()
        self.assertEqual(self.works()[0]["status"], "CANCELLED")

    def test_global_priority_beats_recipe_alphabet_and_dener_overrides(self):
        self.install("zz_recipe")
        save(self.root, "indexes/active-roadmaps.json", {"items": [
            {"roadmap_id": "RM-A", "state": "ACTIVE", "priority": "P0"},
        ]})
        self.test["roadmap_id"] = "RM-A"
        self.test.update(recipe="audit_recipe", priority="LOW"); self.put(self.test)
        other = fixture("TEST-Z"); other.update(recipe="zz_recipe", priority="P0", origin_kind="DENER_DIRECTED",
                                                roadmap_id="RM-A"); self.put(other)
        save(self.root, e.BATTERIES_DOC, {"batteries": [{"id": "occupied1", "status": "RUNNING"}, {"id": "occupied2", "status": "RUNNING"}]})
        items = e.family_battery_items(self.root)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["payload"]["tests"][0]["test_id"], "TEST-Z")

    def test_active_roadmap_wins_and_closed_contest_remains_schedulable(self):
        self.install("zz_recipe")
        save(self.root, "indexes/active-roadmaps.json", {"items": [{"roadmap_id": "RM-A", "state": "CLOSED", "priority": "P0"}, {"roadmap_id": "RM-B", "state": "ACTIVE", "priority": "P1"}]})
        self.test["contests_test_id"] = "old"; self.put(self.test)
        other = fixture("TEST-Z"); other.update(recipe="zz_recipe", roadmap_id="RM-B"); self.put(other)
        items = e.family_battery_items(self.root)
        self.assertEqual(items[0]["payload"]["tests"][0]["test_id"], "TEST-Z")
        self.assertEqual(items[1]["payload"]["tests"][0]["test_id"], "TEST-A")

    def test_family_generator_skips_closed_roadmap_but_not_active_successor(self):
        family = {"family_id": "F-ONE", "roadmap_id": "RM-A", "state": "CLOSED", "close_reason": "SUCCESS",
                  "recipe": "w0wa_bao_sn_multi", "domain": "SCIENCE", "template": {"display_name": "Exemplo"},
                  "instances": [{"label": "A", "params": {"compilations": ["pantheon_plus", "des_sn5yr"]}}]}
        save(self.root, e.FAMILIES_DOC, {"families": {"F-ONE": family}})
        save(self.root, "roadmaps/RM-A.json", {"state": "CLOSED", "charter": {"status": "CLOSED"}})
        self.assertEqual(e.family_spawn_items(self.root), [])
        save(self.root, "roadmaps/RM-A.json", {"state": "ACTIVE", "charter": {"status": "CHARTERED"}})
        self.assertEqual(e.family_spawn_items(self.root)[0]["payload"]["family_id"], "F-ONE-R")

    def test_agent_contracts_do_not_remove_required_provenance_or_fake_ready(self):
        repo = Path(__file__).resolve().parents[1]
        for version in ("0.4.0", "0.5.0"):
            text = (repo / f"gpt/skills/nexo-closed-loop-{version}.md").read_text()
            self.assertNotIn("sem `sha256`", text)
            self.assertNotIn("fica READY (não bloqueado)", text)
            self.assertIn("inputs[{name, url, version, sha256}]", text)
        workspace = (repo / "gpt/skills/nexo-workspace/SKILL.md").read_text()
        for required in ("execution_recovery", "HANDOFF_ACK", "ADVISOR", "LEARNER", "EXECUTOR", "Drive privado NEXO_INBOX"):
            self.assertIn(required, workspace)

    def test_board_preserves_engineer_and_rejects_unknown_recipient(self):
        from runtime.nexo_agent_api.inbox_apply import proposal_to_requests
        item = {"kind": "BOARD_POST", "source": "EXECUTOR", "payload": {"to": "ENGINEER", "text": "Verificar a receita."}}
        requests = proposal_to_requests(item, self.root)
        self.assertEqual(requests[0]["merge"]["posts"][0]["to"], "ENGINEER")
        item["payload"]["to"] = "TYPO_RECIPIENT"
        requests = proposal_to_requests(item, self.root)
        self.assertEqual(requests[0]["changes"]["kind"], "UNAPPLIED_BOARD_POST")
        self.assertEqual(requests[0]["changes"]["payload"]["_not_applied_reason"], "BOARD_RECIPIENT_UNSUPPORTED")

    def test_empty_thought_and_duplicate_board_have_explicit_noop_reason(self):
        from runtime.nexo_agent_api.inbox_apply import proposal_to_requests
        thought = proposal_to_requests({"kind": "NEXO_THOUGHT", "payload": {"entries": []}}, self.root)
        self.assertEqual(thought[0]["changes"]["payload"]["_noop_reason"], "NO_GROUNDED_THOUGHT_ENTRIES")
        save(self.root, e.BOARD_DOC, {"posts": [{"from": "EXECUTOR", "to": "ENGINEER", "text": "Verificar a receita."}]})
        board = proposal_to_requests({"kind": "BOARD_POST", "source": "EXECUTOR", "payload": {"to": "ENGINEER", "text": "Verificar a receita."}}, self.root)
        self.assertEqual(board[0]["changes"]["payload"]["_noop_reason"], "BOARD_MESSAGE_ALREADY_RECORDED")

    def test_invalid_family_is_rejected_instead_of_silent_noop(self):
        from runtime.nexo_agent_api.inbox_apply import proposal_to_requests
        requests = proposal_to_requests({"kind": "FAMILY_CHARTER", "payload": {"roadmap_id": "missing"}}, self.root)
        self.assertEqual(requests[0]["changes"]["kind"], "UNAPPLIED_FAMILY_CHARTER")
        self.assertEqual(requests[0]["changes"]["payload"]["_not_applied_reason"], "FAMILY_ROADMAP_NOT_ACTIVE")

    def test_review_queue_and_admission_share_existing_contest_eligibility(self):
        parent = fixture("PARENT"); parent.update(verdict="PROMOTED", status="DONE", state="DONE", review_state="CONTESTED", contests=[{"contest_test_id": "ATTACK"}])
        child = fixture("ATTACK"); child.update(status="BLOCKED_INPUT", state="BLOCKED_INPUT", contests_test_id="PARENT")
        self.put(parent); self.put(child)
        queue = e._review_queue([parent], self.root)
        self.assertEqual(queue["referee_1"], [])
        self.assertEqual(queue["waiting_on_existing_contest"], ["PARENT"])
        requests = e.contest_requests({}, {"test_id": "PARENT"}, self.root, lambda *args: [])
        self.assertEqual(requests.reason, "EXISTING_CONTEST_REQUIRES_COMPLETION")
        child["verdict"] = "INCONCLUSIVE"; self.put(child)
        self.assertEqual(e._review_queue([parent], self.root)["referee_1"], ["PARENT"])
        self.assertIsNone(e.contest_admission_reason(self.root, parent))

    def test_emergence_does_not_demand_duplicate_contest_for_blocked_child(self):
        from datetime import datetime, timezone
        parent = fixture("PARENT"); parent.update(verdict="PROMOTED", status="DONE", state="DONE", review_state="CONTESTED", contests=[{"contest_test_id": "ATTACK"}])
        child = fixture("ATTACK"); child.update(status="BLOCKED_INPUT", state="BLOCKED_INPUT", contests_test_id="PARENT")
        self.put(parent); self.put(child)
        status = e._emergence(self.root, [parent, child], {}, datetime(2026, 9, 30, 20, tzinfo=timezone.utc))
        self.assertNotIn("contest", [row["loop"] for row in status["stale"]])


if __name__ == "__main__":
    unittest.main()
