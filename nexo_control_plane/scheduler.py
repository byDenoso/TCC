from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from .locks import acquireable
from .models import WorkDomain, WorkRecord, WorkStatus


@dataclass(frozen=True)
class CapacityProfile:
    max_global: int = 8
    science_target: int = 4
    engineering_target: int = 2
    verification_reserve: int = 1
    burst_reserve: int = 1
    max_per_lane: int = 3
    max_speculative: int = 2
    unverified_soft_limit: int = 8
    ready_queue_soft_limit: int = 20


@dataclass(frozen=True)
class SchedulerSnapshot:
    verification_backlog: int = 0
    ready_queue_count: int = 0
    engineering_backlog: int = 0


_ACTIVE = {
    WorkStatus.QUEUED,
    WorkStatus.DISPATCHED,
    WorkStatus.RUNNING,
    WorkStatus.CHECKPOINTED,
    WorkStatus.RESULT_AVAILABLE,
    WorkStatus.VERIFYING,
}

_PRIORITY = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}


def _sort_key(work: WorkRecord, snapshot: SchedulerSnapshot) -> tuple[int, int, int, str]:
    engineering_blocker = (
        work.domain == WorkDomain.ENGINEERING
        and snapshot.engineering_backlog > 0
        and work.priority.upper() == "CRITICAL"
    )
    return (
        0 if engineering_blocker else 1,
        1 if work.speculative else 0,
        _PRIORITY.get(work.priority.upper(), 9),
        work.work_id,
    )


def eligible_dispatches(
    ready: list[WorkRecord],
    active: list[WorkRecord],
    snapshot: SchedulerSnapshot,
    profile: CapacityProfile | None = None,
) -> list[WorkRecord]:
    profile = profile or CapacityProfile()
    active_jobs = [w for w in active if w.status in _ACTIVE]
    reserve = profile.verification_reserve if snapshot.verification_backlog > 0 else 0
    effective_limit = max(0, profile.max_global - reserve)

    lane_counts = Counter(w.lane_id for w in active_jobs if w.lane_id)
    domain_counts = Counter(w.domain for w in active_jobs)
    speculative_count = sum(1 for w in active_jobs if w.speculative)
    suppress_speculation = (
        snapshot.verification_backlog >= profile.unverified_soft_limit
        or snapshot.ready_queue_count >= profile.ready_queue_soft_limit
    )

    candidates = sorted(
        (w for w in ready if w.status == WorkStatus.READY),
        key=lambda w: _sort_key(w, snapshot),
    )
    burst_needed = any(w.priority.upper() == "CRITICAL" for w in candidates)
    dispatch_limit = effective_limit if burst_needed else max(0, effective_limit - profile.burst_reserve)
    slots = max(0, dispatch_limit - len(active_jobs))
    if slots == 0:
        return []

    chosen: list[WorkRecord] = []
    chosen_ids: set[str] = set()

    def can_take(candidate: WorkRecord) -> bool:
        nonlocal speculative_count
        if candidate.work_id in chosen_ids:
            return False
        if candidate.speculative and (
            suppress_speculation or speculative_count >= profile.max_speculative
        ):
            return False
        if candidate.lane_id and lane_counts[candidate.lane_id] >= profile.max_per_lane:
            return False
        return acquireable(candidate, active_jobs + chosen)

    def take(candidate: WorkRecord) -> bool:
        nonlocal speculative_count
        if len(chosen) >= slots or not can_take(candidate):
            return False
        chosen.append(candidate)
        chosen_ids.add(candidate.work_id)
        if candidate.lane_id:
            lane_counts[candidate.lane_id] += 1
        domain_counts[candidate.domain] += 1
        if candidate.speculative:
            speculative_count += 1
        return True

    # Phase 1: protect domain capacity targets while both domains have backlog.
    # Targets are floors, not hard caps; unused capacity is borrowed in phase 2.
    domain_targets = (
        (WorkDomain.ENGINEERING, profile.engineering_target),
        (WorkDomain.SCIENCE, profile.science_target),
    )
    for domain, target in domain_targets:
        deficit = max(0, target - domain_counts[domain])
        if deficit == 0:
            continue
        for candidate in candidates:
            if deficit == 0 or len(chosen) >= slots:
                break
            if candidate.domain == domain and take(candidate):
                deficit -= 1

    # Phase 2: fill the capacity made available above by global priority. The
    # dispatch_limit already holds the burst slot unused when there is no CRITICAL
    # candidate, so normal work cannot silently consume emergency capacity.
    for candidate in candidates:
        if len(chosen) >= slots:
            break
        take(candidate)

    return chosen
