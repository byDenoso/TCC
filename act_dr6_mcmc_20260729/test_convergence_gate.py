from __future__ import annotations

import json
import math
from pathlib import Path

from act_dr6_mcmc_20260729 import convergence_gate as gate


def test_checkpoint_infinity_is_json_safe_and_never_converged(tmp_path: Path) -> None:
    root = tmp_path
    (root / "mcmc").mkdir()
    (root / "mcmc" / "chain.checkpoint").write_text(
        "sampler:\n  mcmc:\n    converged: false\n    Rminus1_last: .inf\n",
        encoding="utf-8",
    )

    result = gate.diagnose(root)

    assert result["converged"] is False
    assert result["cobaya"]["Rminus1_last"] is None
    json.dumps(result, allow_nan=False)


def test_nonfinite_nested_diagnostic_is_sanitized_not_promoted() -> None:
    raw = {
        "converged": False,
        "rank_rhat": {"x": math.inf, "y": math.nan},
        "ok": 1.2,
    }

    safe = gate._json_safe(raw)

    assert safe == {
        "converged": False,
        "rank_rhat": {"x": None, "y": None},
        "ok": 1.2,
    }
    json.dumps(safe, allow_nan=False)
