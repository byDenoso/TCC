from __future__ import annotations

import hashlib
import json
import math
import os
import random
from pathlib import Path
from typing import Any


def _matvec(matrix: list[list[float]], vector: list[float]) -> list[float]:
    if any(len(row) != len(vector) for row in matrix):
        raise ValueError("matrix/vector shape mismatch")
    return [sum(float(a) * float(b) for a, b in zip(row, vector)) for row in matrix]


def _solve(matrix: list[list[float]], vector: list[float]) -> list[float]:
    n = len(vector)
    if len(matrix) != n or any(len(row) != n for row in matrix):
        raise ValueError("linear system must be square")
    augmented = [[float(value) for value in row] + [float(vector[i])] for i, row in enumerate(matrix)]
    for col in range(n):
        pivot = max(range(col, n), key=lambda row: abs(augmented[row][col]))
        if abs(augmented[pivot][col]) < 1e-14:
            raise ValueError("singular matrix")
        augmented[col], augmented[pivot] = augmented[pivot], augmented[col]
        scale = augmented[col][col]
        augmented[col] = [value / scale for value in augmented[col]]
        for row in range(n):
            if row == col:
                continue
            factor = augmented[row][col]
            augmented[row] = [a - factor * b for a, b in zip(augmented[row], augmented[col])]
    return [row[-1] for row in augmented]


def _quadratic(vector: list[float], precision: list[list[float]]) -> float:
    projected = _matvec(precision, vector)
    return sum(float(a) * float(b) for a, b in zip(vector, projected))


def _gls(observed: list[float], design: list[list[float]], precision: list[list[float]]) -> dict[str, Any]:
    if not observed or len(design) != len(observed) or any(not row for row in design):
        raise ValueError("invalid GLS shapes")
    columns = len(design[0])
    if any(len(row) != columns for row in design):
        raise ValueError("ragged design matrix")
    weighted_y = _matvec(precision, observed)
    normal = [[sum(design[k][i] * sum(precision[k][m] * design[m][j] for m in range(len(observed))) for k in range(len(observed))) for j in range(columns)] for i in range(columns)]
    rhs = [sum(design[k][i] * weighted_y[k] for k in range(len(observed))) for i in range(columns)]
    coefficients = _solve(normal, rhs)
    residual = [observed[i] - sum(design[i][j] * coefficients[j] for j in range(columns)) for i in range(len(observed))]
    return {"coefficients": coefficients, "chi2": _quadratic(residual, precision), "dof": len(observed) - columns}


def _statistics(binding: dict[str, Any]) -> dict[str, Any]:
    operation = binding["operation"]
    if operation == "quadratic_form":
        return {"chi2": _quadratic(binding["residual"], binding["precision"]), "dof": len(binding["residual"])}
    if operation == "fixed_trajectory_chi_square":
        observed = binding["observed"]
        return {"chi2": {name: _quadratic([a - b for a, b in zip(observed, trajectory)], binding["precision"]) for name, trajectory in binding["trajectories"].items()}}
    if operation == "gls":
        return _gls(binding["observed"], binding["design"], binding["precision"])
    if operation == "quadrature_1d":
        x, y = binding["x"], binding["y"]
        if len(x) != len(y) or len(x) < 2:
            raise ValueError("quadrature requires paired x/y samples")
        return {"integral": sum((float(x[i + 1]) - float(x[i])) * (float(y[i + 1]) + float(y[i])) / 2 for i in range(len(x) - 1))}
    if operation == "jackknife_mean":
        values = [float(value) for value in binding["values"]]
        if len(values) < 2:
            raise ValueError("jackknife requires at least two values")
        leave_one_out = [(sum(values) - value) / (len(values) - 1) for value in values]
        center = sum(leave_one_out) / len(leave_one_out)
        variance = (len(values) - 1) / len(values) * sum((value - center) ** 2 for value in leave_one_out)
        return {"estimate": sum(values) / len(values), "standard_error": math.sqrt(variance), "replicates": len(values)}
    if operation == "bootstrap_mean":
        values = [float(value) for value in binding["values"]]
        resamples = int(binding.get("resamples", 1000))
        if not values or not 1 <= resamples <= 1_000_000:
            raise ValueError("invalid bootstrap binding")
        rng = random.Random(int(binding.get("seed", 0)))
        means = [sum(rng.choice(values) for _ in values) / len(values) for _ in range(resamples)]
        center = sum(means) / resamples
        variance = sum((value - center) ** 2 for value in means) / max(1, resamples - 1)
        return {"estimate": sum(values) / len(values), "bootstrap_mean": center, "standard_error": math.sqrt(variance), "resamples": resamples, "seed": int(binding.get("seed", 0))}
    raise ValueError(f"unsupported generic operation: {operation}")


def _blocked(frozen: dict[str, Any], reason_code: str, reason: str) -> dict[str, Any]:
    return {
        "status": "BLOCKED",
        "reason_code": reason_code,
        "reason": reason,
        "test_id": frozen.get("id"),
        "claim_boundary": frozen.get("claim_boundary"),
        "scientific_claim_promoted": False,
    }


def evaluate_contract(frozen: dict[str, Any], binding: dict[str, Any]) -> dict[str, Any]:
    required = (frozen.get("id"), frozen.get("method"), frozen.get("decision_rule"), frozen.get("outputs"), frozen.get("claim_boundary"))
    if not all(required):
        return _blocked(frozen, "SCIENTIFIC_DEFINITION_MISSING", "frozen scientific contract is incomplete")
    if not binding.get("operation") or not binding.get("input_refs"):
        return _blocked(frozen, "SCIENTIFIC_DEFINITION_MISSING", "exact numeric inputs, covariance/precision, and provenance bindings are required")
    decision = str(binding.get("decision") or "")
    if decision not in frozen["decision_rule"]:
        return _blocked(frozen, "FROZEN_CONTRACT_CONFLICT", "decision must be one of the frozen decision-rule keys")
    try:
        statistics = _statistics(binding)
    except (KeyError, TypeError, ValueError, ZeroDivisionError) as exc:
        return _blocked(frozen, "SCIENTIFIC_DEFINITION_MISSING", f"invalid numeric binding: {exc}")
    digest = hashlib.sha256(json.dumps(frozen, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return {
        "status": "DONE",
        "test_id": frozen["id"],
        "operation": binding["operation"],
        "statistics": statistics,
        "decision": decision,
        "decision_rule": frozen["decision_rule"][decision],
        "claim_boundary": frozen["claim_boundary"],
        "evidence_level": str(binding.get("evidence_level") or "NATIVE_NUMERIC"),
        "input_refs": binding["input_refs"],
        "frozen_contract_sha256": digest,
        "scientific_claim_promoted": False,
    }


def main() -> None:
    output_path = Path(os.getenv("NEXO_PARAM_OUTPUT_PATH", "scientific_result.json"))
    try:
        frozen = json.loads(os.environ["NEXO_PARAM_FROZEN_CONTRACT"])
        binding = json.loads(os.getenv("NEXO_PARAM_EXECUTION_BINDING", "{}"))
        result = evaluate_contract(frozen, binding)
    except (KeyError, json.JSONDecodeError) as exc:
        result = _blocked({}, "SCIENTIFIC_DEFINITION_MISSING", f"missing or invalid contract binding: {exc}")
    output_path.write_text(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
