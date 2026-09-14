from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from .views import materialize_role_views


class StateMaterializationTests(unittest.TestCase):
    def test_reconciles_hot_index_and_snapshot_from_entities(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            for rel in ("indexes", "entities/work", "snapshot", "manifests"):
                (root / rel).mkdir(parents=True)
            (root / "CONTROL.json").write_text(json.dumps({"mode": "ACTIVE", "schema_version": "0.6"}))
            (root / "snapshot/latest.json").write_text(json.dumps({"schema_version": "0.6", "counts": {"active_work": 999}}))
            (root / "manifests/capabilities.json").write_text(json.dumps({"capabilities": {}}))
            (root / "manifests/artifacts.json").write_text(json.dumps({"artifacts": {}}))
            (root / "indexes/active-work.json").write_text(json.dumps({
                "count": 3,
                "schema_version": "0.6",
                "source": "GITHUB_TOWER_HOT_SET",
                "policy": "hot",
                "work": [
                    {"id": "W1", "entity_version": 1, "status": "READY", "owner_role": "ADVISOR", "kind": "RESEARCH"},
                    {"id": "LEGACY", "entity_version": 1, "status": "READY", "kind": "RESEARCH"},
                    {"id": "W3", "entity_version": 2, "status": "READY", "kind": "RESEARCH"},
                ],
            }))
            (root / "entities/work/W1.json").write_text(json.dumps({
                "id": "W1", "entity_version": 2, "status": "RUNNING", "owner_role": "ADVISOR", "kind": "RESEARCH"
            }))
            (root / "entities/work/W2.json").write_text(json.dumps({
                "id": "W2", "entity_version": 1, "status": "READY", "owner_role": "ADVISOR", "kind": "RESEARCH"
            }))
            (root / "entities/work/W3.json").write_text(json.dumps({
                "id": "W3", "entity_version": 3, "status": "DONE", "owner_role": "ADVISOR", "kind": "RESEARCH"
            }))

            materialize_role_views(root)

            active = json.loads((root / "indexes/active-work.json").read_text())
            snapshot = json.loads((root / "snapshot/latest.json").read_text())
            by_id = {item["id"]: item for item in active["work"]}

            self.assertEqual(active["count"], 3)
            self.assertEqual(set(by_id), {"W1", "W2", "LEGACY"})
            self.assertEqual((by_id["W1"]["entity_version"], by_id["W1"]["status"]), (2, "RUNNING"))
            self.assertEqual(snapshot["counts"]["active_work"], 3)


if __name__ == "__main__":
    unittest.main()
