from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any, Mapping

REGISTRY_PATH = Path(__file__).with_name("peer_detection_gates.json")


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def load_gate_registry(path: str | Path | None = None) -> dict[str, Any]:
    target = Path(path) if path is not None else REGISTRY_PATH
    data = json.loads(target.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("battery_id") != "PEER_DETECTION_V1":
        raise ValueError("invalid PEER detection registry")
    gates = data.get("gates")
    if not isinstance(gates, dict) or sorted(gates) != [f"D{i:02d}" for i in range(26)]:
        raise ValueError("registry must contain exactly D00-D25")
    order = data.get("execution_order")
    if not isinstance(order, list) or sorted(order) != sorted(gates) or len(order) != len(gates):
        raise ValueError("execution_order must contain each gate exactly once")
    return data


_REGISTRY = load_gate_registry()
EXECUTION_ORDER: list[str] = list(_REGISTRY["execution_order"])


def policy_digest() -> str:
    return _digest({
        "battery_id": _REGISTRY["battery_id"],
        "policy": _REGISTRY["policy"],
        "execution_order": _REGISTRY["execution_order"],
        "stop_rules": _REGISTRY.get("stop_rules", []),
        "gates": _REGISTRY["gates"],
    })


def _as_float(value: Any, name: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{name} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{name} must be finite")
    return result


def _as_float_list(value: Any, name: str) -> list[float]:
    if not isinstance(value, list) or not value:
        raise ValueError(f"{name} must be a non-empty list")
    return [_as_float(item, name) for item in value]


def _verification(decision: str, reason_code: str) -> dict[str, Any]:
    return {
        "status": "PASS",
        "decision": decision,
        "reason_code": reason_code,
        "scope": "SCIENTIFIC",
    }


def _result(
    gate_id: str,
    gate_status: str,
    *,
    metrics: Mapping[str, Any] | None = None,
    classification_hint: str | None = None,
    reason_codes: list[str] | None = None,
    evidence: Any = None,
) -> dict[str, Any]:
    conclusive = gate_status in {"PASS", "FAIL", "SKIPPED_BY_POLICY"}
    return {
        "schema": "peer.detection.gate-result.v1",
        "battery_id": "PEER_DETECTION_V1",
        "gate_id": gate_id,
        "gate_status": gate_status,
        "metrics": dict(metrics or {}),
        "classification_hint": classification_hint,
        "reason_codes": list(reason_codes or []),
        "input_digest": None if evidence is None else _digest(evidence),
        "policy_digest": policy_digest(),
        "nexo_verification": _verification(
            "VERIFIED" if conclusive else "INCONCLUSIVE",
            f"GATE_{gate_status}",
        ),
    }


def _inconclusive(gate_id: str, code: str, evidence: Any = None, detail: str | None = None) -> dict[str, Any]:
    metrics = {"detail": detail} if detail else {}
    return _result(gate_id, "INCONCLUSIVE", metrics=metrics, reason_codes=[code], evidence=evidence)


def _eval_delta_chi2(gate_id: str, evidence: Mapping[str, Any]) -> dict[str, Any]:
    chi2_null = _as_float(evidence["chi2_null"], "chi2_null")
    chi2_peer = _as_float(evidence["chi2_peer"], "chi2_peer")
    delta = chi2_null - chi2_peer
    passed = delta > 0
    return _result(
        gate_id,
        "PASS" if passed else "FAIL",
        metrics={"chi2_null": chi2_null, "chi2_peer": chi2_peer, "delta_chi2_null_minus_peer": delta},
        classification_hint=None if passed else "NO_DETECTION",
        reason_codes=["PEER_IMPROVES_SAME_STACK"] if passed else ["NO_SAME_STACK_IMPROVEMENT"],
        evidence=evidence,
    )


def _empirical_tail(observed: float, samples: list[float]) -> float:
    exceed = sum(value >= observed for value in samples)
    return (exceed + 1.0) / (len(samples) + 1.0)


def _eval_empirical_tail(gate_id: str, evidence: Mapping[str, Any], *, scan: bool = False) -> dict[str, Any]:
    observed_key = "q_observed" if "q_observed" in evidence else "q_local"
    sample_key = "q_null_scan_max" if scan and "q_null_scan_max" in evidence else "q_null_max"
    observed = _as_float(evidence[observed_key], observed_key)
    samples = _as_float_list(evidence[sample_key], sample_key)
    p_global = _empirical_tail(observed, samples)
    threshold = _as_float(_REGISTRY["policy"]["global_evidence_p"], "global_evidence_p")
    passes = p_global < threshold
    metrics = {
        "q_observed": observed,
        "null_replicates": len(samples),
        "p_global": p_global,
        "evidence_threshold": threshold,
        "passes_evidence_threshold": passes,
    }
    if scan:
        corrected = bool(evidence.get("look_elsewhere_corrected", True))
        metrics["look_elsewhere_corrected"] = corrected
        passes = passes and corrected
    return _result(
        gate_id,
        "PASS" if passes else "FAIL",
        metrics=metrics,
        classification_hint=None if passes else "NO_DETECTION",
        reason_codes=["GLOBAL_NULL_REJECTED"] if passes else ["GLOBAL_NULL_COMPATIBLE"],
        evidence=evidence,
    )


def _eval_profile(gate_id: str, evidence: Mapping[str, Any]) -> dict[str, Any]:
    raw = evidence.get("profile")
    if not isinstance(raw, list) or len(raw) < 3:
        raise ValueError("profile must contain at least three points")
    points = []
    for item in raw:
        if not isinstance(item, Mapping):
            raise ValueError("profile points must be objects")
        points.append((_as_float(item["f_peer"], "f_peer"), _as_float(item["chi2"], "chi2")))
    points.sort(key=lambda pair: pair[0])
    best_f, best_chi2 = min(points, key=lambda pair: pair[1])
    f0_point = min(points, key=lambda pair: abs(pair[0]))
    if abs(f0_point[0]) > 1e-10:
        raise ValueError("profile must include f_peer=0")
    delta_f0 = f0_point[1] - best_chi2
    interior = points[0][0] < best_f < points[-1][0]
    passes = interior and best_f > 0 and delta_f0 > 0
    return _result(
        gate_id,
        "PASS" if passes else "FAIL",
        metrics={"best_f_peer": best_f, "best_chi2": best_chi2, "chi2_f0": f0_point[1], "delta_chi2_f0": delta_f0, "interior_minimum": interior},
        classification_hint=None if passes else "NO_DETECTION",
        reason_codes=["INTERIOR_NONZERO_PROFILE_MINIMUM"] if passes else ["PROFILE_INCLUDES_F0_COMPATIBILITY"],
        evidence=evidence,
    )


def _eval_bayes(gate_id: str, evidence: Mapping[str, Any]) -> dict[str, Any]:
    if "delta_lnZ" in evidence:
        delta = _as_float(evidence["delta_lnZ"], "delta_lnZ")
    else:
        delta = _as_float(evidence["lnz_peer"], "lnz_peer") - _as_float(evidence["lnz_null"], "lnz_null")
    threshold = _as_float(_REGISTRY["policy"]["strong_delta_lnz"], "strong_delta_lnz")
    passes = delta >= threshold
    return _result(gate_id, "PASS" if passes else "FAIL", metrics={"delta_lnZ": delta, "threshold": threshold}, reason_codes=["BAYES_EVIDENCE_STABLE"] if passes else ["BAYES_EVIDENCE_NOT_STRONG"], evidence=evidence)


def _classifications(evidence: Mapping[str, Any], key: str = "runs") -> list[str]:
    raw = evidence.get(key)
    if not isinstance(raw, list) or not raw:
        raise ValueError(f"{key} must be a non-empty list")
    values = []
    for item in raw:
        if not isinstance(item, Mapping):
            raise ValueError(f"{key} items must be objects")
        classification = str(item.get("classification") or "").strip().upper()
        if not classification:
            raise ValueError("classification is required")
        values.append(classification)
    return values


def _eval_prior_sensitivity(gate_id: str, evidence: Mapping[str, Any]) -> dict[str, Any]:
    values = _classifications(evidence)
    stable = len(set(values)) == 1
    return _result(gate_id, "PASS" if stable else "FAIL", metrics={"runs": len(values), "classifications": values, "stable": stable}, classification_hint=values[0] if stable and values[0] in {"NO_DETECTION","ANCHOR_CONDITIONED_SIGNAL","MODEL_CLASS_DETECTION","PEER_SPECIFIC_DETECTION"} else None, reason_codes=["PRIOR_CLASSIFICATION_STABLE"] if stable else ["PRIOR_CLASSIFICATION_FLIPS"], evidence=evidence)


def _eval_injection(gate_id: str, evidence: Mapping[str, Any]) -> dict[str, Any]:
    p = _REGISTRY["policy"]
    metrics = {
        "bias_sigma_abs": abs(_as_float(evidence["bias_sigma"], "bias_sigma")),
        "coverage68": _as_float(evidence["coverage68"], "coverage68"),
        "coverage95": _as_float(evidence["coverage95"], "coverage95"),
        "fpr": _as_float(evidence["fpr"], "fpr"),
        "fnr": _as_float(evidence["fnr"], "fnr"),
    }
    passes = (
        metrics["bias_sigma_abs"] <= p["injection_max_bias_sigma"]
        and p["coverage68_min"] <= metrics["coverage68"] <= p["coverage68_max"]
        and p["coverage95_min"] <= metrics["coverage95"] <= p["coverage95_max"]
        and metrics["fpr"] <= p["injection_max_fpr"]
        and metrics["fnr"] <= p["injection_max_fnr"]
    )
    return _result(gate_id, "PASS" if passes else "FAIL", metrics=metrics, reason_codes=["INJECTION_RECOVERY_CALIBRATED"] if passes else ["INJECTION_RECOVERY_MIScalibrated".upper()], evidence=evidence)


def _eval_sbc(gate_id: str, evidence: Mapping[str, Any]) -> dict[str, Any]:
    p = _REGISTRY["policy"]
    metrics = {
        "rank_uniformity_p": _as_float(evidence["rank_uniformity_p"], "rank_uniformity_p"),
        "coverage68": _as_float(evidence["coverage68"], "coverage68"),
        "coverage95": _as_float(evidence["coverage95"], "coverage95"),
    }
    passes = (
        metrics["rank_uniformity_p"] >= p["sbc_rank_p_min"]
        and p["coverage68_min"] <= metrics["coverage68"] <= p["coverage68_max"]
        and p["coverage95_min"] <= metrics["coverage95"] <= p["coverage95_max"]
    )
    return _result(gate_id, "PASS" if passes else "FAIL", metrics=metrics, reason_codes=["SBC_CALIBRATED"] if passes else ["SBC_MIScalibrated".upper()], evidence=evidence)


def _eval_anchor_ablation(gate_id: str, evidence: Mapping[str, Any]) -> dict[str, Any]:
    without = evidence.get("without_anchor")
    with_anchor = evidence.get("with_anchor")
    if not isinstance(without, Mapping) or not isinstance(with_anchor, Mapping):
        raise ValueError("with_anchor and without_anchor are required")
    no_excluded = bool(without.get("f0_excluded"))
    no_f = _as_float(without.get("preferred_f", 0.0), "without_anchor.preferred_f")
    yes_excluded = bool(with_anchor.get("f0_excluded"))
    yes_f = _as_float(with_anchor.get("preferred_f", 0.0), "with_anchor.preferred_f")
    anchor_free_survives = no_excluded and no_f > 0
    if anchor_free_survives:
        return _result(gate_id, "PASS", metrics={"anchor_free_survives": True, "without_anchor_f": no_f, "with_anchor_f": yes_f}, reason_codes=["ANCHOR_FREE_SIGNAL_SURVIVES"], evidence=evidence)
    hint = "ANCHOR_CONDITIONED_SIGNAL" if yes_excluded and yes_f > 0 else "NO_DETECTION"
    code = "ANCHOR_FREE_SIGNAL_COLLAPSES" if hint == "ANCHOR_CONDITIONED_SIGNAL" else "NO_SIGNAL_WITH_OR_WITHOUT_ANCHOR"
    return _result(gate_id, "FAIL", metrics={"anchor_free_survives": False, "without_anchor_f": no_f, "with_anchor_f": yes_f}, classification_hint=hint, reason_codes=[code], evidence=evidence)


def _eval_anchor_swap(gate_id: str, evidence: Mapping[str, Any]) -> dict[str, Any]:
    fits = evidence.get("fits")
    if not isinstance(fits, Mapping) or "no_anchor" not in fits:
        raise ValueError("fits with no_anchor is required")
    supports = {}
    for name, value in fits.items():
        if not isinstance(value, Mapping):
            raise ValueError("anchor fit must be an object")
        supports[str(name)] = bool(value.get("f0_excluded")) and _as_float(value.get("preferred_f", 0), f"{name}.preferred_f") > 0
    no_anchor = supports.get("no_anchor", False)
    anchored = [value for key, value in supports.items() if key != "no_anchor"]
    passes = no_anchor and bool(anchored) and all(anchored)
    hint = None
    if not no_anchor and any(anchored):
        hint = "ANCHOR_CONDITIONED_SIGNAL"
    elif not any(supports.values()):
        hint = "NO_DETECTION"
    return _result(gate_id, "PASS" if passes else "FAIL", metrics={"support_by_anchor": supports}, classification_hint=hint, reason_codes=["ANCHOR_SWAP_CONSISTENT"] if passes else ["ANCHOR_SWAP_NOT_ROBUST"], evidence=evidence)


def _eval_split_consistency(gate_id: str, evidence: Mapping[str, Any]) -> dict[str, Any]:
    estimates = evidence.get("estimates")
    if not isinstance(estimates, list) or len(estimates) < 2:
        raise ValueError("estimates must contain at least two experiments")
    parsed = []
    for item in estimates:
        if not isinstance(item, Mapping):
            raise ValueError("estimate must be an object")
        parsed.append((str(item.get("name") or "unnamed"), _as_float(item["value"], "value"), _as_float(item["sigma"], "sigma")))
    max_z = 0.0
    pair = None
    for i, left in enumerate(parsed):
        for right in parsed[i + 1:]:
            denom = math.sqrt(left[2] ** 2 + right[2] ** 2)
            if denom <= 0:
                raise ValueError("sigma must be positive")
            z = abs(left[1] - right[1]) / denom
            if z > max_z:
                max_z, pair = z, [left[0], right[0]]
    threshold = _REGISTRY["policy"]["split_max_pairwise_z"]
    passes = max_z <= threshold
    return _result(gate_id, "PASS" if passes else "FAIL", metrics={"max_pairwise_z": max_z, "worst_pair": pair, "threshold": threshold}, reason_codes=["SPLITS_CONSISTENT"] if passes else ["SPLIT_TENSION_EXCEEDS_POLICY"], evidence=evidence)


def _eval_block_dominance(gate_id: str, evidence: Mapping[str, Any]) -> dict[str, Any]:
    raw = evidence.get("contributions")
    if isinstance(raw, Mapping):
        values = {str(k): abs(_as_float(v, str(k))) for k, v in raw.items()}
    elif isinstance(raw, list):
        values = {str(i): abs(_as_float(v, str(i))) for i, v in enumerate(raw)}
    else:
        raise ValueError("contributions must be object or list")
    total = sum(values.values())
    if total <= 0:
        raise ValueError("contributions must have non-zero total")
    fractions = {key: value / total for key, value in values.items()}
    max_fraction = max(fractions.values())
    creates = bool(evidence.get("single_block_creates_signal", False))
    threshold = _REGISTRY["policy"]["max_block_fraction"]
    passes = max_fraction <= threshold and not creates
    return _result(gate_id, "PASS" if passes else "FAIL", metrics={"fractions": fractions, "max_fraction": max_fraction, "threshold": threshold, "single_block_creates_signal": creates}, reason_codes=["NO_PATHOLOGICAL_BLOCK_DOMINANCE"] if passes else ["SINGLE_BLOCK_DOMINANCE"], evidence=evidence)


def _eval_leave_one_out(gate_id: str, evidence: Mapping[str, Any]) -> dict[str, Any]:
    runs = evidence.get("runs")
    if not isinstance(runs, list) or not runs:
        raise ValueError("runs must be non-empty")
    survives = []
    for item in runs:
        if not isinstance(item, Mapping):
            raise ValueError("run must be an object")
        survives.append(bool(item.get("signal_survives")))
    manufactured = bool(evidence.get("manufactured_by_single_tracer", False))
    passes = all(survives) and not manufactured
    return _result(gate_id, "PASS" if passes else "FAIL", metrics={"leave_one_out_runs": len(runs), "all_survive": all(survives), "manufactured_by_single_tracer": manufactured}, reason_codes=["TRACER_ABLATION_STABLE"] if passes else ["TRACER_DEPENDENT_SIGNAL"], evidence=evidence)


def _eval_dataset_substitution(gate_id: str, evidence: Mapping[str, Any]) -> dict[str, Any]:
    values = _classifications(evidence, key="datasets")
    stable = len(set(values)) == 1
    return _result(gate_id, "PASS" if stable else "FAIL", metrics={"classifications": values, "stable": stable}, classification_hint=values[0] if stable and values[0] in {"NO_DETECTION","ANCHOR_CONDITIONED_SIGNAL","MODEL_CLASS_DETECTION","PEER_SPECIFIC_DETECTION"} else None, reason_codes=["DATASET_SUBSTITUTION_STABLE"] if stable else ["DATASET_SUBSTITUTION_FLIPS"], evidence=evidence)


def _eval_growth(gate_id: str, evidence: Mapping[str, Any]) -> dict[str, Any]:
    tension = _as_float(evidence["max_new_tension_sigma"], "max_new_tension_sigma")
    catastrophic = bool(evidence.get("catastrophic_degradation", False))
    threshold = _REGISTRY["policy"]["max_growth_new_tension_sigma"]
    passes = tension <= threshold and not catastrophic
    return _result(gate_id, "PASS" if passes else "FAIL", metrics={"max_new_tension_sigma": tension, "threshold": threshold, "catastrophic_degradation": catastrophic}, reason_codes=["GROWTH_PREDICTION_ACCEPTABLE"] if passes else ["NEW_GROWTH_TENSION"], evidence=evidence)


def _eval_ppc(gate_id: str, evidence: Mapping[str, Any]) -> dict[str, Any]:
    raw = evidence.get("p_values")
    if isinstance(raw, Mapping):
        values = {str(k): _as_float(v, str(k)) for k, v in raw.items()}
    elif isinstance(raw, list):
        values = {str(i): _as_float(v, str(i)) for i, v in enumerate(raw)}
    else:
        raise ValueError("p_values must be object or list")
    lo, hi = _REGISTRY["policy"]["ppc_min"], _REGISTRY["policy"]["ppc_max"]
    passes = bool(values) and all(lo <= value <= hi for value in values.values())
    return _result(gate_id, "PASS" if passes else "FAIL", metrics={"p_values": values, "allowed_interval": [lo, hi]}, reason_codes=["PPC_BLOCKS_ACCEPTABLE"] if passes else ["PPC_EXTREME_TAIL"], evidence=evidence)


def _eval_holdout(gate_id: str, evidence: Mapping[str, Any]) -> dict[str, Any]:
    delta = _as_float(evidence["delta_elpd"], "delta_elpd")
    se = _as_float(evidence["se"], "se")
    if se <= 0:
        raise ValueError("se must be positive")
    z = delta / se
    threshold = _REGISTRY["policy"]["holdout_min_z"]
    passes = delta > 0 and z >= threshold
    return _result(gate_id, "PASS" if passes else "FAIL", metrics={"delta_elpd": delta, "se": se, "z": z, "threshold": threshold}, reason_codes=["HOLDOUT_PREDICTION_IMPROVES"] if passes else ["NO_HOLDOUT_ADVANTAGE"], evidence=evidence)


def _eval_rival_ic(gate_id: str, evidence: Mapping[str, Any]) -> dict[str, Any]:
    delta = _as_float(evidence["delta_ic_peer_minus_rival"], "delta_ic_peer_minus_rival")
    threshold = _REGISTRY["policy"]["rival_delta_ic_peer_better"]
    passes = delta <= threshold
    return _result(gate_id, "PASS" if passes else "FAIL", metrics={"delta_ic_peer_minus_rival": delta, "peer_better_threshold": threshold}, classification_hint=None if passes else "MODEL_CLASS_DETECTION", reason_codes=["PEER_BEATS_RIVAL"] if passes else ["RIVAL_NOT_DISFAVORED"], evidence=evidence)


def _eval_model_class_rival(gate_id: str, evidence: Mapping[str, Any]) -> dict[str, Any]:
    peer_specific = bool(evidence.get("peer_specific", False))
    early_sector_supported = bool(evidence.get("early_sector_supported", False))
    if peer_specific:
        return _result(gate_id, "PASS", metrics={"peer_specific": True, "early_sector_supported": early_sector_supported}, classification_hint="PEER_SPECIFIC_DETECTION", reason_codes=["PEER_DISTINGUISHED_FROM_MODEL_CLASS"], evidence=evidence)
    hint = "MODEL_CLASS_DETECTION" if early_sector_supported else "NO_DETECTION"
    return _result(gate_id, "FAIL", metrics={"peer_specific": False, "early_sector_supported": early_sector_supported}, classification_hint=hint, reason_codes=["MODEL_CLASS_ONLY"] if early_sector_supported else ["NO_EARLY_SECTOR_REQUIREMENT"], evidence=evidence)


def _eval_structural_rival(gate_id: str, evidence: Mapping[str, Any]) -> dict[str, Any]:
    if "peer_required" in evidence:
        passes = bool(evidence["peer_required"])
        delta = evidence.get("delta_ic_peer_minus_rival")
    else:
        delta = _as_float(evidence["delta_ic_peer_minus_rival"], "delta_ic_peer_minus_rival")
        passes = delta <= _REGISTRY["policy"]["rival_delta_ic_peer_better"]
    early = bool(evidence.get("early_sector_supported", False))
    hint = None if passes else ("MODEL_CLASS_DETECTION" if early else "NO_DETECTION")
    return _result(gate_id, "PASS" if passes else "FAIL", metrics={"peer_required": passes, "delta_ic_peer_minus_rival": delta}, classification_hint=hint, reason_codes=["PEER_SURVIVES_STRUCTURAL_RIVAL"] if passes else ["STRUCTURAL_RIVAL_NOT_DISFAVORED"], evidence=evidence)


def _eval_release(gate_id: str, evidence: Mapping[str, Any]) -> dict[str, Any]:
    shifts = _as_float_list(evidence["shifts_sigma"], "shifts_sigma")
    max_shift = max(abs(value) for value in shifts)
    threshold = _REGISTRY["policy"]["max_release_shift_sigma"]
    passes = max_shift < threshold
    return _result(gate_id, "PASS" if passes else "FAIL", metrics={"max_shift_sigma": max_shift, "threshold": threshold, "n_variants": len(shifts)}, reason_codes=["RELEASE_ROBUST"] if passes else ["RELEASE_SENSITIVE"], evidence=evidence)


def _eval_codepath(gate_id: str, evidence: Mapping[str, Any]) -> dict[str, Any]:
    shift = abs(_as_float(evidence["max_shift_sigma"], "max_shift_sigma"))
    delta = abs(_as_float(evidence["delta_chi2"], "delta_chi2"))
    p = _REGISTRY["policy"]
    passes = shift <= p["codepath_max_shift_sigma"] and delta <= p["codepath_max_delta_chi2"]
    return _result(gate_id, "PASS" if passes else "FAIL", metrics={"max_shift_sigma": shift, "delta_chi2": delta, "shift_threshold": p["codepath_max_shift_sigma"], "delta_chi2_threshold": p["codepath_max_delta_chi2"]}, reason_codes=["CODEPATHS_EQUIVALENT"] if passes else ["CODEPATH_REPLICATION_MISMATCH"], evidence=evidence)


def _eval_seed_optimizer(gate_id: str, evidence: Mapping[str, Any]) -> dict[str, Any]:
    runs = int(evidence["run_count"])
    dispersion = abs(_as_float(evidence["basin_dispersion_sigma"], "basin_dispersion_sigma"))
    same_basin = bool(evidence.get("same_physical_basin", False))
    p = _REGISTRY["policy"]
    passes = runs >= p["seed_min_runs"] and dispersion <= p["seed_max_basin_dispersion_sigma"] and same_basin
    return _result(gate_id, "PASS" if passes else "FAIL", metrics={"run_count": runs, "basin_dispersion_sigma": dispersion, "same_physical_basin": same_basin, "minimum_runs": p["seed_min_runs"], "max_dispersion_sigma": p["seed_max_basin_dispersion_sigma"]}, reason_codes=["OPTIMIZER_BASIN_REPRODUCIBLE"] if passes else ["OPTIMIZER_BASIN_UNSTABLE"], evidence=evidence)


def synthesise_detection(results: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    expected = [f"D{i:02d}" for i in range(25)]
    missing = [gate for gate in expected if gate not in results]
    if missing:
        return {"classification": "INCONCLUSIVE", "reason_codes": ["MISSING_GATE_RESULTS"], "missing_gates": missing}

    d09 = results["D09"]
    if d09.get("classification_hint") == "ANCHOR_CONDITIONED_SIGNAL":
        return {"classification": "ANCHOR_CONDITIONED_SIGNAL", "reason_codes": ["D09_ANCHOR_CONDITIONED_STOP"]}

    unresolved = [gate for gate in expected if str(results[gate].get("gate_status")) in {"INCONCLUSIVE", "SKIPPED_BY_POLICY"}]
    if unresolved:
        return {"classification": "INCONCLUSIVE", "reason_codes": ["UNRESOLVED_MANDATORY_GATES"], "unresolved_gates": unresolved}

    if any(str(results[gate].get("gate_status")) == "FAIL" for gate in ("D01", "D02", "D03", "D04")):
        return {"classification": "NO_DETECTION", "reason_codes": ["CORE_DETECTION_GATE_FAILED"]}

    rival_hints = [str(results[gate].get("classification_hint") or "") for gate in ("D18", "D19", "D20", "D21")]
    if "MODEL_CLASS_DETECTION" in rival_hints:
        return {"classification": "MODEL_CLASS_DETECTION", "reason_codes": ["RIVAL_MODEL_CLASS_NOT_DISFAVORED"]}
    if "NO_DETECTION" in rival_hints:
        return {"classification": "NO_DETECTION", "reason_codes": ["RIVAL_TEST_REMOVES_REQUIREMENT"]}

    failures = [gate for gate in expected if str(results[gate].get("gate_status")) == "FAIL"]
    if failures:
        return {"classification": "NO_DETECTION", "reason_codes": ["ROBUSTNESS_GATE_FAILED"], "failed_gates": failures}

    if str(results["D19"].get("classification_hint") or "") == "PEER_SPECIFIC_DETECTION":
        return {"classification": "PEER_SPECIFIC_DETECTION", "reason_codes": ["ALL_MANDATORY_GATES_PASS_AND_PEER_DISTINGUISHED"]}

    return {"classification": "MODEL_CLASS_DETECTION", "reason_codes": ["EARLY_SECTOR_SURVIVES_WITHOUT_PEER_SPECIFIC_DISCRIMINATION"]}


def _eval_synthesis(gate_id: str, evidence: Mapping[str, Any], prior_results: Mapping[str, Mapping[str, Any]] | None) -> dict[str, Any]:
    source = prior_results
    if source is None:
        raw = evidence.get("results")
        if isinstance(raw, Mapping):
            source = raw  # type: ignore[assignment]
    if source is None:
        raise ValueError("D25 requires prior gate results")
    synthesis = synthesise_detection(source)
    classification = synthesis["classification"]
    status = "INCONCLUSIVE" if classification == "INCONCLUSIVE" else "PASS"
    return _result(gate_id, status, metrics=synthesis, classification_hint=classification, reason_codes=list(synthesis.get("reason_codes", [])), evidence=evidence)


_EVALUATORS = {
    "delta_chi2": _eval_delta_chi2,
    "profile": _eval_profile,
    "bayes_evidence": _eval_bayes,
    "prior_sensitivity": _eval_prior_sensitivity,
    "injection_recovery": _eval_injection,
    "sbc": _eval_sbc,
    "anchor_ablation": _eval_anchor_ablation,
    "anchor_swap": _eval_anchor_swap,
    "split_consistency": _eval_split_consistency,
    "block_dominance": _eval_block_dominance,
    "leave_one_out": _eval_leave_one_out,
    "dataset_substitution": _eval_dataset_substitution,
    "growth_tension": _eval_growth,
    "ppc": _eval_ppc,
    "holdout": _eval_holdout,
    "rival_ic": _eval_rival_ic,
    "model_class_rival": _eval_model_class_rival,
    "structural_rival": _eval_structural_rival,
    "release_robustness": _eval_release,
    "codepath_replication": _eval_codepath,
    "seed_optimizer": _eval_seed_optimizer,
}


def evaluate_gate(
    gate_id: str,
    evidence: Mapping[str, Any] | None,
    prior_results: Mapping[str, Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    gate_id = str(gate_id).upper()
    gate = _REGISTRY["gates"].get(gate_id)
    if gate is None:
        raise ValueError(f"unknown PEER detection gate: {gate_id}")

    evaluator = gate["evaluator"]
    if evaluator == "freeze":
        try:
            registry = load_gate_registry()
            return _result(
                gate_id,
                "PASS",
                metrics={"gate_count": len(registry["gates"]), "execution_order_count": len(registry["execution_order"]), "policy_digest": policy_digest()},
                reason_codes=["BATTERY_POLICY_FROZEN"],
            )
        except Exception as exc:
            return _inconclusive(gate_id, "FREEZE_VALIDATION_FAILED", detail=str(exc))

    if evidence is None:
        return _inconclusive(gate_id, "INPUT_BUNDLE_NOT_BOUND")
    if not isinstance(evidence, Mapping):
        return _inconclusive(gate_id, "INPUT_BUNDLE_INVALID", evidence=evidence)

    try:
        if evaluator == "empirical_tail":
            return _eval_empirical_tail(gate_id, evidence)
        if evaluator == "look_elsewhere":
            return _eval_empirical_tail(gate_id, evidence, scan=True)
        if evaluator == "synthesis":
            return _eval_synthesis(gate_id, evidence, prior_results)
        function = _EVALUATORS[evaluator]
        return function(gate_id, evidence)
    except (KeyError, TypeError, ValueError, ZeroDivisionError) as exc:
        return _inconclusive(gate_id, "INPUT_BUNDLE_INVALID", evidence=evidence, detail=str(exc))
