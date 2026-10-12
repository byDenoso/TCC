"""Read-only, target-scoped throughput evidence for production planning.

This module never schedules or runs scientific work. It reports a 4x target
only when a canonical target entity, its SHA-256, an applied readback event,
and an explicit positive baseline interval are all verifiable in the supplied
Tower snapshot.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import statistics
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any


CONFIG_PATH = "evolution/production_throughput_target.json"
CONFIG_SCHEMA = "NEXO_PRODUCTION_THROUGHPUT_TARGET_V1"
GOAL_SCHEMA = "NEXO_PRODUCTION_THROUGHPUT_GOAL_V1"
METRIC_ID = "verified_scientific_tests_per_hour"
MULTIPLIER = 4
_HASH = re.compile(r"^(?:sha256:)?[0-9a-f]{64}$")
_TERMINAL = {"DONE", "VERIFIED"}
_EXCLUDED_CLASSES = {"SMOKE", "RETRY", "SEED", "SCAN", "DUPLICATE"}


def _instant(value: Any) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def _window(value: Any) -> tuple[datetime, datetime] | None:
    if not isinstance(value, dict):
        return None
    start, end = _instant(value.get("start")), _instant(value.get("end"))
    if start is None or end is None or end <= start:
        return None
    return start, end


def _load_events(root: Path) -> tuple[dict[str, dict], dict[tuple[str, str, int], dict]]:
    by_id: dict[str, dict] = {}
    by_entity_version: dict[tuple[str, str, int], dict] = {}
    event_root = root / "events"
    for path in sorted(event_root.rglob("*.json")) if event_root.is_dir() else []:
        try:
            event = json.loads(path.read_text(encoding="utf-8"))
            version = int(event.get("entity_version") or 0) if isinstance(event, dict) else 0
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            continue
        if not isinstance(event, dict):
            continue
        event_id = event.get("event_id")
        if isinstance(event_id, str) and event_id:
            by_id[event_id] = event
        if (event.get("readback") == "PASS" and event.get("material") is True
                and event.get("entity_kind") and event.get("entity_name") and version > 0):
            by_entity_version[(str(event["entity_kind"]), str(event["entity_name"]), version)] = event
    return by_id, by_entity_version


def _canonical_target(root: Path, config: Any, events: dict[str, dict]) -> tuple[dict | None, str | None]:
    if not isinstance(config, dict) or config.get("schema") != CONFIG_SCHEMA:
        return None, "LIVE_TARGET_NOT_CONFIGURED"
    target_ref = str(config.get("target_ref") or "")
    relative = PurePosixPath(target_ref)
    if (relative.is_absolute() or ".." in relative.parts or len(relative.parts) != 3
            or relative.parts[0] != "entities"
            or relative.parts[1] not in {"work", "campaign", "test_group"}
            or relative.suffix != ".json"):
        return None, "TARGET_REFERENCE_INVALID"
    target_path = root.joinpath(*relative.parts)
    try:
        resolved_root = root.resolve()
        resolved_target = target_path.resolve()
        if resolved_root not in resolved_target.parents:
            return None, "TARGET_REFERENCE_INVALID"
        raw = target_path.read_bytes()
        target = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError):
        return None, "TARGET_ENTITY_UNREADABLE"
    actual_sha = hashlib.sha256(raw).hexdigest()
    try:
        version = int(target.get("entity_version") or 0)
    except (AttributeError, TypeError, ValueError):
        return None, "TARGET_ENTITY_INVALID"
    if (not isinstance(target, dict) or str(target.get("id") or "") != target_path.stem
            or not _HASH.fullmatch(str(config.get("target_sha256") or ""))
            or str(config["target_sha256"]).removeprefix("sha256:") != actual_sha
            or config.get("target_entity_version") != version):
        return None, "TARGET_PROVENANCE_MISMATCH"
    goal = target.get("throughput_goal")
    if (not isinstance(goal, dict) or goal.get("schema") != GOAL_SCHEMA
            or goal.get("metric") != METRIC_ID or goal.get("multiplier") != MULTIPLIER):
        return None, "TARGET_GOAL_NOT_VERIFIED"
    event_id = str(config.get("target_verification_event_id") or "")
    event = events.get(event_id)
    expected_kind = relative.parts[1]
    if (not isinstance(event, dict) or event.get("entity_kind") != expected_kind
            or event.get("entity_name") != target_path.stem or event.get("entity_version") != version
            or event.get("readback") != "PASS" or event.get("material") is not True
            or not str(event.get("writer_role") or "").strip()):
        return None, "TARGET_READBACK_UNVERIFIED"
    return {"target_ref": target_ref, "target_sha256": actual_sha,
            "target_entity_version": version, "verification_event_id": event_id}, None


def _excluded(test: dict) -> str | None:
    kind = str(test.get("production_class") or test.get("test_class") or "").upper()
    if kind in _EXCLUDED_CLASSES:
        return kind
    flags = (("is_smoke", "SMOKE"), ("is_retry", "RETRY"), ("seed_only", "SEED"),
             ("seed_scan", "SCAN"), ("is_scan", "SCAN"), ("is_duplicate", "DUPLICATE"))
    for field, label in flags:
        if test.get(field) is True:
            return label
    if test.get("retry_of") or test.get("duplicate_of") or test.get("scan_of"):
        return "RETRY_OR_DUPLICATE"
    if test.get("contests_test_id") or str(test.get("verdict") or "").strip().upper() in {
            "CONTESTED", "CONTESTATION", "CONTESTANDO"}:
        return "CONTESTATION"
    return None


def _artifact_is_verified(root: Path, test: dict) -> bool:
    ref = str(test.get("artifact_ref") or test.get("result_artifact_ref") or "")
    ref = ref.removeprefix("TOWER_V06/")
    relative = PurePosixPath(ref)
    if (not ref or relative.is_absolute() or ".." in relative.parts
            or not relative.parts or relative.parts[0] != "runtime" or "artifacts" not in relative.parts):
        return False
    path = root.joinpath(*relative.parts)
    try:
        if root.resolve() not in path.resolve().parents:
            return False
        raw = path.read_bytes()
        artifact = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError):
        return False
    declared_hash = str(test.get("artifact_sha256") or "")
    return (
        bool(_HASH.fullmatch(declared_hash))
        and declared_hash.removeprefix("sha256:") == hashlib.sha256(raw).hexdigest()
        and isinstance(artifact, dict)
        and artifact.get("test_id") == test.get("id")
        and str(artifact.get("status") or "").upper() == "TERMINAL"
    )


def _verified_tests(root: Path, target_ref: str, window: tuple[datetime, datetime],
                    readbacks: dict[tuple[str, str, int], dict]) -> tuple[list[dict], dict[str, int]]:
    start, end = window
    folder = root / "entities" / "test"
    groups: dict[str, list[dict]] = {}
    for path in sorted(folder.glob("*.json")) if folder.is_dir() else []:
        try:
            test = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, json.JSONDecodeError):
            continue
        if isinstance(test, dict) and isinstance(test.get("id"), str):
            groups.setdefault(test["id"], []).append(test)
    counts = {"duplicate_ids": 0, "excluded_test_rows": 0, "missing_artifact_or_readback": 0,
              "execution_not_completed": 0}
    accepted: list[dict] = []
    for test_id, versions in groups.items():
        if len(versions) != 1:
            counts["duplicate_ids"] += 1
            continue
        test = versions[0]
        if str(test.get("target_ref") or "") != target_ref:
            continue
        exclusion = _excluded(test)
        if exclusion:
            counts["excluded_test_rows"] += 1
            continue
        if (str(test.get("status") or "").upper() not in _TERMINAL
                or not str(test.get("verdict") or "").strip()
                or not str(test.get("prereg_hash") or "").strip()):
            continue
        execution_phase = str(test.get("execution_phase") or "").upper()
        if execution_phase != "COMPLETED":
            counts["execution_not_completed"] += 1
            continue
        executed = _instant(test.get("executed_at"))
        if executed is None or not start <= executed <= end:
            continue
        try:
            version = int(test.get("entity_version") or 0)
        except (TypeError, ValueError):
            version = 0
        if (version <= 0 or not _artifact_is_verified(root, test)
                or ("test", test_id, version) not in readbacks):
            counts["missing_artifact_or_readback"] += 1
            continue
        accepted.append(test)
    return accepted, counts


def _hours(window: tuple[datetime, datetime]) -> float:
    return (window[1] - window[0]).total_seconds() / 3600


def _derived_observations(tests: list[dict]) -> dict[str, dict]:
    eligible = [test for test in tests if (
        (test.get("readiness") if isinstance(test.get("readiness"), dict) else {}).get("eligible") is True
        or test.get("eligible") is True
    )]
    interventions = [test.get("human_intervention") for test in eligible]
    if interventions and all(type(value) is bool for value in interventions):
        autonomy = {"value": round(sum(value is False for value in interventions) / len(interventions), 3),
                    "numerator": sum(value is False for value in interventions), "denominator": len(interventions),
                    "status": "MEASURED"}
    else:
        autonomy = {"value": None, "numerator": None, "denominator": len(eligible),
                    "status": "INTERVENTION_METADATA_UNVERIFIED"}

    durations = []
    recovery_times = []
    for test in tests:
        started = _instant(test.get("started_at") or ((test.get("execution") or {}).get("started_at")))
        executed = _instant(test.get("executed_at"))
        if started is not None and executed is not None and executed >= started:
            durations.append((executed - started).total_seconds() / 3600)
        recovered = _instant(test.get("recovered_at"))
        recovery_start = _instant(test.get("recovery_started_at"))
        if recovery_start is not None and recovered is not None and recovered >= recovery_start:
            recovery_times.append((recovered - recovery_start).total_seconds() / 3600)

    def median(values: list[float]) -> dict:
        return {"value": round(statistics.median(values), 3), "samples": len(values), "unit": "hours"} if values else {
            "value": None, "samples": 0, "unit": "hours", "status": "UNMEASURED"}

    return {"autonomy_fraction": autonomy, "median_recovery_time": median(recovery_times),
            "median_observed_duration": median(durations)}


def evaluate_production_target(root: str | Path, *, current_window: dict) -> dict:
    """Measure one verified target against an explicit current interval.

    A missing or non-positive baseline stays unknown. The caller cannot select
    a global target or manufacture a baseline count in configuration.
    """
    root = Path(root)
    current = _window(current_window)
    if current is None:
        raise ValueError("CURRENT_WINDOW_MUST_BE_EXPLICIT_AND_VALID")
    events, readbacks = _load_events(root)
    config_path = root / CONFIG_PATH
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError):
        return {"schema": "NEXO_PRODUCTION_THROUGHPUT_V1", "status": "BLOCKED_LIVE_TARGET_UNVERIFIED",
                "metric": METRIC_ID, "multiplier": MULTIPLIER,
                "blockers": ["NO_VERIFIABLE_LIVE_THROUGHPUT_TARGET", "BASELINE_INTERVAL_NOT_CONFIGURED"],
                "baseline": {"value": None, "status": "UNVERIFIED"},
                "observed": {"value": None, "status": "UNVERIFIED"},
                "scope": None}
    baseline = _window(config.get("baseline_window")) if isinstance(config, dict) else None
    if baseline is None:
        return {"schema": "NEXO_PRODUCTION_THROUGHPUT_V1", "status": "BLOCKED_BASELINE_INTERVAL_UNVERIFIED",
                "metric": METRIC_ID, "multiplier": MULTIPLIER,
                "blockers": ["EXPLICIT_REAL_BASELINE_INTERVAL_REQUIRED"],
                "baseline": {"value": None, "status": "UNVERIFIED"},
                "observed": {"value": None, "status": "UNVERIFIED"},
                "scope": config.get("target_ref") if isinstance(config, dict) else None}
    if baseline[1] > current[0]:
        return {"schema": "NEXO_PRODUCTION_THROUGHPUT_V1", "status": "BLOCKED_BASELINE_INTERVAL_UNVERIFIED",
                "metric": METRIC_ID, "multiplier": MULTIPLIER,
                "blockers": ["BASELINE_MUST_PRECEDE_CURRENT_WINDOW"],
                "baseline": {"value": None, "status": "UNVERIFIED"},
                "observed": {"value": None, "status": "UNVERIFIED"},
                "scope": config.get("target_ref") if isinstance(config, dict) else None}
    target, blocker = _canonical_target(root, config, events)
    if blocker:
        return {"schema": "NEXO_PRODUCTION_THROUGHPUT_V1", "status": "BLOCKED_TARGET_PROVENANCE_UNVERIFIED",
                "metric": METRIC_ID, "multiplier": MULTIPLIER, "blockers": [blocker],
                "baseline": {"value": None, "status": "UNVERIFIED"},
                "observed": {"value": None, "status": "UNVERIFIED"},
                "scope": config.get("target_ref") if isinstance(config, dict) else None}
    baseline_tests, baseline_quality = _verified_tests(root, target["target_ref"], baseline, readbacks)
    current_tests, current_quality = _verified_tests(root, target["target_ref"], current, readbacks)
    baseline_hours, current_hours = _hours(baseline), _hours(current)
    baseline_rate = len(baseline_tests) / baseline_hours
    current_rate = len(current_tests) / current_hours
    if baseline_rate <= 0:
        return {"schema": "NEXO_PRODUCTION_THROUGHPUT_V1", "status": "BLOCKED_BASELINE_NOT_POSITIVE",
                "metric": METRIC_ID, "multiplier": MULTIPLIER, "blockers": ["BASELINE_HAS_NO_VERIFIED_COMPLETED_TESTS"],
                "scope": target, "baseline": {"count": len(baseline_tests), "hours": baseline_hours,
                                                "value": 0.0, "status": "NOT_POSITIVE", "quality": baseline_quality},
                "observed": {"count": len(current_tests), "hours": current_hours, "value": current_rate,
                             "quality": current_quality}}
    observations = _derived_observations(current_tests)
    target_rate = baseline_rate * MULTIPLIER
    minimum_count = math.ceil(target_rate * current_hours)
    return {
        "schema": "NEXO_PRODUCTION_THROUGHPUT_V1", "status": "MEASURED_TARGET",
        "metric": METRIC_ID, "multiplier": MULTIPLIER, "scope": target,
        "baseline": {"count": len(baseline_tests), "hours": baseline_hours, "value": baseline_rate,
                     "interval": {"start": config["baseline_window"]["start"], "end": config["baseline_window"]["end"]},
                     "quality": baseline_quality},
        "observed": {"count": len(current_tests), "hours": current_hours, "value": current_rate,
                     "interval": {"start": current_window["start"], "end": current_window["end"]},
                     "quality": current_quality},
        "target": {"value": target_rate, "minimum_count_for_current_window": minimum_count,
                   "unit": "verified_scientific_tests_per_hour"},
        "observed_multiplier": round(current_rate / baseline_rate, 3),
        "target_met": current_rate >= target_rate,
        "autonomy": observations["autonomy_fraction"],
        "median_recovery_time": observations["median_recovery_time"],
        "median_observed_duration": observations["median_observed_duration"],
        "claim_scope": "TARGET_SCOPED_MEASUREMENT; DOES_NOT_AUTHORIZE_CAPACITY_OR_SCHEDULER_CHANGES",
    }
