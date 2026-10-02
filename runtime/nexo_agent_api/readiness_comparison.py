"""Read-only C01 comparison producer; never routes or promotes a canary.

Run only on an authorized, immutable materialization. This diagnostic is not an
offline-corpus/shadow admission report: it makes no assertion about corpus
strata, independent units, a frozen analysis plan, or private-source authority.
No recipe is executed, no Tower/registry/selection state is written.
"""
from __future__ import annotations

import copy
from pathlib import Path
from typing import Any, Mapping

from . import scientific_integrity
from .operational_canary import (
    _measure_path_reads, _readiness_results_equal, digest_json,
    loaded_readiness_cache_sha256,
)
from .readiness_cache import (
    ReadinessCache, ReadinessCacheContext,
    evaluate_with_readiness_cache,
)


def compare_readiness(root: Path, test: Mapping[str, Any], *,
                      access_scope: str, authorization_revision: str,
                      manifest_revision: str, manifest_sha256: str) -> dict[str, Any]:
    """Measure both execution orders, including cold fill and context overhead.

    Only hashes, error classes and measurements leave this function; input
    bindings, readiness reasons, private paths and contents are not emitted.
    An unavailable context runs baseline only and cannot be called cache proof.
    Replays are repeated observations, never additional independent live units.
    """
    snapshot = copy.deepcopy(dict(test))

    def baseline():
        return scientific_integrity.readiness(root, snapshot)

    def capture():
        return ReadinessCacheContext.from_runtime(
            root, snapshot, access_scope=access_scope,
            authorization_revision=authorization_revision,
            manifest_revision=manifest_revision, manifest_sha256=manifest_sha256,
            validator=scientific_integrity.readiness,
            validator_version=scientific_integrity.POLICY)

    def measure(label, action):
        def outcome():
            try:
                return {"ok": True, "value": action()}
            except Exception as error:
                return {"ok": False, "error_type": type(error).__name__}
        return _measure_path_reads(label, outcome)

    records = []
    for order in ("BASELINE_THEN_CANDIDATE", "CANDIDATE_THEN_BASELINE"):
        cache = ReadinessCache()
        before, context_metrics = measure("context_before", capture)
        if not before["ok"]:
            result, metric = measure("baseline", baseline)
            records.append({"order": order, "status": "CONTEXT_UNAVAILABLE",
                            "context_error_type": before["error_type"],
                            "baseline_ok": result["ok"], "baseline_metrics": metric,
                            "context_metrics": context_metrics})
            continue
        context = before["value"]
        # Cold fill is reported separately, not hidden in a claimed hit saving.
        warmup, warmup_metrics = measure("candidate_cold", lambda:
            evaluate_with_readiness_cache(baseline, context, cache, enabled=True))
        variants = ("baseline", "candidate") if order.startswith("BASELINE") else ("candidate", "baseline")
        results, metrics = {}, {}
        for variant in variants:
            results[variant], metrics[variant] = measure(variant, baseline if variant == "baseline" else lambda:
                evaluate_with_readiness_cache(baseline, context, cache, enabled=True))
        after, after_metrics = measure("context_after", capture)
        stable = after["ok"] and context.key == after["value"].key
        successful = warmup["ok"] and all(result["ok"] for result in results.values())
        equal = successful and _readiness_results_equal(
            results["baseline"]["value"], results["candidate"]["value"])
        records.append({
            "order": order,
            "status": "MATCH" if stable and equal else "CONTEXT_CHANGED" if not stable else "ERROR" if not successful else "MISMATCH",
            "context_sha256": context.key,
            "context_stable": stable, "equal": bool(equal),
            "result_sha256": {name: digest_json(result["value"]) if result["ok"] else None
                              for name, result in results.items()},
            "error_types": {name: result["error_type"] for name, result in results.items() if not result["ok"]},
            "metrics": metrics, "cold_fill_metrics": warmup_metrics,
            "context_before_metrics": context_metrics, "context_after_metrics": after_metrics,
        })
    report = {
        "contract": "C01_READINESS_COMPARISON_DIAGNOSTIC_V1",
        "adapter_id": "readiness_cache",
        "candidate_adapter_sha256": loaded_readiness_cache_sha256(),
        "selection": "BASELINE", "activation_evidence": False,
        "scope": "READINESS_SOFTWARE_ONLY_NOT_SCIENTIFIC_PROOF",
        "all_equal_and_stable": all(record["status"] == "MATCH" for record in records),
        "records": records,
    }
    report["report_sha256"] = digest_json(report)
    return report
