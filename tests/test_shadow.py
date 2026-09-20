import copy
import json
import unittest
from pathlib import Path

from nexo_control_plane.shadow import build_shadow_plan


class ShadowPlannerTests(unittest.TestCase):
    def setUp(self):
        path = Path(__file__).parent / "fixtures" / "shadow_snapshot.json"
        self.snapshot = json.loads(path.read_text())

    def test_shadow_plan_classifies_without_mutating_input(self):
        before = copy.deepcopy(self.snapshot)
        plan = build_shadow_plan(self.snapshot)
        self.assertEqual(self.snapshot, before)
        self.assertIn("ENG-BLOCKER", {x["work_id"] for x in plan["dispatch"]})
        self.assertIn("SCI-WAIT", {x["work_id"] for x in plan["waits"]})
        self.assertIn("SCI-CONFLICT", {x["work_id"] for x in plan["conflicts"]})
        self.assertNotIn("SCI-SPEC", {x["work_id"] for x in plan["dispatch"]})
        self.assertIn("VERIFICATION_BACKPRESSURE", plan["pressure"])

    def test_unknown_domain_fails_closed(self):
        bad = copy.deepcopy(self.snapshot)
        bad["works"][0]["domain"] = "MAGIC"
        with self.assertRaises(ValueError):
            build_shadow_plan(bad)

    def test_unknown_status_fails_closed(self):
        bad = copy.deepcopy(self.snapshot)
        bad["works"][0]["status"] = "YOLO"
        with self.assertRaises(ValueError):
            build_shadow_plan(bad)


if __name__ == "__main__":
    unittest.main()
