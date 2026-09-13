#!/usr/bin/env python3
from __future__ import annotations

import os
import subprocess
import sys

NUMPY_VERSION = "1.26.4"
CYTHON_VERSION = "3.0.12"
SCIPY_VERSION = "1.13.1"


def bootstrap_runtime() -> None:
    subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--disable-pip-version-check",
            "--no-input",
            "--user",
            "--upgrade",
            "--force-reinstall",
            f"numpy=={NUMPY_VERSION}",
            f"cython=={CYTHON_VERSION}",
            f"scipy=={SCIPY_VERSION}",
        ],
        check=True,
    )
    os.environ["PIP_NO_BUILD_ISOLATION"] = "1"
    os.execv(
        sys.executable,
        [sys.executable, "-m", "benchmarks.idm_scientific_battery"],
    )


if __name__ == "__main__":
    bootstrap_runtime()
