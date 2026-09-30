"""Engenharia de descoberta: os "sonhos" do livro do NEXO (caps. 4.3, 6.2, 10 e 11), feitos em código pequeno.

  information_value     ganho esperado de informação (proxy) para ordenar o que roda primeiro
  learning_loop         aprendizado procedural: regra candidata -> baseline -> holdout temporal -> promove ou rejeita,
                        com MERGE -> EXTEND -> SUPERSEDE -> CREATE sobre evolution/learning.json
  search_space          look-elsewhere: quantas comparações uma família ou um roadmap abriu (o "N" da correção)
  autonomy_metrics      indicadores operacionais auditáveis; proxies não comprovam ausência de intervenção
Estratégia, nunca verdade científica: a regra só muda a ordem e a prioridade dos testes, não os vereditos.
"""
from __future__ import annotations

import statistics
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

LEARNING_DOC = "evolution/learning.json"
MIN_CASES = 20
MIN_GAIN = 0.10
DECISIVE = {"PROMOTED", "PROMOVIDO", "REJECTED", "REJEITADO", "CONFIRMED", "REFUTED"}
INCONCLUSIVE = {"INCONCLUSIVE", "INCONCLUSIVO"}


def _verdict(test: dict[str, Any]) -> str:
    return str(test.get("verdict") or "").upper()


def _when(test: dict[str, Any]) -> str:
    e = test.get("executed_at")
    return str((e.get("at") if isinstance(e, dict) else e) or "")


def features(test: dict[str, Any]) -> dict[str, str]:
    """Traits known BEFORE the run, so a rule built on them can steer what runs next."""
    params = test.get("recipe_params") if isinstance(test.get("recipe_params"), dict) else {}
    units = len(params.get("bands") or params.get("tracer_groups") or [])
    comps = params.get("compilations") or []
    return {
        "recipe": str(test.get("recipe") or ""),
        "mode": str(params.get("mode") or ""),
        "n_compilations": str(len(comps)),
        "has_union3": str("union3" in comps),
        "units": str(units),
    }


def information_value(test: dict[str, Any], rules: list[dict[str, Any]] | None = None) -> float:
    """EIG proxy: uncertainty of the prediction (p(1-p), max at 0.5) x chance the run decides anything / cost (units of the grid)."""
    pred = test.get("prediction") if isinstance(test.get("prediction"), dict) else {}
    try:
        p = min(max(float(pred.get("p_promoted")), 0.02), 0.98)
    except (TypeError, ValueError):
        p = 0.5
    decides = 1.0
    feats = features(test)
    for rule in rules or []:
        if rule.get("state") == "ACTIVE" and feats.get(rule["feature"]) == rule["value"]:
            decides = min(decides, 1.0 - float(rule.get("inconclusive_rate") or 0.0))
    cost = max(1, len(((test.get("recipe_params") or {}).get("compilations")) or [1]) * max(1, int(feats["units"] or 1)))
    return round(4 * p * (1 - p) * decides / cost ** 0.5, 4)


def _candidates(rows: list[tuple[dict[str, str], bool]]) -> list[tuple[str, str]]:
    seen = {(k, v) for feats, _ in rows for k, v in feats.items() if k != "recipe" and v}
    return sorted(seen)


