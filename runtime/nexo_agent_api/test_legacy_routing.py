from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from .service import AgentService


class LegacyRoutingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "entities" / "work").mkdir(parents=True)
        (self.root / "indexes").mkdir(parents=True)
        (self.root / "snapshot").mkdir(parents=True)
        (self.root / "manifests").mkdir(parents=True)
        (self.root / "CONTROL.json").write_text(json.dumps({"mode": "ACTIVE"}), encoding="utf-8")
        (self.root / "snapshot" / "latest.json").write_text(json.dumps({}), encoding="utf-8")
        (self.root / "manifests" / "capabilities.json").write_text(json.dumps({"capabilities": {}}), encoding="utf-8")
        (self.root / "indexes" / "active-work.json").write_text(json.dumps({"work": [
            {"id": "R1", "entity_version": 1, "kind": "RESEARCH", "status": "READY", "priority": "HIGH"},
            {"id": "A1", "entity_version": 1, "kind": "ACTION", "status": "CANDIDATE", "priority": "HIGH"},
            {"id": "E1", "entity_version": 1, "kind": "EMERGENT_TEST", "status": "CANDIDATE"}
        ]}), encoding="utf-8")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_unowned_research_and_action_route_to_advisor(self) -> None:
        ids = {item["id"] for item in AgentService(self.root).queue_for("ADVISOR")}
        self.assertEqual(ids, {"R1", "A1"})

    def test_emergent_test_routes_to_emergent_not_advisor(self) -> None:
        advisor_ids = {item["id"] for item in AgentService(self.root).queue_for("ADVISOR")}
        emergent_ids = {item["id"] for item in AgentService(self.root).queue_for("EMERGENT")}
        self.assertNotIn("E1", advisor_ids)
        self.assertIn("E1", emergent_ids)


if __name__ == "__main__":
    unittest.main()
