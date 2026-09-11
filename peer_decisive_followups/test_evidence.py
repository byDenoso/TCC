import math
from pathlib import Path

import pytest

from peer_decisive_followups.evidence import (
    EvidenceError,
    compare_models,
    normalize_evidence,
    parse_polychord_stats,
    production_converged,
)


def test_normalization_propagates_independent_uncertainty_in_quadrature():
    result = normalize_evidence(10.0, 0.3, 2.0, 0.4)
    assert result["logZ"] == pytest.approx(8.0)
    assert result["logZstd"] == pytest.approx(0.5)


def test_model_comparison_is_m3_minus_m1_with_quadrature_uncertainty():
    result = compare_models(
        {"status": "COMPLETE", "logZ": 3.0, "logZstd": 0.5, "converged": True},
        {"status": "COMPLETE", "logZ": 1.0, "logZstd": 0.4, "converged": True},
    )
    assert result["delta_logZ_M3_minus_M1"] == pytest.approx(2.0)
    assert result["delta_logZ_std"] == pytest.approx(math.sqrt(0.41))
    assert result["status"] == "COMPLETE"


def test_model_comparison_rejects_unconverged_input():
    with pytest.raises(EvidenceError, match="converged"):
        compare_models(
            {"status": "COMPLETE", "logZ": 3.0, "logZstd": 0.5, "converged": False},
            {"status": "COMPLETE", "logZ": 1.0, "logZstd": 0.4, "converged": True},
        )


def test_nonfinite_evidence_is_rejected():
    with pytest.raises(EvidenceError, match="finite"):
        normalize_evidence(float("nan"), 0.1, 0.0, 0.1)


def test_parse_polychord_stats_reads_logz_and_dead_count(tmp_path: Path):
    path = tmp_path / "chain.stats"
    path.write_text(
        "header\nlog(Z) = 12.345 +/- 0.067\n ndead:       12345\n nlive:         400\n",
        encoding="utf-8",
    )
    parsed = parse_polychord_stats(path)
    assert parsed["logZ"] == pytest.approx(12.345)
    assert parsed["logZstd"] == pytest.approx(0.067)
    assert parsed["ndead"] == 12345
    assert parsed["nlive"] == 400


def test_production_convergence_rejects_max_ndead_cap():
    assert production_converged({"ndead": 49999}, max_ndead=50000, precision_criterion=0.001,
                                publication_dlogz_gate=0.1) is True
    assert production_converged({"ndead": 50000}, max_ndead=50000, precision_criterion=0.001,
                                publication_dlogz_gate=0.1) is False


def test_production_convergence_fails_closed_without_ndead():
    assert production_converged({}, max_ndead=50000, precision_criterion=0.001,
                                publication_dlogz_gate=0.1) is False