def learning_loop(tests: list[dict[str, Any]], current: dict[str, Any] | None = None) -> dict[str, Any]:
    """Rule candidate "runs with feature f=v end INCONCLUSIVE": fit on the older half, judge ONCE on the newer half against the
    majority baseline. Promote only if it beats the baseline by MIN_GAIN. Existing rules are merged, extended or superseded before a new one is created."""
    from .execution_assessment import has_valid_operational_exclusion
    excluded, included = [], []
    for test in tests:
        (excluded if has_valid_operational_exclusion(test) else included).append(test)
    tests = included
    rows = sorted(((_when(t), features(t), _verdict(t) in INCONCLUSIVE) for t in tests
                   if t.get("recipe") and _verdict(t) and _when(t) and (_verdict(t) in DECISIVE or _verdict(t) in INCONCLUSIVE)),
                  key=lambda r: r[0])
    doc = dict(current or {"rules": []})
    rules = [dict(r) for r in doc.get("rules") or []]
    if len(rows) < MIN_CASES:
        return {**doc, "rules": rules, "evaluated": {"cases": len(rows), "excluded_operational": len(excluded), "note": "poucos casos para avaliar"}}
    half = len(rows) // 2
    train, hold = [(f, y) for _, f, y in rows[:half]], [(f, y) for _, f, y in rows[half:]]
    base_rate = statistics.fmean(y for _, y in hold) if hold else 0.0
    baseline_acc = max(base_rate, 1 - base_rate)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    report = []
    for feat, value in _candidates(train + hold):
        fit = [y for f, y in train if f.get(feat) == value]
        if len(fit) < 5:
            continue
        rate = statistics.fmean(fit)
        predict_inc = rate >= 0.6
        if not predict_inc:
            continue
        acc = statistics.fmean(((f.get(feat) == value) == y) if (f.get(feat) == value) else (not y) for f, y in hold)
        gain = acc - baseline_acc
        entry = {"feature": feat, "value": value, "inconclusive_rate": round(rate, 3), "n_train": len(fit),
                 "holdout_accuracy": round(acc, 3), "baseline": round(baseline_acc, 3), "gain": round(gain, 3)}
        report.append(entry)
        if gain < MIN_GAIN:
            continue
        same = next((r for r in rules if r["feature"] == feat and r["value"] == value), None)
        overlap = next((r for r in rules if r["feature"] == feat and r["value"] != value and r.get("state") == "ACTIVE"), None)
        if same:
            same.update(entry, revised_at=now)  # MERGE: same rule, fresher numbers
        elif overlap and gain > float(overlap.get("gain") or 0):
            overlap.update(state="SUPERSEDED", superseded_by=f"{feat}={value}")  # SUPERSEDE: better rule on the same trait
            rules.append({**entry, "state": "ACTIVE", "created_at": now, "op": "SUPERSEDE"})
        elif overlap:
            continue
        else:
            rules.append({**entry, "state": "ACTIVE", "created_at": now, "op": "CREATE"})
    # A rule that stops beating the baseline on the newest half is retired, not kept out of habit.
    for r in rules:
        if r.get("state") == "ACTIVE" and not any(e["feature"] == r["feature"] and e["value"] == r["value"] and e["gain"] >= MIN_GAIN for e in report):
            r.update(state="RETIRED", retired_at=now)
    return {"rules": rules, "evaluated": {"cases": len(rows), "excluded_operational": len(excluded), "holdout": len(hold), "baseline": round(baseline_acc, 3), "candidates": report[:8]}}


