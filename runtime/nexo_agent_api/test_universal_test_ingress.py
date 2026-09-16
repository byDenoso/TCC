from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

from .mutations import apply_mutation_request


class UniversalTestIngressContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "indexes").mkdir(parents=True)
        (self.root / "snapshot").mkdir(parents=True)
        (self.root / "manifests").mkdir(parents=True)
        (self.root / "CONTROL.json").write_text(json.dumps({"mode": "ACTIVE"}), encoding="utf-8")
        (self.root / "snapshot" / "latest.json").write_text(json.dumps({}), encoding="utf-8")
        (self.root / "manifests" / "capabilities.json").write_text(json.dumps({"capabilities": {}}), encoding="utf-8")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _create(self, kind: str, entity_id: str, changes: dict) -> dict:
        return apply_mutation_request(self.root, {
            "request_id": f"REQ-{kind.upper()}-CREATE",
            "entity_kind": kind,
            "entity_name": entity_id,
            "expected_version": 0,
            "changes": {"id": entity_id, **changes},
            "writer_role": "ADVISOR",
            "event_type": f"{kind.upper()}_CREATED",
        })

    def test_campaign_is_first_class_creatable_entity(self) -> None:
        campaign_id = "CAMPAIGN::COSMOLOGY::PEER-2026"
        receipt = self._create("campaign", campaign_id, {
            "domain": "COSMOLOGY",
            "project_id": "PROJECT::PEER",
            "label": "PEER 2026",
            "status": "ACTIVE",
        })
        self.assertTrue(receipt["accepted"])
        self.assertEqual(receipt["readback"], "PASS")
        entity = json.loads((self.root / "entities" / "campaign" / f"{campaign_id}.json").read_text())
        self.assertEqual(entity["domain"], "COSMOLOGY")
        self.assertEqual(entity["project_id"], "PROJECT::PEER")

    def test_run_is_first_class_creatable_entity(self) -> None:
        run_id = "RUN::TEST-D04::0002"
        receipt = self._create("run", run_id, {
            "domain": "COSMOLOGY",
            "parent_id": "TEST::D04",
            "operational_status": "QUEUED",
            "analytical_status": "UNASSESSED",
            "status": "QUEUED",
        })
        self.assertTrue(receipt["accepted"])
        self.assertEqual(receipt["readback"], "PASS")
        entity = json.loads((self.root / "entities" / "run" / f"{run_id}.json").read_text())
        self.assertEqual(entity["parent_id"], "TEST::D04")
        self.assertEqual(entity["analytical_status"], "UNASSESSED")

    def test_universal_test_registry_module_exists(self) -> None:
        spec = importlib.util.find_spec("runtime.nexo_agent_api.test_registry")
        self.assertIsNotNone(spec, "universal test registry module must exist before dispatch can be canonical")


if __name__ == "__main__":
    unittest.main()
