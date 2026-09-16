# Universal Test Campaign Design

## Goal

Make every user/system-declared relevant test a canonical Tower entity before or at dispatch, independent of domain, and expose campaigns/tests through generic graph projections consumed by Atlas/NEXO One.

## Canonical hierarchy

`DOMAIN → PROJECT/HYPOTHESIS/WORK → CAMPAIGN → TEST_GROUP → TEST → RUN/EVENT → RESULT/ARTIFACT`

`TEST` is graph-visible canonical work. `CHECK` is internal runtime verification and is not graph-projected by default.

## Canonical entities

`CAMPAIGN`, `TEST_GROUP`, `TEST`, `RUN`, `RESULT`, and `ARTIFACT` are first-class canonical entity kinds. Existing `PROJECT`, `HYPOTHESIS`, and `WORK` may parent campaigns.

A TEST stores at minimum: stable identity, domain, project/parent/test-group/campaign references, title/objective, operational status, analytical status, capability, current/history run references, timestamps, evidence/artifact links, hypothesis/work/dataset relations, and provenance.

Operational state and analytical state are distinct. Execution success must never imply scientific support.

## Universal ingress

A single `register_test(...)` ingress resolves or creates the campaign/test-group, creates the canonical TEST, creates a canonical RUN, emits mutation events/readback, and only then returns a dispatch-ready identity bundle.

Executors must not invent TEST identity. They receive `test_id` and `run_id` from ingress. Internal checks stay runtime-local unless explicitly promoted to TEST.

## Projection

Graph projection is type/relation-driven and generic. Frontends must not special-case PEER, Olympus, Cosmology, Software, or any project name.

Projected nodes include route metadata derived from entity type/id. Root grouping comes from each entity's `domain`, not a hardcoded Science root.

The primary graph should remain compact: domain/project/campaign nodes are visible at high level; campaign drill-down exposes TEST_GROUP/TEST; test detail exposes RUN/RESULT/ARTIFACT.

## Frontend interaction

A campaign appears as a node inside the subgraph for its domain. Selecting it exposes campaign metadata plus a canonical route/link to its tests. The route is derived from entity type/id, not manually stored per project.

Recommended routes:

- `/campaigns/:campaignId`
- `/tests/:testId`

The campaign page lists linked TEST_GROUP/TEST entities and statuses. The test page may expose runs, results, artifacts, evidence, and provenance.

## Compatibility

Legacy tests that exist only as workflows/logs/artifacts are not silently discarded. Migration/reconciliation may promote materially relevant historical executions into canonical TEST/RUN entities while preserving provenance.

## Acceptance

1. Creating a campaign through the canonical mutation writer succeeds with readback.
2. `register_test` creates/reuses campaign/test-group, creates TEST and RUN before returning dispatch data.
3. Projection exposes domain, campaign/test relations, split operational/analytical status, and derived routes.
4. Frontend graph renders campaign nodes under their actual domain and lets the user navigate to campaign test drill-down.
5. No frontend code branches on project-specific names such as PEER or Olympus.