def search_space(tests: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Look-elsewhere register: comparisons opened per roadmap and family. A positive out of N looks is reported with its N."""
    out: dict[str, dict[str, Any]] = {}
    for t in tests:
        if t.get("contests_test_id"):
            continue
        key = str(t.get("family_id") or t.get("roadmap_id") or "")
        if not key:
            continue
        slot = out.setdefault(key, {"comparisons": 0, "positives": 0})
        slot["comparisons"] += 1
        slot["positives"] += _verdict(t) in {"PROMOTED", "PROMOVIDO", "SUPPORTED", "CONFIRMED"}
    for slot in out.values():
        n, k = slot["comparisons"], slot["positives"]
        # chance of at least one false positive at alpha=0.05 across n looks (Sidak); how many positives chance alone would give
        slot["chance_any_positive"] = round(1 - 0.95 ** n, 3)
        slot["expected_by_chance"] = round(0.05 * n, 2)
        slot["excess_positives"] = round(k - 0.05 * n, 2)
    return out


def autonomy_metrics(tests: list[dict[str, Any]], hours: int = 24, now: datetime | None = None) -> dict[str, Any]:
    """Operational observations with explicit cohorts, plus unchanged legacy aliases.

    Recorded execution/family metadata cannot establish unattended operation, and
    a verdict label cannot establish scientific certainty. Stock measures include
    all supplied tests; only measures with scope=window use the execution window.
    """
    now = now or datetime.now(timezone.utc)
    now = now.replace(tzinfo=timezone.utc) if now.tzinfo is None else now.astimezone(timezone.utc)

    def timestamp(iso: str) -> datetime | None:
        try:
            when = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        except (TypeError, ValueError):
            return None
        if when.tzinfo is None:  # agents sometimes write naive timestamps: read them as UTC
            when = when.replace(tzinfo=timezone.utc)
        return when

    def age_h(iso: str) -> float | None:
        when = timestamp(iso)
        return (now - when).total_seconds() / 3600 if when is not None else None

    recent = [t for t in tests if (a := age_h(_when(t))) is not None and 0 <= a <= hours and not t.get("contests_test_id")]
    done = [t for t in recent if _verdict(t)]
    non_inconclusive = sum(_verdict(t) not in INCONCLUSIVE for t in done)
    decisive = sum(_verdict(t) in DECISIVE for t in done)
    inconclusive = sum(_verdict(t) in INCONCLUSIVE for t in done)
    waits = []
    legacy_waits = []
    latency_counts = {"measured": 0, "missing_start": 0, "invalid_start": 0, "start_after_execution": 0}
    latency_sources = {"created_at_effective": 0, "created_at": 0, "first_observed_at": 0, "missing": 0}
    for t in done:
        source = next((key for key in ("created_at_effective", "created_at", "first_observed_at") if t.get(key)), None)
        latency_sources[source or "missing"] += 1
        created = str(t.get(source) or "") if source else ""
        start, end = timestamp(created), timestamp(_when(t))
        if not created:
            latency_counts["missing_start"] += 1
        elif start is None:
            latency_counts["invalid_start"] += 1
        elif start > end:
            latency_counts["start_after_execution"] += 1
        else:
            waits.append((end - start).total_seconds() / 3600)
            latency_counts["measured"] += 1
        legacy_created = str(t.get("created_at_effective") or t.get("first_observed_at") or "")
        legacy_start = timestamp(legacy_created)
        if legacy_start is not None and legacy_start <= end:
            legacy_waits.append((end - legacy_start).total_seconds() / 3600)
    positives = [t for t in tests if _verdict(t) in {"PROMOTED", "PROMOVIDO", "SUPPORTED"} and not t.get("contests_test_id")]
    closed = [t for t in positives if t.get("review_state") in {"CONFIRMED", "REFUTED"}]
    failed = [t for t in tests if int(t.get("runtime_failure_count") or 0) > 0]
    ready = sum(1 for t in tests if str(t.get("status") or "").upper() == "READY")
    blocked = sum(1 for t in tests if str(t.get("status") or "").upper().startswith("BLOCKED"))
    rate = lambda a, b: round(a / b, 3) if b else None
    result_count = len(done)
    execution_records = sum(1 for t in done if t.get("family_id") or t.get("execution"))
    failure_results = sum(1 for t in failed if _verdict(t))
    median_wait = round(statistics.median(waits), 1) if waits else None
    legacy_median_wait = round(statistics.median(legacy_waits), 1) if legacy_waits else None

    def metric(value: int | float | None, numerator: int | None, denominator: int | None,
               scope: str, definition: str, unit: str = "ratio", **extra: Any) -> dict[str, Any]:
        return {"value": value, "numerator": numerator, "denominator": denominator,
                "scope": scope, "definition": definition, "unit": unit, **extra}

    metrics = {
        "results": metric(result_count, result_count, None, "window",
            "Non-contestation tests with a non-empty verdict and a valid executed_at within the inclusive window.", "count"),
        "execution_record_share": metric(rate(execution_records, result_count), execution_records, result_count, "window",
            "Window results with truthy family_id or execution metadata. A recording proxy; does not establish absence of human or agent intervention."),
        "decisive_rate": metric(rate(decisive, result_count), decisive, result_count, "window",
            "Window results whose recorded verdict is in the explicit decisive allowlist. Label coverage, not scientific certainty.",
            verdicts=sorted(DECISIVE)),
        "non_inconclusive_rate": metric(rate(non_inconclusive, result_count), non_inconclusive, result_count, "window",
            "Window results with any non-empty verdict except INCONCLUSIVE/INCONCLUSIVO, including unrecognized labels. Legacy outcome coverage, not a decision rate.",
            definition_id="LEGACY_NON_INCONCLUSIVE"),
        "median_hours_to_result": metric(median_wait, None, None, "window",
            "Median hours from the first present timestamp in created_at_effective, created_at, first_observed_at to executed_at among window results with valid non-negative durations. Measures recorded test age, not time since the idea.", "hours",
            sample_count=len(waits), coverage={"value": rate(len(waits), result_count), "numerator": len(waits), "denominator": result_count}),
        "legacy_median_hours_to_result": metric(legacy_median_wait, None, None, "window",
            "Legacy median hours from created_at_effective, or first_observed_at when absent, to executed_at among window results with valid non-negative durations; ignores created_at.", "hours",
            definition_id="LEGACY_OBSERVATION_LATENCY", sample_count=len(legacy_waits),
            coverage={"value": rate(len(legacy_waits), result_count), "numerator": len(legacy_waits), "denominator": result_count}),
        "positive_review_closure": metric(rate(len(closed), len(positives)), len(closed), len(positives), "all_tests",
            "Non-contestation tests labeled PROMOTED/PROMOVIDO/SUPPORTED with review_state exactly CONFIRMED or REFUTED, divided by all such positive tests. Stock, not window throughput or confirmation rate."),
        "failure_result_coverage": metric(rate(failure_results, len(failed)), failure_results, len(failed), "all_tests",
            "Tests with runtime_failure_count > 0 and any recorded verdict divided by all tests with runtime_failure_count > 0, including contestations. Does not establish recovery ordering."),
        "blocked_share": metric(rate(blocked, ready + blocked), blocked, ready + blocked, "all_tests",
            "Tests whose uppercased status starts with BLOCKED divided by READY plus BLOCKED* tests, including contestations. Does not classify any block as false."),
    }
    return {
        "schema_version": "AUTONOMY_METRICS_V2",
        "computed_at": now.isoformat().replace("+00:00", "Z"),
        "window_start": (now - timedelta(hours=hours)).isoformat().replace("+00:00", "Z"),
        "window_end": now.isoformat().replace("+00:00", "Z"),
        "window_hours": hours,
        "metrics": metrics,
        "buckets": {
            "result_verdicts": dict(sorted(Counter(_verdict(t) for t in done).items())),
            "result_categories": {"decisive": decisive, "inconclusive": inconclusive,
                                "other": result_count - decisive - inconclusive},
            "result_execution_records": {"execution_or_family": execution_records, "neither": result_count - execution_records},
            "latency_coverage": latency_counts,
            "latency_start_sources": latency_sources,
            "positive_review_states": dict(sorted(Counter(str(t.get("review_state") or "MISSING") for t in positives).items())),
            "queue_statuses": {"ready": ready, "blocked": blocked, "other": len(tests) - ready - blocked},
            "failure_results": {"with_verdict": failure_results, "without_verdict": len(failed) - failure_results},
        },
        "legacy_aliases": {
            "results": "results", "robot_share": "execution_record_share",
            "decisive_rate": "non_inconclusive_rate", "info_per_test": "non_inconclusive_rate",
            "median_hours_to_result": "legacy_median_hours_to_result", "contest_closure": "positive_review_closure",
            "recovery_rate": "failure_result_coverage", "false_block_share": "blocked_share",
        },
        "results": result_count,
        "robot_share": rate(execution_records, result_count),
        "decisive_rate": rate(non_inconclusive, result_count),
        "median_hours_to_result": legacy_median_wait,
        "contest_closure": rate(len(closed), len(positives)),
        "recovery_rate": rate(failure_results, len(failed)),
        "false_block_share": rate(blocked, ready + blocked),
        "info_per_test": rate(non_inconclusive, result_count),
    }
