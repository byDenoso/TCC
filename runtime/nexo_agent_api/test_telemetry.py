from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from .telemetry import enrich_materialized_state
from runtime.nexo_agent_api.tower_paths import entity_path


class TelemetryTests(unittest.TestCase):
    def _base_root(self, td: str) -> Path:
        root = Path(td)
        for rel in (
            "entities/work",
            "entities/hypothesis",
            "entities/test",
            "events/2026-09-15",
            "mutations/receipts",
            "snapshot",
        ):
            (root / rel).mkdir(parents=True, exist_ok=True)
        (root / "snapshot/latest.json").write_text(
            json.dumps({"schema_version": "0.6", "counts": {"hypotheses": 999, "tests": 999}}),
            encoding="utf-8",
        )
        (root / "snapshot/ai-roi.json").write_text(
            json.dumps({
                "schema_version": "0.6",
                "events": {"runtime_total": 0, "material": 0},
                "roi": {"mode": "PROXY_ONLY_NO_COST_DATA", "useful_output_proxies": {}},
            }),
            encoding="utf-8",
        )
        return root

    def test_recomputes_semantic_counts_from_canonical_entities(self):
        with tempfile.TemporaryDirectory() as td:
            root = self._base_root(td)
            for name in ("H1", "H2"):
                (root / f"entities/hypothesis/{name}.json").write_text("{}", encoding="utf-8")
            (entity_path(root, "test", "T1")).write_text("{}", encoding="utf-8")

            enrich_materialized_state(root)

            snapshot = json.loads((root / "snapshot/latest.json").read_text(encoding="utf-8"))
            self.assertEqual(snapshot["counts"]["hypotheses"], 2)
            self.assertEqual(snapshot["counts"]["tests"], 1)
            self.assertEqual(snapshot["semantic_freshness"], "CURRENT_CANONICAL_ENTITY_SCAN")

    def test_derives_conservative_autonomy_and_delivery_metrics(self):
        with tempfile.TemporaryDirectory() as td:
            root = self._base_root(td)
            (entity_path(root, "work", "W-DONE")).write_text(
                json.dumps({"id": "W-DONE", "status": "DONE"}), encoding="utf-8"
            )
            (entity_path(root, "work", "W-VERIFIED")).write_text(
                json.dumps({"id": "W-VERIFIED", "status": "VERIFIED"}), encoding="utf-8"
            )
            events = (
                ("20260915T120000000000Z-human000.json", {"event_type": "WORK_REFINED", "writer_role": "DIRECTOR", "material": True}),
                ("20260915T120100000000Z-auto0001.json", {"event_type": "WORK_DONE", "writer_role": "EXECUTOR", "material": True}),
                ("20260915T120200000000Z-dupe0001.json", {"event_type": "DUPLICATE_EXECUTION_PREVENTED", "writer_role": "EXECUTOR", "material": False}),
            )
            for filename, payload in events:
                (root / f"events/2026-09-15/{filename}").write_text(json.dumps(payload), encoding="utf-8")

            enrich_materialized_state(root)

            roi = json.loads((root / "snapshot/ai-roi.json").read_text(encoding="utf-8"))
            self.assertEqual(roi["delivery"]["terminal_work"], 2)
            self.assertEqual(roi["delivery"]["verified_work"], 1)
            self.assertEqual(roi["autonomy"]["human_intervention_events"], 1)
            self.assertEqual(roi["autonomy"]["autonomous_material_events"], 1)
            self.assertEqual(roi["autonomy"]["autonomous_material_rate"], 0.5)
            self.assertEqual(roi["quality"]["duplicate_execution_prevented_events"], 1)


if __name__ == "__main__":
    unittest.main()
