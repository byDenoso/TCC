# Campaign Continuation Resolver V1 — Design

## Goal

Allow any NEXO chat/runtime surface to continue any canonical campaign without campaign-specific prompt logic, while preserving TOWER_V06 as the sole operational truth owner and preserving frozen scientific contracts.

## Constraints

- No new agent, scheduler, kernel, memory authority, or truth store.
- TOWER_V06 remains the sole operational truth owner.
- Drive/ATLAS remain projections only.
- Frozen scientific meaning cannot be changed by operational repair.
- Existing `task_id` dispatch stays compatible as fallback.
- TEST/RUN identity must remain canonical before dispatch.
- CAS/readback/provenance and RESULT→CLAIM/NEXT closure remain mandatory.

## Architecture

Extend the existing runtime with two small modules:

1. `CampaignContinuationResolver`: reconstructs a campaign frontier from canonical CAMPAIGN/TEST/RUN/RESULT entities. It derives active, recoverable, completed, ready, blocked and terminal states. It does not create a second persistent cursor; any cached frontier is derived.
2. `CapabilityExecutionResolver`: maps a READY TEST to an existing executable capability or to an explicit non-executable decision. Resolution order is REUSE → ADAPT → BUILD_MINIMAL_ADAPTER. V1 implements REUSE and explicit ADAPT eligibility only; automatic adapter creation remains gated by later engineering work.

The existing `register_test()` remains the identity ingress. The existing execution router remains the dispatch owner.

## Data model additions

TEST entities may declare:

- `required_capabilities: list[str]`
- `depends_on: list[str]`
- `execution_policy: "AUTO" | "MANUAL"` (default `AUTO`)

CAMPAIGN entities may declare:

- `execution_order: list[str]` for simple preregistered sequences
- `terminal_test_ids: list[str]`
- optional `max_active_parallel_tests`

Capability manifest entries may declare:

- `semantic_capabilities: list[str]`
- `adapter_for: list[str]`
- existing concrete `task_id`, backend, repository/workflow metadata

## Frontier semantics

For each TEST in the campaign:

- terminal: analytical/operational terminal state already closed;
- active: RUN is QUEUED/RUNNING/CHECKPOINTED and still valid;
- recoverable: RUN exists but is stale/failed in a contract-preserving way;
- ready: all `depends_on` tests are terminal-success/closed, no active RUN exists, and execution policy permits AUTO;
- blocked: dependency, external input, credential, or scientific-contract gate prevents safe execution.

A campaign is terminal only when all declared terminal tests are closed or an explicit campaign terminal status exists.

## Capability resolution

Resolution input: TEST + capability manifest.

1. Exact concrete capability/task mapping if `capability_id`/`task_id` is already present.
2. Semantic match: every `required_capabilities` item must be covered by one executable manifest entry or one declared compatible adapter.
3. If no compatible executable path exists, return `NEEDS_ADAPTER`; do not fabricate a task or mutate scientific fields.

Resolution output is a pure decision record containing `status`, `capability_id`, `task_id`, `backend`, and `reason`.

## Continuation flow

`CAMPAIGN → reconstruct frontier → recover active/recoverable RUN first → select READY TEST by canonical order/priority → resolve capability → register/reuse canonical TEST/RUN → dispatch via existing router → verify → persist/readback → close RESULT/CLAIM/NEXT → recompute frontier`.

## Global behavior

Any chat that can access NEXO/TOWER can continue a campaign by campaign id. Chat memory is not an authority and is not required.

## Safety and rollback

Feature flags:

- `CAMPAIGN_CONTINUATION_RESOLVER_V1 = SHADOW | ACTIVE | OFF`
- `CAPABILITY_EXECUTION_RESOLVER_V1 = SHADOW | ACTIVE | OFF`

`OFF` restores the current task-id-driven behavior. Existing entities and results remain valid because identity and result schemas are unchanged.

## Acceptance

1. Frontier is reconstructed deterministically from canonical entities without a persisted second cursor.
2. Existing active/recoverable RUN always wins over creation of a duplicate RUN.
3. A READY TEST with exact known capability resolves to the existing backend/task.
4. A READY TEST with only semantic requirements resolves to a compatible manifest entry when available.
5. Unknown capability returns `NEEDS_ADAPTER`, never an invented dispatch.
6. Existing task-id workflows remain unchanged.
7. Unit tests cover dependency ordering, active-run recovery preference, semantic capability resolution, unknown capability, and terminal campaign detection.
