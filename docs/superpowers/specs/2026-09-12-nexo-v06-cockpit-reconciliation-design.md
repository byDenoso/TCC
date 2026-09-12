# NEXO v0.6 Cockpit Reconciliation Design

## Goal

Reconcile the post-migration NEXO v0.6 system around a single canonical frontend, `nexo-atlas-cockpit`, without changing the cockpit's visual layout while it is still being finished. The cockpit must consume derived, read-only views from the NEXO backend and must never depend directly on raw GitHub Tower paths, Google Drive paths, legacy Sheets, workflow internals, or storage credentials.

## Current State

Canonical state is active in `byDenoso/NEXO-Obsidian-Vault@main:TOWER_V06` with GitHub Tower as truth owner. The five active roles are DAILY, ADVISOR, EXECUTOR, LEARNER and EMERGENT. Role bootstraps and queues are materialized and mutation writes flow through the mutation inbox. Legacy Sheets/Tower remain read-only first-touch provenance. Heavy artifacts remain in Drive.

Observed reconciliation debt:

- Three frontend surfaces still exist in production: `nexo-atlas-cockpit`, `nexo-one`, and `nexo-atlas-control-tower`.
- Many probe/test/preview Vercel projects remain from previous architecture experiments, including retired Neon-era projects.
- The View API remains a library reader, not yet the single HTTP contract consumed by the cockpit.
- The role bootstrap contract exists, but a director/cockpit bootstrap does not.
- `snapshot/latest.json` does not currently provide a meaningful event cursor for all consumers.
- The capability registry is intentionally small and still exposes only a few proven capabilities.
- Legacy fallback is still enabled because not all active entities have been hydrated.

## Canonical Roles After Reconciliation

### NEXO Atlas Cockpit

`nexo-atlas-cockpit` becomes the only canonical frontend.

Responsibilities:
- visualize current state;
- navigate programs, campaigns, work, blockers, agents, graphs and artifacts;
- surface material deltas and Director decisions;
- remain read-only for the first reconciliation release.

Non-responsibilities:
- no direct Tower file lookup;
- no direct Drive lookup;
- no direct Sheets lookup;
- no workflow dispatch logic;
- no storage tokens in the browser;
- no arbitrary JSON mutation.

### NEXO Runtime / Backend

Owns operational interpretation and all storage/provider resolution.

Responsibilities:
- materialize derived views;
- calculate role eligibility;
- resolve artifacts and capabilities;
- expose read-only View API routes;
- own event cursors;
- centralize typed mutations and readback;
- reconcile first-touch legacy state.

### GitHub Tower v0.6

Single declarative truth owner.

Responsibilities:
- CONTROL;
- canonical entities;
- material events;
- receipts;
- derived indexes/views;
- manifests;
- snapshots;
- graph catalog.

### Drive

Heavy storage only.

Responsibilities:
- datasets;
- chains;
- large scientific outputs;
- figures/PDFs;
- migration archives;
- heavyweight artifacts referenced by stable artifact IDs.

### Legacy Sheets / Legacy PEER Tower

Read-only provenance and first-touch hydration only. They must not be consulted in the cockpit normal read path and must never receive new writes.

## Frontend Canonicalization

The system records the following frontend roles:

- `nexo-atlas-cockpit`: `CANONICAL`
- `nexo-one`: `ROLLBACK_ONLY`
- `nexo-atlas-control-tower`: `ROLLBACK_ONLY`
- historical probe/preview projects: `ARCHIVE_CANDIDATE` or `DELETE_CANDIDATE`
- all Neon-era projects: `RETIRED_DO_NOT_USE`

No legacy project is deleted as part of the first reconciliation release. Deletion is a later cleanup after the cockpit read path passes end-to-end canaries.

## Cockpit Read Contract

The cockpit consumes only backend-owned read routes:

- `GET /api/snapshot`
- `GET /api/director`
- `GET /api/programs`
- `GET /api/campaigns`
- `GET /api/work`
- `GET /api/blockers`
- `GET /api/agents`
- `GET /api/graphs`
- `GET /api/graphs/:graph_id`
- `GET /api/artifacts/:artifact_id`
- `GET /api/health`

The backend may resolve these routes from GitHub Tower, Drive manifests, runtime/provider state, or generated views. That implementation detail is invisible to the cockpit.

The browser must never receive:
- GitHub write credentials;
- Drive credentials;
- legacy Sheets IDs as runtime routing data;
- raw internal provider tokens;
- mutable repository paths as frontend contracts.

## Director Bootstrap

Add a derived director view as the primary cockpit landing payload. Recommended file-backed materialization:

`TOWER_V06/bootstrap/director.json`

Required fields:

```json
{
  "schema_version": "0.6",
  "generated_at": "ISO-8601",
  "control": {},
  "health": {},
  "counts": {},
  "material_changes": [],
  "director_decisions": [],
  "global_blockers": [],
  "campaigns": [],
  "active_work": [],
  "agents": [],
  "graph_ids": [],
  "event_cursor": "EVT-..."
}
```

The director bootstrap is derived. It is never a separate truth owner.

## Event Cursor Contract

Each material event has a stable `event_id` and sortable timestamp/sequence metadata. Materialized consumers receive the most recent cursor they include.

Rules:
- cursor is monotonic for a materialized view;
- consumer can request or compare deltas after the cursor;
- no consumer should rescan the entire event tree to determine freshness;
- null cursor is allowed only for an empty system with zero material events, not for the current v0.6 state.

The first implementation may compute a global material cursor from the latest canonical material event and include it in all derived bootstraps. Per-role cursors can follow later if needed.

## Capability Registry Contract

Capabilities are the only execution-facing abstraction consumed by agents or future cockpit actions.

