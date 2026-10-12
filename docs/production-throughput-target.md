# Target-scoped production throughput evidence

## Current contract inventory

- `docs/autonomy-metrics-v2.md` describes operational summaries of recorded tests. Its window result count and legacy proxies do not establish a target-specific production throughput baseline.
- `docs/nexo-autonomy-preparation.md` describes the separate, fixed `NEXO_CAPACITY_STABILITY_V1` capacity progression. It is a guarded capacity policy, not a verified production-throughput goal.
- `gpt/skills/nexo-master-router-0.5.0.md` and `gpt/skills/nexo-workspace/SKILL.md` describe historical 6/24 router probes as observability probes, not quotas or targets.

This repository snapshot contains no verified, target-specific 4x production goal or explicit real baseline interval. The implementation therefore supports such a target but returns a specific blocked status until a live canonical target and baseline are supplied and verified. It does not treat a missing target, the supplied user snapshots, or an empty interval as a useful global baseline.

## Runtime configuration contract

The evaluator reads `evolution/production_throughput_target.json` from a supplied Tower snapshot. Configuration has this shape:

```json
{
  "schema": "NEXO_PRODUCTION_THROUGHPUT_TARGET_V1",
  "target_ref": "entities/work/WORK-ID.json",
  "target_sha256": "<sha256 of the exact canonical target bytes>",
  "target_entity_version": 7,
  "target_verification_event_id": "<canonical material event with readback PASS>",
  "baseline_window": {
    "start": "<explicit UTC start>",
    "end": "<explicit UTC end>"
  }
}
```

The referenced canonical `WORK`, `CAMPAIGN`, or `TEST_GROUP` must itself contain `throughput_goal` with schema `NEXO_PRODUCTION_THROUGHPUT_GOAL_V1`, metric `verified_scientific_tests_per_hour`, and multiplier `4`. The evaluator checks the exact target bytes/hash/version and a matching material readback event. The baseline interval must be explicit, positive in duration, and end no later than the separately supplied current interval begins. Each counted test must reference that exact target and have a distinct canonical ID, terminal scientific status and verdict, preregistration hash, `execution_phase: COMPLETED`, an artifact whose bytes match its recorded SHA and test ID, and a matching material test-version readback event. Smokes, retries, seeds, scans, duplicates, contests, incomplete executions, and missing artifact/readback proof are excluded and reported in quality counts.

The evaluator is read-only. It measures autonomy only when eligibility and human-intervention metadata are explicit, and reports recovery time and observed duration only where both timestamp endpoints are present and valid. It neither creates a baseline nor runs science, schedules work, or authorizes capacity changes. A positive verified baseline is required before a 4x comparison can be made.

## Remaining live evidence

Populate the target and baseline from an authorized live snapshot, preserving exact source provenance and readback. Then provide a distinct explicit current interval and run the evaluator over that snapshot. Until those steps succeed, report `BLOCKED_LIVE_TARGET_UNVERIFIED`, `BLOCKED_BASELINE_INTERVAL_UNVERIFIED`, or `BLOCKED_BASELINE_NOT_POSITIVE` as applicable; do not claim a production 4x gain. The user's partial observations from 2026-10-11 20:50–21:18 have no canonical RUN/RESULT receipt here and are not treated as either zero science or a representative baseline.
