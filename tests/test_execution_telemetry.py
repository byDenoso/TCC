import unittest
from datetime import datetime, timezone

from nexo_control_plane.execution_telemetry import (
    ExecutionTrace,
    classify_failure_stage,
    derive_latency_metrics,
)


def ts(value):
    return datetime.fromisoformat(value).replace(tzinfo=timezone.utc)


class ExecutionTelemetryTests(unittest.TestCase):
    def test_full_trace_derives_end_to_end_latencies(self):
        trace = ExecutionTrace(
            accepted_at=ts("2026-09-15T10:00:00"),
            canonical_ready_at=ts("2026-09-15T10:00:02"),
            dispatched_at=ts("2026-09-15T10:00:05"),
            result_at=ts("2026-09-15T10:02:05"),
            canonical_closed_at=ts("2026-09-15T10:02:08"),
        )
        self.assertEqual(
            derive_latency_metrics(trace),
            {
                "time_to_canonical_ready_s": 2.0,
                "time_to_dispatch_s": 5.0,
                "time_to_result_s": 125.0,
                "time_to_canonical_close_s": 128.0,
            },
        )
        self.assertIsNone(classify_failure_stage(trace))

    def test_missing_stages_return_none_metrics(self):
        trace = ExecutionTrace(accepted_at=ts("2026-09-15T10:00:00"))
        metrics = derive_latency_metrics(trace)
        self.assertIsNone(metrics["time_to_canonical_ready_s"])
        self.assertIsNone(metrics["time_to_dispatch_s"])
        self.assertIsNone(metrics["time_to_result_s"])
        self.assertIsNone(metrics["time_to_canonical_close_s"])

    def test_failure_stage_is_attributed_to_first_failed_boundary(self):
        trace = ExecutionTrace(
            accepted_at=ts("2026-09-15T10:00:00"),
            canonical_ready_at=ts("2026-09-15T10:00:02"),
            failure_stage="DISPATCH",
        )
        self.assertEqual(classify_failure_stage(trace), "DISPATCH")

    def test_negative_or_out_of_order_latency_is_rejected(self):
        trace = ExecutionTrace(
            accepted_at=ts("2026-09-15T10:00:02"),
            canonical_ready_at=ts("2026-09-15T10:00:01"),
        )
        with self.assertRaises(ValueError):
            derive_latency_metrics(trace)


if __name__ == "__main__":
    unittest.main()
