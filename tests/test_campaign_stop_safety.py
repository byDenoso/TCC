"""Regression tests for automatic roadmap closure; no scientific data or writes."""
from __future__ import annotations

from contextlib import ExitStack
from pathlib import Path
from unittest import TestCase, main
from unittest.mock import patch

from runtime.nexo_agent_api import gpt_writer


def roadmap(**changes):
    value = {
        "roadmap_id": "RM-SYNTHETIC", "charter_status": "CHARTERED",
        "state": "ACTIVE", "confirmed": 3, "tests_used": 3,
        "max_tests": 8, "days": 1, "max_days": 7,
        "renewable": False, "stop_reached": "SUCCESS",
    }
    value.update(changes)
    return value


class CampaignStopSafetyTests(TestCase):
    def closures(self, *rows):
        with ExitStack() as stack:
            stack.enter_context(patch.object(gpt_writer, "materialize_live_tower", return_value=(Path("/unused"), {})))
            stack.enter_context(patch.object(gpt_writer.evolution, "evolution_status", return_value={"roadmaps": list(rows)}))
            return gpt_writer._stop_closures(b"synthetic-unused")

    def test_success_threshold_is_not_automatic_protocol_completion(self):
        self.assertEqual(self.closures(roadmap()), [])

    def test_refutation_streak_does_not_skip_remaining_comparisons(self):
        self.assertEqual(self.closures(roadmap(stop_reached="KILL", confirmed=0)), [])

    def test_explicit_nonrenewable_test_budget_closes(self):
        result = self.closures(roadmap(stop_reached="BUDGET", tests_used=8))
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["payload"]["reason"], "BUDGET")

    def test_success_cannot_mask_exhausted_budget(self):
        result = self.closures(roadmap(stop_reached="SUCCESS", tests_used=8))
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["payload"]["reason"], "BUDGET")

    def test_refutation_cannot_mask_exhausted_time_budget(self):
        result = self.closures(roadmap(stop_reached="KILL", days=7))
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["payload"]["reason"], "BUDGET")

    def test_renewable_campaign_does_not_close_on_budget(self):
        self.assertEqual(self.closures(roadmap(renewable=True, tests_used=20)), [])

    def test_proposed_limits_are_not_authorization(self):
        self.assertEqual(self.closures(roadmap(charter_status="PROPOSED", tests_used=20)), [])

    def test_closed_charter_is_not_closed_again(self):
        self.assertEqual(self.closures(roadmap(charter_status="CLOSED", state="CLOSED", tests_used=20)), [])

    def test_missing_budget_does_not_invent_one(self):
        self.assertEqual(self.closures(roadmap(max_tests=None, max_days=None, tests_used=999)), [])

    def test_unverified_budget_label_is_not_enough(self):
        self.assertEqual(self.closures(roadmap(stop_reached="BUDGET", tests_used=2, days=1)), [])

    def test_bad_numeric_limits_do_not_close_or_crash(self):
        for invalid in (True, False, -1, 0, 1.5, "bad", "NaN", "Infinity", {}, []):
            with self.subTest(invalid=invalid):
                self.assertEqual(self.closures(roadmap(max_tests=invalid, max_days=None)), [])

    def test_unknown_elapsed_time_does_not_close(self):
        self.assertEqual(self.closures(roadmap(max_tests=None, days=None)), [])

    def test_schema_compatible_integer_strings(self):
        result = self.closures(roadmap(max_tests="8", tests_used=8))
        self.assertEqual(result[0]["payload"]["reason"], "BUDGET")

    def test_one_campaign_does_not_block_other_campaign(self):
        result = self.closures(roadmap(), roadmap(roadmap_id="RM-B", tests_used=8))
        self.assertEqual([row["payload"]["roadmap_id"] for row in result], ["RM-B"])

    def test_budget_report_is_not_a_scientific_verdict(self):
        result = self.closures(roadmap(stop_reached="BUDGET", tests_used=8))
        self.assertIn("nao", result[0]["payload"]["final_report"].lower())
        self.assertNotIn("CONFIRMED", result[0]["payload"])

    def test_repeat_derivation_is_stable_without_new_execution(self):
        row = roadmap(tests_used=8)
        a, b = self.closures(row)[0], self.closures(row)[0]
        self.assertEqual(a["_inbox_name"], b["_inbox_name"])
        self.assertEqual(a["payload"], b["payload"])

    def test_input_status_objects_are_not_mutated(self):
        row = roadmap()
        original = dict(row)
        self.closures(row)
        self.assertEqual(row, original)


if __name__ == "__main__":
    main()
