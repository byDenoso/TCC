"""Fixed Writer policy for prospective, evidence-bound capacity increments.

The policy evaluates the entire current-stage sample. An agent recommendation
and its claimed role never authorize a capacity increment.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import re

from . import autonomy as a
from . import scientific_integrity as s

REGISTRY = "evolution/autonomy_capacity_reviews.json"
SCHEMA = "NEXO_CAPACITY_REVIEW_REGISTRY_V1"
POLICY = {"id": "NEXO_CAPACITY_STABILITY_V1", "minimum_successful_batteries": 2,
          "sample": "ALL_CURRENT_STAGE_SINCE_ENTRY", "independent_review_required": True,
          "unique_runs_and_attempts": True, "zero_runtime_failures": True,
          "full_capacity_overlap_required": True}


def _reviewed_pair(root, parent, attack):
    from .evolution import _attack_outcome
    if parent.get("review_state") not in {"CONFIRMED", "REFUTED"} or attack.get("contests_test_id") != parent.get("id"):
        return False
    for test in (parent, attack):
        evidence, issues = s.execution_phase_reconciliation_evidence(root, dict(test, execution_phase="RUNNING"))
        if (not evidence or issues or test.get("mandate_id") != a.mandate(root).get("id")
                or test.get("public_data_only") is not True or test.get("visibility") != "PUBLIC"):
            return False
    outcome = _attack_outcome(attack)
    declaration = attack.get("independence") or {}
    expected = declaration.get("on_pass" if outcome == "CONFIRMED" else "on_fail")
    if not outcome or expected != parent.get("review_state") or not s.independence(parent, attack, Path(root))["eligible"]:
        return False
    for review in parent.get("reviews") or []:
        if (review.get("contest_test_id") != attack.get("id") or not a.timestamp(review.get("at"))
                or review.get("referee") not in {"REFEREE_1", "GUARDIAO"}
                or review.get("outcome") != ("SURVIVED" if expected == "CONFIRMED" else "REFUTED")):
            continue
        if any(entry.get("contest_test_id") == attack.get("id") and entry.get("by") == review["referee"]
               for entry in parent.get("contests") or []):
            return True
    return False


def facts(root, now=None):
    try:
        return _facts(root, now)
    except (AttributeError, KeyError, OSError, TypeError, ValueError):
        return None  # malformed evidence must block growth, not interrupt Writer


def _facts(root, now=None):
    """Recompute eligibility; never select successful rows out of a failed sample."""
    now = now or datetime.now(timezone.utc)
    mandate, capacity = a.mandate(root), a.read(root, a.CAPACITY_DOC)
    stage = a.parallelism(root)
    since = a.timestamp(capacity.get("stage_started_at") or mandate.get("activated_at"))
    quota = capacity.get("quota") or {}
    checked = a.timestamp(quota.get("checked_at"))
    if (not a.active(root) or mandate.get("capacity_policy") != POLICY or stage not in {1, 2}
            or not since or quota.get("status") != "AVAILABLE_FREE" or quota.get("additional_cost") != 0
            or quota.get("standard_public_runners") is not True or not checked
            or not 0 <= (now - checked).total_seconds() <= 3600):
        return None
    sample = []
    for battery in s.batteries(root):
        if battery.get("mandate_id") != mandate["id"] or battery.get("parallelism") != stage:
            continue
        created = a.timestamp(battery.get("created_at"))
        if not created:
            return None
        if created >= since:
            sample.append(battery)
    if len(sample) < POLICY["minimum_successful_batteries"]:
        return None
    runs, attempts, fingerprints, test_records = set(), set(), set(), {}
    full_samples = 0
    for battery in sample:
        specs = battery.get("tests") or []
        completed = a.timestamp(battery.get("completed_at"))
        run = battery.get("run_ref")
        if (battery.get("status") != "DONE" or battery.get("conclusion") != "success"
                or battery.get("execution_observation") != "GITHUB_RUN_AND_ARTIFACT"
                or not specs or battery.get("ok") != len(specs) or battery.get("failed") != 0
                or battery.get("phase_failure_receipts") or not completed or completed > now
                or not s.RUN_REF.fullmatch(str(run or "")) or run in runs):
            return None
        runs.add(run)
        intervals = []
        for spec in specs:
            tid = str(spec.get("test_id") or "")
            if not re.fullmatch(r"[A-Za-z0-9_-]+", tid):
                return None
            test = a.read(root, "entities/test/" + tid + ".json")
            attempt, fingerprint = spec.get("attempt_id"), spec.get("execution_fingerprint")
            # Reuse the same strict terminal provenance predicate as Writer
            # result closure. The adapter changes no canonical execution phase.
            evidence, issues = s.execution_phase_reconciliation_evidence(root, dict(test, execution_phase="RUNNING"))
            if (not evidence or issues or test.get("mandate_id") != mandate["id"]
                    or test.get("battery_id") != battery["id"] or not attempt or attempt in attempts
                    or not fingerprint or fingerprint in fingerprints):
                return None
            attempts.add(attempt)
            fingerprints.add(fingerprint)
            intervals.append((a.timestamp(test["started_at"]), a.timestamp(test["executed_at"])))
            test_records[tid] = test
            if test.get("contests_test_id"):
                parent = a.read(root, "entities/test/" + str(test["contests_test_id"]) + ".json")
                if not _reviewed_pair(root, parent, test):
                    return None
                test_records[parent["id"]] = parent
            else:
                attack = next((a.read(root, "entities/test/" + str(review.get("contest_test_id")) + ".json")
                               for review in test.get("reviews") or []
                               if re.fullmatch(r"[A-Za-z0-9_-]+", str(review.get("contest_test_id") or ""))
                               and _reviewed_pair(root, test, a.read(root, "entities/test/" + str(review["contest_test_id"]) + ".json"))), None)
                if not attack:
                    return None
                test_records[attack["id"]] = attack
        if len(specs) == stage and (stage == 1 or max(start for start, _ in intervals) < min(end for _, end in intervals)):
            full_samples += 1
    if full_samples < POLICY["minimum_successful_batteries"]:
        return None
    proof = {"schema": "NEXO_CAPACITY_REVIEW_V1", "policy": POLICY["id"],
             "approved_by": "WRITER_GUARDIAN_POLICY", "decision": "PASS", "mandate_id": mandate["id"],
             "stage": stage, "next_parallelism": {1: 2, 2: 4}[stage],
             "sample_since": since.isoformat().replace("+00:00", "Z"),
             "battery_refs": sorted(battery["id"] for battery in sample),
             "battery_sha256": {battery["id"]: a.digest(battery) for battery in sample},
             "test_sha256": {tid: a.digest(test) for tid, test in test_records.items()}}
    proof["id"] = "CAPACITY-" + a.digest(proof)[:32]
    return proof


def approved(root, reference, now=None):
    prefix = REGISTRY + "#"
    if not isinstance(reference, str) or not reference.startswith(prefix):
        return None
    registry = a.read(root, REGISTRY)
    if registry.get("schema") != SCHEMA:
        return None
    row = next((row for row in registry.get("reviews") or [] if row.get("id") == reference[len(prefix):]), None)
    expected = facts(root, now)
    if not row or not expected or not a.timestamp(row.get("reviewed_at")):
        return None
    return row if {key: value for key, value in row.items() if key != "reviewed_at"} == expected else None


def review_requests(root, now=None):
    proof = facts(root, now)
    if not proof:
        return []
    registry = a.read(root, REGISTRY)
    reviews = list(registry.get("reviews") or [])
    if any(row.get("id") == proof["id"] for row in reviews):
        return []
    proof["reviewed_at"] = (now or datetime.now(timezone.utc)).isoformat().replace("+00:00", "Z")
    return [{"request_id": "REQ-" + proof["id"], "document": REGISTRY,
             "merge": {"schema": SCHEMA, "reviews": reviews + [proof]},
             "_autonomy_authority": a.WRITER_AUTHORITY}]
