from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from .materialize import materialize_view

class MaterializeTests(unittest.TestCase):
    def snapshot(self):
        return {"schema_version":"1.0","ssot_revision":1,"state_hash":"sha256:test","generated_at":"2026-09-14T00:00:00Z","projects":[{"id":"P1","title":"Project"}],"work":[{"id":"W1"}],"tests":[{"id":"T1"}],"events":[{"id":"E1"}],"knowledge":[{"id":"K1"}],"relations":[{"id":"R1"}],"decisions":[{"id":"D1"}],"olympus_summary":[{"id":"O1","label":"Client"}],"system":{}}

    def test_materializes_static_api_and_graphs(self):
        with tempfile.TemporaryDirectory() as tmp:
            result=materialize_view(self.snapshot(),tmp)
            root=Path(tmp)/"api"/"v1"
            self.assertEqual(result["graph_count"],3)
            self.assertTrue((root/"snapshot.json").exists())
            self.assertTrue((root/"graphs"/"science.json").exists())
            health=json.loads((root/"health.json").read_text())
            self.assertEqual(health["state_hash"],"sha256:test")

if __name__ == "__main__":
    unittest.main()
