# NEXO Control Plane v0.3 — Shadow Design

## Goal

Raise NEXO throughput without allowing role drift, duplicate work, global blocking, or scientific truth to leak into the execution backend.

## Operating principle

NEXO remains a five-role cognitive system. `Core` is not a sixth conversational agent. It is deterministic control-plane policy: queue state, dependency resolution, scoped locks, capacity budgets, reconciliation, and engineering-work creation from typed failures/capability gaps.

The Research Advisor remains science-only. It may identify a capability gap, but it does not author code work directly. Core converts typed capability gaps and runtime failures into ENGINEERING work. The Executor is one logical authority but not one worker; it routes work to independent backends and tracks it asynchronously.

## Safety boundary

1. Existing five ChatGPT automations remain active until shadow verification passes.
2. GitHub Actions may be a subordinate compute/engineering backend, never a scientific truth owner.
3. A GitHub result is not canonical until verification plus Drive persistence/readback succeeds.
4. No routine compute uses a global lock. Locks are scoped to resource keys.
5. Unknown states, invalid transitions, ambiguous ownership, or missing evidence fail closed.
6. No secrets, user data, canonical SSOT payloads, or private prompts are committed to the public TCC repository.

## Role boundaries

### Advisor
- Owns scientific prioritization and scientific test proposals.
- May emit `CAPABILITY_GAP` events when science is blocked by infrastructure.
- Must not create/patch engineering implementation directly.

### Emergent
- May propose scientific hypotheses and procedural hypotheses.
- A procedural hypothesis is not executable engineering work until Core converts it into a typed ENGINEERING work item.

### Core
- Deterministic, not an LLM role.
- Owns state transition validation, dependency gates, lock resolution, resource/capacity allocation, reconciliation, and typed conversion of runtime/capability failures into ENGINEERING work.
- Does not interpret scientific meaning.

### Executor
- Owns dispatch, run tracking, resume/retry choice, result ingestion, and handoff to verification.
- Does not need to remain blocked while external work runs.
- Routes SCIENCE heavy compute and ENGINEERING code/runtime work to separate worker classes.

### Learner
- Learns OBJECT knowledge only from verified scientific evidence.
- Learns PROCEDURAL knowledge only from verified engineering/runtime evidence.
- Never learns from raw GitHub stdout or an unverified external result.

### Daily
- Reports only material deltas, blockers, decisions, and discoveries to the user.
- Does not dump individual job noise.

## Work domains

`SCIENCE`, `ENGINEERING`, `OLYMPUS`, `SYSTEM`.

## Work states

The control plane recognizes the existing terminal states plus asynchronous execution states:

- `PENDING`
- `READY`
- `QUEUED`
- `DISPATCHED`
- `RUNNING`
- `CHECKPOINTED`
- `RESULT_AVAILABLE`
- `VERIFYING`
- `VERIFIED`
- `WAIT_DEPENDENCY`
- `BLOCKED`
- `FAILED`
- `INCONCLUSIVE`
- `SUPERSEDED`
- `DONE`

Routine transition validation is strict. `DONE` is only reachable from `VERIFIED` for externally executed material work. Existing legacy DONE rows remain readable and are not retroactively invalidated.

## WORK compatibility extension

Existing columns A:R remain unchanged. Use currently unused S:Z columns:

- S `domain`
- T `execution_backend`
- U `external_run_id`
- V `dependency_ids`
- W `resource_keys`
- X `attempt`
- Y `checkpoint_ref`
- Z `verification_status`

`result_ref` remains the canonical place for artifact references and result hashes, preserving backward compatibility.

## EVENTS compatibility extension

Existing columns A:K remain unchanged. Add:

- L `correlation_id`
- M `source_role`
- N `target_role`
- O `state_from`
- P `state_to`
- Q `payload_ref`
- R `resource_key`
- S `severity`
- T `dedupe_key`
- U `acknowledged_at`

## Scoped locks

Resource locks are strings such as:

- `science:T-DE042`
- `repo:TCC:portable_camb`
- `workflow:nested`
- `artifact:T-DE042`

