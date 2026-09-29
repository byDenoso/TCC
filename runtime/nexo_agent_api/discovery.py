"""Engenharia de descoberta: os "sonhos" do livro do NEXO (caps. 4.3, 6.2, 10 e 11), feitos em código pequeno.

  information_value     ganho esperado de informação (proxy) para ordenar o que roda primeiro
  learning_loop         aprendizado procedural: regra candidata -> baseline -> holdout temporal -> promove ou rejeita,
                        com MERGE -> EXTEND -> SUPERSEDE -> CREATE sobre evolution/learning.json
  search_space          look-elsewhere: quantas comparações uma família ou um roadmap abriu (o "N" da correção)
  autonomy_metrics      vetor de autonomia: o que o ciclo fecha sem operador
Estratégia, nunca verdade científica: a regra só muda a ordem e a prioridade dos testes, não os vereditos.
"""
from __future__ import annotations

import statistics
from datetime import datetime, timezone
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
    rows = sorted(((_when(t), features(t), _verdict(t) in INCONCLUSIVE) for t in tests
                   if t.get("recipe") and _verdict(t) and _when(t) and (_verdict(t) in DECISIVE or _verdict(t) in INCONCLUSIVE)),
                  key=lambda r: r[0])
    doc = dict(current or {"rules": []})
    rules = [dict(r) for r in doc.get("rules") or []]
    if len(rows) < MIN_CASES:
        return {**doc, "rules": rules, "evaluated": {"cases": len(rows), "note": "poucos casos para avaliar"}}
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
    return {"rules": rules, "evaluated": {"cases": len(rows), "holdout": len(hold), "baseline": round(baseline_acc, 3), "candidates": report[:8]}}


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
    """Vetor de autonomia (livro, cap. 11.3), medido sobre a janela recente."""
    now = now or datetime.now(timezone.utc)

    def age_h(iso: str) -> float | None:
        try:
            return (now - datetime.fromisoformat(iso.replace("Z", "+00:00"))).total_seconds() / 3600
        except ValueError:
            return None

    recent = [t for t in tests if (a := age_h(_when(t))) is not None and a <= hours and not t.get("contests_test_id")]
    done = [t for t in recent if _verdict(t)]
    decisive = [t for t in done if _verdict(t) not in INCONCLUSIVE]
    waits = []
    for t in done:
        created = str(t.get("created_at_effective") or t.get("first_observed_at") or "")
        if created and (a := age_h(created)) is not None and (b := age_h(_when(t))) is not None and a >= b:
            waits.append(a - b)
    positives = [t for t in tests if _verdict(t) in {"PROMOTED", "PROMOVIDO", "SUPPORTED"} and not t.get("contests_test_id")]
    closed = [t for t in positives if t.get("review_state") in {"CONFIRMED", "REFUTED"}]
    failed = [t for t in tests if int(t.get("runtime_failure_count") or 0) > 0]
    ready = sum(1 for t in tests if str(t.get("status") or "").upper() == "READY")
    blocked = sum(1 for t in tests if str(t.get("status") or "").upper().startswith("BLOCKED"))
    rate = lambda a, b: round(a / b, 3) if b else None
    return {
        "window_hours": hours,
        "results": len(done),
        "robot_share": rate(sum(1 for t in done if t.get("family_id") or t.get("execution")), len(done)),
        "decisive_rate": rate(len(decisive), len(done)),
        "median_hours_to_result": round(statistics.median(waits), 1) if waits else None,
        "contest_closure": rate(len(closed), len(positives)),
        "recovery_rate": rate(sum(1 for t in failed if _verdict(t)), len(failed)),
        "false_block_share": rate(blocked, ready + blocked),
        "info_per_test": rate(len(decisive), len(done)),
    }
