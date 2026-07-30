from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pytest

import pt_driver


class CAMBError(RuntimeError):
    pass


CAMBError.__module__ = "camb.baseconfig"


class LoggedError(RuntimeError):
    pass


LoggedError.__module__ = "cobaya.log"


class RecoverableFailureModel:
    def logposterior(self, *args, **kwargs):
        raise CAMBError("HMCode INTEGRATE, Integration timed out")


class ThetaH0FailureModel:
    def logposterior(self, *args, **kwargs):
        raise LoggedError("No solution for H0 inside of theta_H0_range")


class ScalarTimeMismatchModel:
    def logposterior(self, *args, **kwargs):
        raise LoggedError("mismatch in integrated times (CAMB: CalcScalarSources)")


class ProgrammingFailureModel:
    def logposterior(self, *args, **kwargs):
        raise KeyError("broken parameter mapping")


def _evaluate_failure(model, tmp_path: Path, filename: str):
    names = list(pt_driver.BOUNDS)
    position = np.full(len(names), 0.5, dtype=float)
    log_path = tmp_path / filename
    result = pt_driver._evaluate_model(
        model,
        names,
        position,
        invalid_log_path=log_path,
        context={"rank": 5, "step": 123, "ladder_id": 0},
    )
    records = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
    return result, records


def test_camb_numerical_failure_rejects_proposal_and_records_diagnostic(tmp_path: Path):
    (logprior, loglike, derived), records = _evaluate_failure(
        RecoverableFailureModel(), tmp_path, "camb_invalid.jsonl"
    )

    assert logprior == -math.inf
    assert loglike == -math.inf
    assert derived == {}
    assert len(records) == 1
    assert records[0]["exception_type"] == "camb.baseconfig.CAMBError"
    assert records[0]["rank"] == 5
    assert records[0]["step"] == 123
    assert records[0]["parameters"]


def test_theta_h0_mapping_failure_rejects_only_the_proposal(tmp_path: Path):
    (logprior, loglike, derived), records = _evaluate_failure(
        ThetaH0FailureModel(), tmp_path, "theta_h0_invalid.jsonl"
    )

    assert logprior == -math.inf
    assert loglike == -math.inf
    assert derived == {}
    assert records[0]["exception_type"] == "cobaya.log.LoggedError"
    assert "theta_H0_range" in records[0]["message"]


def test_scalar_source_time_mismatch_rejects_only_the_proposal(tmp_path: Path):
    (logprior, loglike, derived), records = _evaluate_failure(
        ScalarTimeMismatchModel(), tmp_path, "scalar_time_invalid.jsonl"
    )

    assert logprior == -math.inf
    assert loglike == -math.inf
    assert derived == {}
    assert records[0]["exception_type"] == "cobaya.log.LoggedError"
    assert "mismatch in integrated times" in records[0]["message"]


def test_unexpected_programming_error_is_not_silenced(tmp_path: Path):
    names = list(pt_driver.BOUNDS)
    position = np.full(len(names), 0.5, dtype=float)

    with pytest.raises(KeyError, match="broken parameter mapping"):
        pt_driver._evaluate_model(
            ProgrammingFailureModel(),
            names,
            position,
            invalid_log_path=tmp_path / "invalid.jsonl",
        )
