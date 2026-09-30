from __future__ import annotations

import copy
import json
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from .discovery import DECISIVE, autonomy_metrics


NOW = datetime(2026, 9, 30, 12, tzinfo=timezone.utc)


def result(verdict="PROMOTED", **fields):
    return {"verdict": verdict, "executed_at": "2026-09-30T11:00:00Z", **fields}


class AutonomyMetricsTests(unittest.TestCase):
    def test_empty_cohorts_are_unknown_ratios_not_zero_or_perfect_scores(self):
        out = autonomy_metrics([], now=NOW)
        self.assertEqual(out["schema_version"], "AUTONOMY_METRICS_V2")
        self.assertEqual(out["computed_at"], "2026-09-30T12:00:00Z")
        self.assertEqual(out["window_end"], out["computed_at"])
        self.assertEqual(out["window_start"], "2026-09-29T12:00:00Z")
        for name, metric in out["metrics"].items():
            self.assertTrue({"value", "numerator", "denominator", "scope", "definition", "unit"} <= metric.keys())
            self.assertEqual(metric["value"], 0 if name == "results" else None)
            if metric["unit"] == "ratio":
                self.assertEqual((metric["numerator"], metric["denominator"]), (0, 0))
        latency = out["metrics"]["median_hours_to_result"]
        self.assertIsNone(latency["numerator"])
        self.assertIsNone(latency["denominator"])
        self.assertEqual(latency["coverage"], {"value": None, "numerator": 0, "denominator": 0})
        json.dumps(out, allow_nan=False)

    def test_window_has_both_boundaries_and_excludes_future_invalid_missing_and_contests(self):
        tests = [
            result(executed_at="2026-09-29T12:00:00Z"),
            result(executed_at={"at": "2026-09-30T12:00:00Z"}),
            result(executed_at="2026-09-30T12:00:00.000001Z"),
            result(executed_at="2026-09-29T11:59:59Z"),
            result(executed_at="invalid"), result(executed_at=None),
            result(executed_at={}), result(contests_test_id="SOURCE"),
            result(verdict=None), result(verdict=""),
        ]
        out = autonomy_metrics(tests, now=NOW)
        self.assertEqual(out["results"], 2)
        self.assertEqual(out["buckets"]["result_verdicts"], {"PROMOTED": 2})

    def test_naive_and_offset_times_share_the_utc_window(self):
        out = autonomy_metrics([
            result(executed_at="2026-09-30T11:00:00", created_at_effective="2026-09-30T10:00:00"),
            result(executed_at="2026-09-30T14:00:00+03:00", first_observed_at="2026-09-30T13:00:00+03:00"),
        ], hours=2, now=NOW.astimezone(timezone(timedelta(hours=3))))
        self.assertEqual(out["results"], 2)
        self.assertEqual(out["median_hours_to_result"], 1.0)
        self.assertEqual(out["window_start"], "2026-09-30T10:00:00Z")
        self.assertEqual(autonomy_metrics([], now=NOW.replace(tzinfo=None))["computed_at"], out["computed_at"])

    def test_execution_metadata_is_only_a_recording_proxy(self):
        tests = [result(family_id="F", created_by="human"), result(execution={"runner": "agent"}),
                 result(family_id="", execution={}), result()]
        out = autonomy_metrics(tests, now=NOW)
        metric = out["metrics"]["execution_record_share"]
        self.assertEqual((metric["value"], metric["numerator"], metric["denominator"]), (0.5, 2, 4))
        self.assertEqual(out["robot_share"], 0.5)
        self.assertIn("does not establish absence", metric["definition"])
        self.assertEqual(out["buckets"]["result_execution_records"], {"execution_or_family": 2, "neither": 2})

    def test_unknown_and_contested_verdicts_do_not_inflate_canonical_decisive_rate(self):
        tests = [result(verdict=v.lower()) for v in sorted(DECISIVE)]
        tests += [result(verdict=v) for v in ("INCONCLUSIVE", "INCONCLUSIVO", "CONTESTED", "FUTURE_LABEL", "SUPPORTED")]
        out = autonomy_metrics(tests, now=NOW)
        canonical = out["metrics"]["decisive_rate"]
        self.assertEqual((canonical["value"], canonical["numerator"], canonical["denominator"]), (round(6 / 11, 3), 6, 11))
        self.assertEqual(canonical["verdicts"], sorted(DECISIVE))
        self.assertEqual(out["decisive_rate"], round(9 / 11, 3))
        self.assertEqual(out["info_per_test"], out["decisive_rate"])
        self.assertEqual(out["metrics"]["non_inconclusive_rate"]["definition_id"], "LEGACY_NON_INCONCLUSIVE")
        self.assertEqual(out["buckets"]["result_categories"], {"decisive": 6, "inconclusive": 2, "other": 3})

    def test_stock_cohorts_are_independent_of_execution_window(self):
        tests = [
            result(executed_at="2020-01-01T00:00:00Z", review_state="CONFIRMED"),
            result(verdict="PROMOVIDO", executed_at=None, review_state="REFUTED"),
            result(verdict="SUPPORTED", review_state="OPEN"),
            result(review_state="CONFIRMED", contests_test_id="SOURCE", runtime_failure_count=1),
            result(verdict="REJECTED", runtime_failure_count=2),
            result(verdict=None, runtime_failure_count=1),
        ]
        out = autonomy_metrics(tests, now=NOW)
        closure = out["metrics"]["positive_review_closure"]
        recovery = out["metrics"]["failure_result_coverage"]
        self.assertEqual(out["results"], 2)
        self.assertEqual((closure["numerator"], closure["denominator"], closure["scope"]), (2, 3, "all_tests"))
        self.assertEqual((recovery["numerator"], recovery["denominator"], recovery["scope"]), (2, 3, "all_tests"))
        self.assertEqual(out["buckets"]["positive_review_states"], {"CONFIRMED": 1, "OPEN": 1, "REFUTED": 1})
        self.assertEqual(out["buckets"]["failure_results"], {"with_verdict": 2, "without_verdict": 1})

    def test_blocked_share_is_one_with_zero_ready_and_is_not_a_false_block_measure(self):
        out = autonomy_metrics([{"status": "blocked_input"}, {"status": "BLOCKED_REVIEW", "contests_test_id": "T"},
                                {"status": "RUNNING"}, {}], now=NOW)
        metric = out["metrics"]["blocked_share"]
        self.assertEqual((metric["value"], metric["numerator"], metric["denominator"]), (1.0, 2, 2))
        self.assertEqual(out["buckets"]["queue_statuses"], {"ready": 0, "blocked": 2, "other": 2})
        self.assertIn("Does not classify any block as false", metric["definition"])
        self.assertEqual(autonomy_metrics([{"status": "READY"}, {"status": "BLOCKED"}], now=NOW)["false_block_share"], 0.5)

    def test_latency_reports_sample_coverage_and_reasons_for_missing_measurements(self):
        out = autonomy_metrics([
            result(created_at_effective="2026-09-30T10:00:00Z"),
            result(first_observed_at="2026-09-30T08:00:00Z"), result(),
            result(created_at_effective="bad", first_observed_at="2026-09-30T08:00:00Z"),
            result(created_at_effective="2026-09-30T11:00:01Z"),
        ], now=NOW)
        metric = out["metrics"]["median_hours_to_result"]
        self.assertEqual(metric["value"], 2.0)
        self.assertEqual(metric["sample_count"], 2)
        self.assertEqual(metric["coverage"], {"value": 0.4, "numerator": 2, "denominator": 5})
        self.assertEqual(out["buckets"]["latency_coverage"], {"measured": 2, "missing_start": 1, "invalid_start": 1, "start_after_execution": 1})

    def test_legacy_aliases_preserve_original_meaning_without_mutating_scientific_records(self):
        tests = [result(verdict="CONTESTED", execution={"nested": ["input"]}, review_state="CONFIRMED", status="BLOCKED_INPUT"),
                 result(verdict="INCONCLUSIVE", runtime_failure_count=1), result(first_observed_at="2026-09-30T10:00:00Z")]
        before = copy.deepcopy(tests)
        out = autonomy_metrics(tests, now=NOW)
        self.assertEqual(tests, before)
        for alias, canonical in out["legacy_aliases"].items():
            self.assertEqual(out[alias], out["metrics"][canonical]["value"])
        self.assertNotEqual(out["decisive_rate"], out["metrics"]["decisive_rate"]["value"])

    def test_canonical_latency_uses_recorded_creation_with_explicit_precedence(self):
        out = autonomy_metrics([
            result(created_at="2026-09-30T09:00:00Z"),
            result(created_at="2026-09-30T07:00:00Z", first_observed_at="2026-09-30T10:00:00Z"),
            result(created_at_effective="2026-09-30T05:00:00Z", created_at="2026-09-30T09:00:00Z"),
            result(first_observed_at="2026-09-30T03:00:00Z"), result(),
        ], now=NOW)
        canonical = out["metrics"]["median_hours_to_result"]
        self.assertEqual(canonical["value"], 5.0)
        self.assertEqual(canonical["coverage"], {"value": 0.8, "numerator": 4, "denominator": 5})
        self.assertEqual(out["buckets"]["latency_start_sources"], {
            "created_at_effective": 1, "created_at": 2, "first_observed_at": 1, "missing": 1,
        })
        self.assertEqual(out["median_hours_to_result"], 6.0)
        self.assertEqual(out["metrics"]["legacy_median_hours_to_result"]["coverage"], {
            "value": 0.6, "numerator": 3, "denominator": 5,
        })
        only_creation = autonomy_metrics([result(created_at="2026-09-30T10:00:00Z")], now=NOW)
        self.assertEqual(only_creation["metrics"]["median_hours_to_result"]["value"], 1.0)
        self.assertIsNone(only_creation["median_hours_to_result"])

    def test_discovery_projection_preserves_metadata(self):
        from .evolution import evolution_status

        with TemporaryDirectory() as td:
            out = evolution_status(Path(td), now=NOW, public=True)
        self.assertEqual(out["autonomy"]["schema_version"], "AUTONOMY_METRICS_V2")
        self.assertEqual(out["autonomy"]["computed_at"], "2026-09-30T12:00:00Z")
        self.assertIn("metrics", out["autonomy"])
        self.assertIn("buckets", out["autonomy"])


if __name__ == "__main__":
    unittest.main()
