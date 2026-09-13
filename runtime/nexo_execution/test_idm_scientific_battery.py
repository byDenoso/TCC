import unittest

from runtime.nexo_execution.core import ExecutionContract


BASE = {
    "schema": "nexo.execution.v1",
    "execution_id": "EXEC-IDM-BATTERY-TEST",
    "work_id": "WORK::SCI-UNIFIED-DARK-SECTOR-COUPLING-DISCRIMINANT-20260911",
    "test_id": "T-IDM-BATTERY",
    "provider": "github_actions",
    "repository": "byDenoso/TCC",
    "commit_sha": "abc123",
    "task_id": "idm_scientific_battery",
    "parameters": {"source_revision": "dc55e59dec8f5c647df6e9d764f5c6960796e1df"},
    "seed": 20260912,
    "timeout_minutes": 15,
    "required_outputs": ["idm_scientific_battery_result.json"],
}


class IDMBatteryContractTests(unittest.TestCase):
    def test_scientific_battery_task_uses_abi_bootstrap_entrypoint(self):
        contract = ExecutionContract.from_dict(dict(BASE))
        self.assertEqual(
            contract.argv,
            ["python3", "-m", "benchmarks.idm_scientific_battery_bootstrap"],
        )

    def test_battery_runtime_pins_numpy_cython_and_scipy(self):
        from benchmarks.idm_scientific_battery_bootstrap import (
            CYTHON_VERSION,
            NUMPY_VERSION,
            SCIPY_VERSION,
        )

        self.assertEqual(NUMPY_VERSION, "1.26.4")
        self.assertEqual(CYTHON_VERSION, "3.0.12")
        self.assertEqual(SCIPY_VERSION, "1.13.1")

    def test_battery_defines_exactly_15_unique_cases(self):
        from benchmarks.idm_scientific_battery import build_cases

        cases = build_cases()
        self.assertEqual(len(cases), 15)
        self.assertEqual(len({case["id"] for case in cases}), 15)

    def test_battery_contains_null_and_rival_controls(self):
        from benchmarks.idm_scientific_battery import build_cases

        cases = {case["id"]: case for case in build_cases()}
        self.assertIn("T01_LCDM", cases)
        self.assertIn("T02_SCF_UNCOUPLED", cases)
        self.assertIn("T03_IDM_C0", cases)

    def test_battery_scans_both_coupling_signs(self):
        from benchmarks.idm_scientific_battery import build_cases

        couplings = [
            case["cdm_c"]
            for case in build_cases()
            if case.get("kind") == "idm_coupling"
        ]
        self.assertTrue(any(value < 0 for value in couplings))
        self.assertTrue(any(value > 0 for value in couplings))
        self.assertIn(0.0, couplings)


if __name__ == "__main__":
    unittest.main()
