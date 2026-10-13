"""Regression coverage for frozen Round12 TEST fields stored in nested records.

The view never supplies missing provenance, runner inputs, recipe binding or a
preregistration receipt. It only avoids misreporting archived definitions as
absent when a matching canonical contract is present.
"""
import json
import tempfile
import unittest
from pathlib import Path

from runtime.nexo_agent_api.scientific_integrity import (
    _readiness_contract_view,
    readiness,
)


class Round12FrozenReadinessTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "contracts").mkdir()
        self.test = {
            "id": "T-MEGA26-LCDM-BIAS-HOD-152",
            "kind": "TEST",
            "status": "BLOCKED_INPUT",
            "contract_lock": True,
            "contract_ref": "TOWER_V06/contracts/MEGASTRUCTURE_LCDM_ROUND12_V1.json",
            "frozen_test": {
                "id": "T-MEGA26-LCDM-BIAS-HOD-152",
                "null": "Dependent at fixed field and volume",
                "rival": "Stable at fixed field and volume",
                "method": "Compare exact locked HOD selections on the same fields",
                "datasets": ["frozen simulation fields"],
                "selection": "frozen halo and HOD selections, fixed volume",
                "cuts": "unchanged Round12 search",
                "success_criteria": ["measured under matched volume"],
                "kill_criteria": ["exact selected inputs unavailable"],
                "claim_boundary": "No anomaly inference",
            },
        }
        self.contract = {
            "id": "MEGASTRUCTURE_LCDM_ROUND12_V1",
            "status": "FROZEN_PREREGISTERED",
            "question": "How do large structures depend on survey and tracer?",
            "tests": [{"id": self.test["id"], "objective": "Repeat the frozen finder across exact HOD selections"}],
        }
        self._contract()

    def _contract(self):
        (self.root / "contracts" / "MEGASTRUCTURE_LCDM_ROUND12_V1.json").write_text(
            json.dumps(self.contract), encoding="utf-8"
        )

    def test_nested_frozen_fields_are_read_only_aliases(self):
        original = json.dumps(self.test, sort_keys=True)
        view = _readiness_contract_view(self.test, self.root)
        self.assertEqual(view["null"], self.test["frozen_test"]["null"])
        self.assertEqual(view["rival"], self.test["frozen_test"]["rival"])
        self.assertEqual(view["method"]["declared_method"], self.test["frozen_test"]["method"])
        self.assertEqual(view["dataset_and_selection"]["selection"], self.test["frozen_test"]["selection"])
        self.assertEqual(view["question"]["specific_objective"], self.contract["tests"][0]["objective"])
        self.assertEqual(view["success_criteria"], self.test["frozen_test"]["success_criteria"])
        self.assertEqual(json.dumps(self.test, sort_keys=True), original)

    def test_no_promotion_without_freeze_inputs_and_recipe(self):
        result = readiness(self.root, self.test)
        self.assertFalse(result["eligible"])
        self.assertIn("FROZEN_DESIGN_UNVERIFIED", result["reasons"])
        self.assertIn("INPUT_PROVENANCE_INCOMPLETE", result["reasons"])
        self.assertIn("RECIPE_BINDING_MISSING", result["reasons"])
        self.assertNotIn("MISSING_NULL", result["reasons"])
        self.assertNotIn("MISSING_METHOD", result["reasons"])
        self.assertNotIn("MISSING_DATASET_AND_SELECTION", result["reasons"])
        self.assertNotIn("MISSING_SUCCESS_CRITERIA", result["reasons"])

    def test_unmatched_contract_cannot_supply_aliases(self):
        self.contract["tests"] = [{"id": "ANOTHER-TEST", "objective": "unrelated"}]
        self._contract()
        view = _readiness_contract_view(self.test, self.root)
        self.assertNotIn("null", view)
        self.assertNotIn("question", view)

    def test_unlocked_or_mismatched_frozen_id_is_ignored(self):
        for replacement in ({"contract_lock": False},
                            {"frozen_test": {**self.test["frozen_test"], "id": "ANOTHER-TEST"}},
                            {"contract_ref": "TOWER_V06/contracts/../private.json"}):
            view = _readiness_contract_view({**self.test, **replacement}, self.root)
            self.assertNotIn("null", view)
            self.assertNotIn("question", view)

    def test_other_round12_members_use_the_same_frozen_contract(self):
        for test_id in ("T-MEGA26-LCDM-EVT-LMAX-149",
                        "T-MEGA26-LCDM-TRACER-DENSITY-151"):
            with self.subTest(test_id=test_id):
                child = {
                    **self.test,
                    "id": test_id,
                    "frozen_test": {**self.test["frozen_test"], "id": test_id},
                }
                self.contract["tests"] = [
                    {"id": test_id, "objective": "Run exact locked Round12 selection"}
                ]
                self._contract()
                view = _readiness_contract_view(child, self.root)
                self.assertEqual(view["method"]["declared_method"], child["frozen_test"]["method"])
                self.assertEqual(view["null"], child["frozen_test"]["null"])
                result = readiness(self.root, child)
                self.assertFalse(result["eligible"])
                self.assertIn("RECIPE_BINDING_MISSING", result["reasons"])
                self.assertIn("INPUT_PROVENANCE_INCOMPLETE", result["reasons"])

    def test_top_level_definition_is_not_replaced(self):
        view = _readiness_contract_view({**self.test, "null": "top-level frozen null"}, self.root)
        self.assertEqual(view["null"], "top-level frozen null")


if __name__ == "__main__":
    unittest.main()
