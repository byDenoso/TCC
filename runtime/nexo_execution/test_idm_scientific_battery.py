import subprocess
import sys
import unittest
from pathlib import Path

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
    def test_scientific_battery_task_is_allowlisted(self):
        contract = ExecutionContract.from_dict(dict(BASE))
        self.assertEqual(
            contract.argv,
            ["python3", "benchmarks/idm_scientific_battery.py"],
        )

    def test_battery_script_imports_when_executed_from_benchmarks_directory(self):
        benchmarks = Path(__file__).resolve().parents[2] / "benchmarks"
        completed = subprocess.run(
            [
                sys.executable,
                "-c",
                "import runpy; runpy.run_path('idm_scientific_battery.py', run_name='battery_import_test')",
            ],
            cwd=benchmarks,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout)

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
