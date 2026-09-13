import json
from pathlib import Path

from act_dr6_mcmc_20260729.convergence_gate import diagnose


def _write_constant_chain(path: Path, value: float) -> None:
    rows = ["# weight minuslogpost H0"]
    rows.extend(f"1 0 {value}" for _ in range(40))
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def test_nonfinite_rhat_is_json_safe_and_fails_closed(tmp_path: Path) -> None:
    mcmc = tmp_path / "mcmc"
    mcmc.mkdir()
    for index in range(1, 5):
        _write_constant_chain(mcmc / f"chain.{index}.txt", 70.0)

    (mcmc / "chain.checkpoint").write_text(
        "sampler:\n  mcmc:\n    converged: true\n    Rminus1_last: 0.001\n",
        encoding="utf-8",
    )

    result = diagnose(tmp_path, params=["H0"], max_draws_per_chain=1000)

    assert result["converged"] is False
    payload = json.dumps(result, allow_nan=False)
    decoded = json.loads(payload)
    assert decoded["rank_rhat"]["H0"] is None
    assert decoded["rank_rhat_minus1"]["H0"] is None
    assert decoded["rhat_minus1_max"] is None