Each capability record must support:

```json
{
  "capability_id": "example_v1",
  "status": "ACTIVE|PROVEN|DISABLED|BLOCKED",
  "roles": ["EXECUTOR"],
  "backend": "github_dispatch|local|nexo_agent_api",
  "task_id": "stable-task-id",
  "input_contract": {},
  "required_outputs": [],
  "acceptance": {},
  "compute_class": "LIGHT|MEDIUM|HEAVY",
  "timeout_class": "SHORT|STANDARD|LONG"
}
```

Agents must not depend on workflow names, branches, request-file mechanics or provider-specific paths when a capability exists.

## Automation Reconciliation

The five active schedules remain:

- Daily `:00`
- Executor `:05`
- Learner `:20`
- Emergent `:35`
- Advisor `:50`

These are trigger offsets, not a forced serial pipeline.

Semantic handoffs are:

`Emergent -> Advisor -> Executor -> Learner -> Daily`

Rules:
- handoffs are typed entities/events, not prose assumptions;
- one blocked lane never stalls unrelated lanes;
- Executor queue membership is mechanically derived;
- READY is insufficient for Executor eligibility;
- Daily only surfaces material Director-facing deltas;
- role prompts must not reproduce storage, CAS, event-path or view-refresh mechanics.

## Artifact Resolution

The cockpit and agents use stable artifact IDs only.

Example:

`ART::CAMP-DDE::RUN-127::RESULT`

The backend resolves storage location and metadata. The artifact response may contain a temporary access URL or metadata appropriate for the authenticated user, but storage credentials remain server-side.

## Read-Only First Release

Cockpit reconciliation does not enable generic writes from the UI.

Allowed first-release behavior:
- browse;
- inspect;
- filter;
- compare;
- open graph;
- open campaign;
- open work;
- open blocker;
- inspect agent/capability state;
- resolve artifact links.

Future typed Director actions may include `approve`, `reject`, `prioritize`, `pause`, `retry` and `resolve`. They must map to typed mutation contracts, never arbitrary JSON patches.

## Legacy Retirement

Legacy dependency is reduced progressively:

1. active entity is touched;
2. first-touch hydration creates canonical GitHub entity;
3. future reads/writes use GitHub only;
4. hydration coverage is measured;
5. when all live operational state required by active campaigns is hydrated, set `LEGACY_READ_ALLOWED=false`;
6. Sheets/legacy Tower become archive/projection only.

No bulk destructive migration is required solely to make a historical record look modern.

## Vercel Project Cleanup Policy

Classify every NEXO Vercel project as one of:

- `CANONICAL`
- `ROLLBACK`
- `ARCHIVE`
- `DELETE_CANDIDATE`
- `RETIRED_DO_NOT_USE`

Initial expected classification:
- `nexo-atlas-cockpit`: CANONICAL
- `nexo-one`: ROLLBACK
- `nexo-atlas-control-tower`: ROLLBACK
- old previews/probes/smokes: ARCHIVE or DELETE_CANDIDATE
- Neon-named projects: RETIRED_DO_NOT_USE

No project is deleted before the canonical cockpit passes the read-path canary and at least one normal operating cycle.

## End-to-End Reconciliation Canary

The system is considered reconciled only when one evidence-backed path proves:

1. Advisor prepares or updates an executable WORK.
2. Tower accepts the mutation and emits receipt/event.
3. Executor queue changes mechanically.
4. Executor consumes a proven capability and produces provider/result evidence.
5. Result is verified and persisted canonically.
6. Learner receives the verified outcome when reusable.
7. Daily receives a material delta when Director-relevant.
8. Director bootstrap updates with a new event cursor.
9. Cockpit shows the updated state through View API only.
10. No normal-path read/write touches legacy Sheets.

The canary must record exact refs for every transition. Provider pulse without verified material output does not count as success.

## Failure Semantics

Failures are local and typed whenever possible.

Examples:
- `WRITE_CONFLICT_RETRY_REQUIRED`
- `BINDING_INCOMPLETE`
- `SOURCE_BINDING_REQUIRED`
- `CAPABILITY_NOT_FOUND`
- `ARTIFACT_NOT_FOUND`
- `VIEW_STALE`
- `LEGACY_HYDRATION_REQUIRED`
- `COCKPIT_VIEW_UNAVAILABLE`

A local failure must not be promoted into a global outage without evidence.

## Testing Gates

Before the cockpit becomes the sole operational frontend:

- unit tests for director bootstrap materialization;
- unit tests for event cursor monotonicity;
- unit tests for View API response contracts;
- tests proving no direct legacy read is required for already hydrated entities;
- tests for capability/artifact resolution;
- schema validation for all cockpit payloads;
- canary proving mutation -> view refresh -> cursor advance;
- production smoke for all read-only routes;
- end-to-end reconciliation canary described above.

## Non-Goals

This reconciliation does not:
- redesign the cockpit UI;
- introduce another database;
- restore Neon or any retired provider;
- move heavy artifacts into GitHub;
- enable arbitrary browser writes;
- delete rollback projects immediately;
- rebuild all 2,198 historical tests into hot-path entities.

## Final Target

```text
NEXO Atlas Cockpit
        |
        v
    NEXO View API
        |
  +-----+------------------+
  |                        |
  v                        v
GitHub Tower          Runtime/Resolvers
Truth Owner             |          |
                        v          v
                     Compute      Drive

Legacy Sheets/Tower -> read-only first-touch provenance -> retirement
```

The cockpit visualizes the system. Runtime operates the system. Tower records canonical state. Drive stores heavy evidence. Agents receive derived queues and submit typed mutations. No layer duplicates another layer's responsibility.