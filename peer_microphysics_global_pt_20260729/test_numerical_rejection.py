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


class RecoverableFailureModel:
    def logposterior(self, *args, **kwargs):
        raise CAMBError("HMCode INTEGRATE, Integration timed out")


class ProgrammingFailureModel:
    def logposterior(self, *args, **kwargs):
        raise KeyError("broken parameter mapping")


def test_camb_numerical_failure_rejects_proposal_and_records_diagnostic(tmp_path: Path):
    names = list(pt_driver.BOUNDS)
    position = np.full(len(names), 0.5, dtype=float)
    log_path = tmp_path / "invalid_theory_evaluations.jsonl"

    logprior, loglike, derived = pt_driver._evaluate_model(
        RecoverableFailureModel(),
        names,
        position,
        invalid_log_path=log_path,
        context={"rank": 5, "step": 123, "ladder_id": 0},
    )

    assert logprior == -math.inf
    assert loglike == -math.inf
    assert derived == {}
    records = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
    assert len(records) == 1
    assert records[0]["exception_type"] == "camb.baseconfig.CAMBError"
    assert records[0]["rank"] == 5
    assert records[0]["step"] == 123
    assert records[0]["parameters"]


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
