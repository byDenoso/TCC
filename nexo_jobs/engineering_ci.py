from __future__ import annotations

import io
import unittest
from typing import Any


def _run_control_plane_suite() -> dict[str, Any]:
    suite = unittest.defaultTestLoader.discover("tests")
    stream = io.StringIO()
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    return {
        "verification": "PASS" if result.wasSuccessful() else "FAIL",
        "tests_run": result.testsRun,
        "failures": len(result.failures),
        "errors": len(result.errors),
        "skipped": len(result.skipped),
        "output_tail": stream.getvalue()[-8000:],
    }


_ALLOWED_SUITES = {
    "control_plane": _run_control_plane_suite,
}


def execute(args: dict[str, Any]) -> dict[str, Any]:
    allowed = {"suite"}
    unknown = set(args) - allowed
    if unknown:
        raise ValueError(f"unsupported engineering_ci args: {sorted(unknown)}")

    suite_name = args.get("suite")
    if not isinstance(suite_name, str) or suite_name not in _ALLOWED_SUITES:
        raise ValueError("engineering_ci suite is not allow-listed")

    result = _ALLOWED_SUITES[suite_name]()
    return {"suite": suite_name, **result}
