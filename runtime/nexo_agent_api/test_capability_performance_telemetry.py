from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from .telemetry import enrich_materialized_state


class CapabilityPerformanceTelemetryTests(unittest.TestCase):
    def test_derives_per_capability_success_runtime_retry_and_cost_without_inventing_missing_values(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            for rel in ("entities/work", "snapshot", "runtime/artifacts"):
                (root / rel).mkdir(parents=True)
            (root / "snapshot/latest.json").write_text(json.dumps({"counts": {}}), encoding="utf-8")
            (root / "snapshot/ai-roi.json").write_text(json.dumps({"roi": {}}), encoding="utf-8")

            artifacts = [
                {
                    "id": "A1",
                    "run_id": "R1",
                    "capability_id": "solver.alpha",
                    "validation_status": "PASS",
                    "runtime_ms": 1200,
                    "retry_count": 1,
                    "measured_cost_usd": 0.25,
                },
                {
                    "id": "A2",
                    "run_id": "R2",
                    "capability_id": "solver.alpha",
                    "validation_status": "FAIL",
                    "runtime_ms": 800,
                    "retry_count": 0,
                    "measured_cost_usd": 0.15,
                },
                {
                    "id": "A3",
                    "run_id": "R3",
                    "capability_id": "solver.beta",
                    "validation_status": "PASS",
                },
                {
                    "id": "A4",
                    "run_id": "R4",
                    "validation_status": "PASS",
                    "runtime_ms": 10,
                },
            ]
            for artifact in artifacts:
                (root / "runtime/artifacts" / f"{artifact['id']}.json").write_text(json.dumps(artifact), encoding="utf-8")

            result = enrich_materialized_state(root)
            roi = json.loads((root / "snapshot/ai-roi.json").read_text(encoding="utf-8"))
            performance = roi["capability_performance"]

            self.assertEqual(performance["source"], "runtime/artifacts/*.json explicit capability/runtime/retry/cost fields only")
            self.assertEqual(performance["by_capability_id"]["solver.alpha"], {
                "attempts": 2,
                "successes": 1,
                "failures": 1,
                "success_rate": 0.5,
                "runtime_ms": {"samples": 2, "total": 2000.0, "average": 1000.0},
                "retries": {"samples": 2, "total": 1, "average": 0.5},
                "cost_usd": {"samples": 2, "total": 0.4, "average": 0.2},
            })
            self.assertEqual(performance["by_capability_id"]["solver.beta"]["success_rate"], 1.0)
            self.assertEqual(performance["by_capability_id"]["solver.beta"]["runtime_ms"], {"samples": 0, "status": "UNAVAILABLE"})
            self.assertEqual(performance["by_capability_id"]["solver.beta"]["retries"], {"samples": 0, "status": "UNAVAILABLE"})
            self.assertEqual(performance["by_capability_id"]["solver.beta"]["cost_usd"], {"samples": 0, "status": "UNAVAILABLE"})
            self.assertEqual(result["capability_performance"], performance)


if __name__ == "__main__":
    unittest.main()
