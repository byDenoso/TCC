# C01 offline cache feasibility protocol

Protocol version: `C01_OFFLINE_FEASIBILITY_PROTOCOL_V1`
Frozen at: `2026-10-02T07:24:13Z`
Classification: `PERFORMANCE_BENCHMARK` (not scientific evidence, an activation mandate, or live-promotion evidence)

## Scope and authority

Use the frozen private input `private-plan/NEXO_TOWER_0522.json` after the final Writer, D01, and LF-normalization freeze. Materialize it into an isolated temporary directory and never write the input bundle or publish a Tower revision. Run the actual `scientific_integrity.readiness(root, test)` implementation over the baseline corpus selected by the baseline replay owner. The existing Pantheon recipe catalog is a read-only input.

Do not install a C01 config, approval registry, analysis plan, monitor, selection, or reservation to make a candidate path reachable. Do not fabricate access scopes, authorization revisions, monitor health, candidate units, independent clusters, or missing strata. When actual trusted runtime inputs are absent, record the production candidate path as blocked and do not substitute synthetic metadata. The exact production no-argument evaluator may be measured as the current `OFF` path, but this is not a candidate-arm result.

## Frozen corpus and strata

The denominator is every canonical test entity included by the frozen baseline replay. Report its count and context-construction coverage; never print test IDs, intent IDs, entity content, or per-row timing in the sanitized aggregate. The only reportable corpus strata are:

`missing_dependency`, `hash_mismatch`, `public`, `private`, `context_changed`, `conflict`, `timeout`, and `partial`.

Derive each stratum only from current Tower content and observed real readiness results. `public` and `private` are the performance strata; the remaining names are coverage strata. If a stratum is absent or cannot be established from the frozen corpus, report it as absent or unknown. Do not synthesize rows to fill it. Cluster identity/independence is `UNKNOWN` unless the frozen corpus itself supplies a justified basis; repeated evaluations of one test, baseline controls, and technical repeats never add independent units.

## Pairing, order, and estimator

For every row for which a valid production context can be built from actual trusted Tower inputs, run exactly one corrected-baseline evaluation and one unique cold-cache candidate evaluation. The candidate cache is empty at the start of that row; the candidate path includes metadata derivation, monitor/store verification, full context/key construction and hashing, cache lookup/miss, the real baseline evaluation on miss, and cache insertion. Do not prewarm the cache for the primary comparison. If the context cannot be built or runtime authority fails, do not count a candidate pair; record a sanitized blocker and preserve baseline behavior.

Counterbalance arm order deterministically without emitting identities: for local intent key `k`, compute `SHA256(k)` and run baseline first when the first digest byte is even, candidate first when it is odd. Each arm is measured once per eligible pair. The primary paired statistic is the within-row natural-log ratio of candidate to baseline filesystem read calls. Compute the paired sample variance from those log ratios only when a justified independent cluster definition exists. Otherwise report the finite-corpus descriptive distribution and mark inferential variance/independence unknown. Do not install this offline variance into a LIVE plan.

Compute candidate/baseline byte and full elapsed-time ratios as diagnostics. Full elapsed time starts before production metadata/controller work and ends after cache insertion/readback; it includes all context/key/monitor/store/hash work that actually runs. Candidate result equality is exact on the canonical readiness result. Any mismatch, measurement gap, or invocation error fails closed to baseline and prevents a performance pass.

Warm exact-context reuse may be measured once as a separate descriptive diagnostic after the cold comparison. Label it `WARM_REUSE_DESCRIPTIVE`; do not combine it with the cold estimator, count it as a candidate unit, or treat it as a production exposure.

## Metrics and decision rules

Instrument `Path.read_bytes` and `Path.read_text` around the entire measured arm and include `ReadinessCacheContext.from_runtime` construction metrics. Report total filesystem read calls, bytes, and elapsed time for baseline and cold candidate paths. Any uninstrumented input read or missing metric invalidates that arm; do not claim savings from readiness-call-only measurements.

Performance feasibility thresholds retain the C01 policy: one-sided 95% upper confidence bound for the paired read-call ratio must be at most `0.85`, and candidate p95 elapsed-time ratio must be at most `1.10`. Statistical error policy remains 95% confidence with maximum one-sided binomial error upper bound `0.005`. These are gate definitions, not expected outcomes. If context/authority prevents an actual production candidate pair, report `NOT_ESTIMABLE` rather than a pass or imputed ratio.

LIVE policy remains separate: deterministic 10% intent assignment; no more than 100 actually evaluated unique candidate units per day and 2,800 total; at least 600 actually evaluated candidate units across 7–28 days. Controls, repeats, reservations, replay rows, and warm hits do not count. A zero-error sample needs at least 598 independent evaluated candidate units to make the one-sided 95% binomial upper bound no greater than `0.005`; dependence must be addressed before claiming that condition. Promotion also requires the frozen paired performance gates, p95 latency gate, complete required coverage/monitor evidence, and verified readback. Insufficient evidence or a failed gate leaves the baseline selected.

## Outputs

Keep row-level results, exact corpus identities, raw Tower content, and raw monitor/registry material in a private evidence artifact outside public projections. The sanitized aggregate may contain source and bundle hashes, module/config hashes, corpus and coverage counts, total/aggregate metrics, observed gate result, and a fixed blocker code. It must omit test/intent/entity IDs, private Tower records, approval paths/references, registry contents, and row-level values. Label all offline paired estimates `PLANNING_EVIDENCE_ONLY`; they do not establish live exposure, independent-unit counts, a frozen production sample plan, or permission to promote.
