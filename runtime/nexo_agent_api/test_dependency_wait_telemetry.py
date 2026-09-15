from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from .telemetry import enrich_materialized_state


class DependencyWaitTelemetryTests(unittest.TestCase):
    def test_derives_human_retryable_and_unclassified_wait_lanes_from_canonical_fields(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            for rel in ("entities/work", "snapshot"):
                (root / rel).mkdir(parents=True)
            (root / "snapshot/latest.json").write_text(json.dumps({"counts": {}}), encoding="utf-8")
            (root / "snapshot/ai-roi.json").write_text(json.dumps({"roi": {}}), encoding="utf-8")

            work = [
                {
                    "id": "AUTH",
                    "status": "WAIT_DEPENDENCY",
                    "dependency_class": "HUMAN_AUTH_REQUIRED",
                    "human_action_required": True,
                    "auto_retry_eligible": False,
                },
                {
                    "id": "RETRY",
                    "status": "WAIT_DEPENDENCY",
                    "dependency_class": "EXTERNAL_TRANSIENT",
                    "human_action_required": False,
                    "auto_retry_eligible": True,
                },
                {
                    "id": "MIXED",
                    "status": "WAIT_DEPENDENCY",
                    "dependency_class": "MIXED",
                    "dependency_classes": ["EXTERNAL_TRANSIENT", "HUMAN_AUTH_REQUIRED"],
                    "human_action_required": True,
                    "auto_retry_eligible": True,
                },
                {"id": "OLD", "status": "WAIT_DEPENDENCY"},
                {"id": "READY", "status": "READY", "human_action_required": True, "auto_retry_eligible": True},
            ]
            for item in work:
                (root / "entities/work" / f"{item['id']}.json").write_text(json.dumps(item), encoding="utf-8")

            result = enrich_materialized_state(root)
            roi = json.loads((root / "snapshot/ai-roi.json").read_text(encoding="utf-8"))

            expected = {
                "total": 4,
                "human_attention": 2,
                "retryable": 2,
                "unclassified": 1,
                "by_class": {
                    "EXTERNAL_TRANSIENT": 1,
                    "HUMAN_AUTH_REQUIRED": 1,
                    "MIXED": 1,
                    "UNCLASSIFIED": 1,
                },
                "source": "entities/work/*.json explicit dependency classification fields only",
            }
            self.assertEqual(roi["autonomy"]["dependency_wait"], expected)
            self.assertEqual(result["dependency_wait"], expected)


if __name__ == "__main__":
    unittest.main()