Two items conflict only when their resource-key sets intersect. A global structural lock is reserved for canonical schema/governance migrations, not routine execution.

## Dependency model

A work item is executable only when every `dependency_id` is terminal-success (`VERIFIED` or `DONE`). Missing dependencies fail closed as `WAIT_DEPENDENCY`; failed/superseded dependencies block descendants unless an explicit replacement dependency is written.

## Scheduler and backpressure

Initial capacity profile:

- global active external jobs: 8
- SCIENCE target capacity: 4
- ENGINEERING target capacity: 2
- verification reserve: 1
- burst/blocker reserve: 1
- per-lane active jobs: 3
- speculative jobs: 2
- unverified-result backlog soft limit: 8
- ready-queue soft limit: 20

Unused domain capacity may be borrowed, but verification and engineering blocker capacity is protected when those backlogs are non-zero. The burst/blocker slot is deliberately held unused during ordinary work, so normal external dispatch tops out at 7. A CRITICAL ready item may consume the eighth slot. If verification backlog is non-zero, the verification reserve further reduces ordinary dispatch capacity until verification catches up.

When verification backlog exceeds the soft limit, new speculative dispatch stops. When the ready queue exceeds the soft limit, Emergent exploration is throttled. This is backpressure, not failure.

## Routing

- heavy SCIENCE -> `GITHUB_SCIENCE`
- code/runtime/CI ENGINEERING -> `GITHUB_ENGINEERING`
- lightweight/internal work -> `LOCAL`
- OLYMPUS remains local unless separately authorized
- unresolved dependency -> `WAIT_DEPENDENCY`

The router is deterministic from domain, runtime requirement, and typed work metadata.

## Execution envelope

Every external dispatch has a frozen envelope containing at least:

- work/test ID
- correlation ID
- domain
- lane/thread
- backend
- task type
- commit SHA or source revision
- configuration/input hash
- seed when stochastic
- checkpoint policy
- attempt number
- resource keys
- acceptance/evidence requirements

The backend executes the contract; it does not reinterpret it.

## Result envelope

External result ingestion requires:

- work/test ID
- correlation ID
- backend run ID
- external status
- exit code
- artifact reference
- checkpoint reference if any
- runtime seconds
- result hash
- source revision/commit SHA

A complete run may move to `RESULT_AVAILABLE`; it may not move to `VERIFIED` or `DONE` without evidence verification.

## Reconciliation

Core reconciles SSOT state against external run truth. Typical repairs:

- SSOT RUNNING + external COMPLETED -> RESULT_AVAILABLE
- SSOT DISPATCHED + no resolvable external run -> typed DISPATCH failure/block
- SSOT RUNNING + external FAILED + checkpoint -> CHECKPOINTED/eligible resume
- duplicate external run IDs for the same idempotency key -> block and surface conflict

Reconciliation is idempotent and emits deduplicated EVENTS.

## Engineering generation

Core may create ENGINEERING work only from typed inputs:

- `CAPABILITY_GAP`
- `RUNTIME_DEFECT`
- `CI_FAILURE`
- `CHECKPOINT_FAILURE`
- `ARTIFACT_CORRUPTION`
- `PERFORMANCE_REGRESSION`
- `CONNECTOR_FAILURE`
- `PROCEDURAL_HYPOTHESIS` (bounded improvement candidate; never direct code authority)

Engineering work that can alter likelihood/model/prior/scientific numerics requires a SCIENCE review gate before scientific reuse.

## Shadow phase acceptance

Before any live prompt cutover:

1. state-transition tests pass;
2. scoped-lock tests prove unrelated work proceeds;
3. dependency tests prove blocked work does not dispatch;
4. scheduler tests prove domain reserves and backpressure;
5. role-policy tests prove Advisor cannot create engineering work directly;
6. result-gate tests prove unverified external results cannot teach or close work;
7. reconciliation tests prove idempotent repair;
8. CI passes on the feature branch/PR;
9. SSOT schema extension is readback-verified;
10. only then may automation prompts be updated, with rollback by restoring previous prompts.
