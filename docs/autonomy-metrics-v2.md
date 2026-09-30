# Operational metrics contract

`evolution.autonomy` now publishes `schema_version: AUTONOMY_METRICS_V2`.
The historical payload name does not establish unattended operation. Consumers
should prefer `metrics` and use the supplied numerators, denominators and scopes.
They must not reconstruct these metrics from projected public tests: that view can
add execution and observation timestamps absent from the canonical source.

`computed_at`, `window_start` and `window_end` are UTC ISO timestamps. The window is
inclusive at both ends. Future, missing and invalid execution times are excluded.
Naive timestamps are interpreted as UTC. `evolution_status(now=...)` supplies the
same clock to these metrics.
Public projections pass their explicit `generated_at` clock to the metrics, so
rebuilding the same state at the same supplied time yields identical bytes.
When `generated_at` is omitted, the projection captures UTC once and records that
clock in its manifest and metrics. Invalid supplied timestamps are rejected;
naive timestamps are interpreted as UTC.
The projection fingerprint excludes only the V2 observation timestamps
`computed_at`, `window_start` and `window_end`. Values, cohort counts, definitions,
coverage and buckets remain hashed, including changes when results leave the window.

Every metric contains `value`, `numerator`, `denominator`, `scope`, `definition`
and `unit`. Ratios are rounded to three decimals and are `null` for an empty
denominator. `scope: window` means non-contestation tests with a recorded verdict
and an execution timestamp in the window. `scope: all_tests` is stock across the
supplied records, subject to the specific definition below.

| Metric | Unit | Definition |
| --- | --- | --- |
| `results` | count | Number of window results; denominator is not applicable (`null`) |
| `execution_record_share` | ratio | Window results with truthy `family_id` or `execution`; metadata proxy only |
| `decisive_rate` | ratio | Window results labeled `PROMOTED`, `PROMOVIDO`, `REJECTED`, `REJEITADO`, `CONFIRMED` or `REFUTED`; no inference of scientific certainty |
| `non_inconclusive_rate` | ratio | Any non-empty window verdict except `INCONCLUSIVE`/`INCONCLUSIVO`, including unknown labels; definition ID `LEGACY_NON_INCONCLUSIVE` |
| `median_hours_to_result` | hours | Median from the first present timestamp in `created_at_effective`, `created_at`, `first_observed_at` to execution, using valid non-negative durations; numerator and denominator are not applicable (`null`) |
| `legacy_median_hours_to_result` | hours | Original observation-based median, ignoring `created_at`; definition ID `LEGACY_OBSERVATION_LATENCY` |
| `positive_review_closure` | ratio | Non-contestation positives (`PROMOTED`/`PROMOVIDO`/`SUPPORTED`) with review state exactly `CONFIRMED` or `REFUTED` over all non-contestation positives; stock, including refutations |
| `failure_result_coverage` | ratio | Records with `runtime_failure_count > 0` and any verdict over records with failures, including contestations; no claim about ordering or causality |
| `blocked_share` | ratio | Uppercased status `BLOCKED*` over `READY` + `BLOCKED*`, including contestations; does not classify a block as false |

Latency additionally publishes `sample_count` and
`coverage: {value, numerator, denominator}`. Coverage divides valid durations by
all window results; a median based on few records must not imply full coverage.
Missing timestamps remain unmeasured and are not synthesized.
The canonical median measures time from the recorded test creation/observation,
not time since an idea. Its creation timestamp fallback fixes missing measurements
for canonical records that contain only `created_at`. The legacy median retains
its own sample count and coverage to make the difference explicit.

Audit buckets:

- `result_verdicts`: uppercase verdict to count
- `result_categories`: `{decisive, inconclusive, other}`, a disjoint partition;
  `CONTESTED`, `SUPPORTED`, and unknown labels are `other`
- `result_execution_records`: `{execution_or_family, neither}`
- `latency_coverage`: `{measured, missing_start, invalid_start, start_after_execution}`
- `latency_start_sources`: `{created_at_effective, created_at, first_observed_at, missing}`;
  counts selected source fields, including any invalid durations
- `positive_review_states`: recorded review state to count, with `MISSING` for absent values
- `queue_statuses`: `{ready, blocked, other}` across all records
- `failure_results`: `{with_verdict, without_verdict}` among records with failures

Legacy top-level numbers retain their definitions, apart from excluding future
execution timestamps. `legacy_aliases` maps each top-level key to its metric:
`robot_share` → `execution_record_share`, `decisive_rate` and `info_per_test` →
`non_inconclusive_rate`, `contest_closure` → `positive_review_closure`,
`recovery_rate` → `failure_result_coverage`, and `false_block_share` →
`blocked_share`. `results` keeps its name. Top-level `median_hours_to_result` maps
to `legacy_median_hours_to_result`, preserving the old observation-only inputs.
In particular, legacy top-level `decisive_rate` is intentionally different from
canonical `metrics.decisive_rate` when other verdict labels are present.

This projection only reads records. It does not change results, verdicts, review
states, execution records, or scientific decisions.
