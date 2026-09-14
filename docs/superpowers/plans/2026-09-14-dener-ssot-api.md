# DENER SSOT API + Pages Projection Implementation Plan

> **For agentic workers:** use the existing SSOT design and execute changes in isolation with tests/readback before merge.

**Goal:** Reconcile Drive and TOWER_V06, make the existing Drive spreadsheet the target single state Truth Owner after explicit cutover, expose a private Apps Script adapter, and materialize a sanitized static View API to GitHub Pages every three hours.

**Security boundary:** concrete Drive file IDs, sheet IDs, deployment URLs and credentials are private configuration. This public repository contains only generic schemas, reconcilers, materializers and workflows. `SSOT_EXPORT_URL` is supplied as a GitHub secret; the Apps Script spreadsheet mapping is supplied through private Script Properties/private source.

**Architecture:** Drive SSOT = state; TCC = public code/compute/validation; private Apps Script = canonical adapter; Pages = sanitized projection; TOWER_V06 = live authority until cutover, then frozen provenance.

**Cadence:** `0 */3 * * *` plus manual `workflow_dispatch`.

## Phase 1: Schema

Implement `runtime/nexo_ssot/schema.py` and tests. Required logical sections: `projects`, `work`, `tests`, `events`, `knowledge`, `relations`, `decisions`, `olympus_summary`, plus `system`. Every snapshot exposes `schema_version`, `ssot_revision`, `state_hash`, `generated_at`.

Gate: schema tests PASS.

## Phase 2: Reconciliation

Implement deterministic Drive × TOWER reconciler and CLI. Classifications: `DRIVE_ONLY`, `GIT_ONLY`, `EQUAL`, `MERGED`, `CONFLICT`.

Rules:
- Drive owns private client state.
- Verified result wins result fields.
- Higher operational entity version may win `work`/`relations` when semantics match.
- Otherwise disagreement becomes `CONFLICT`.
- Never use cross-domain timestamp-only last-write-wins.

Gate: `material_conflict_count == 0` before cutover.

## Phase 3: Private read adapter

Extend the existing NEXO ONE Apps Script pattern privately. V1 operations: `health`, `export_public`, `export_internal`.

Requirements:
- deterministic state hash;
- allowlist public client summary;
- no concrete private identifiers in public source;
- missing mapping returns structured `SCHEMA_NOT_READY`;
- read-only during SHADOW.

Gate: repeated unchanged exports have identical `state_hash` and public projection contains only approved fields.

## Phase 4: Shadow SSOT

Back up the existing spreadsheet before mutation. Create/normalize shadow logical projections without deleting legacy tabs. Populate from reconciled candidate. Keep TOWER_V06 as truth during this phase.

Gate: candidate and shadow export agree by IDs/counts/material fields.

## Phase 5: Static View API

Extend `runtime/nexo_ssot/materialize.py` and existing `nexo_view_api` concepts to produce:

- `/api/v1/health.json`
- `/api/v1/snapshot.json`
- `/api/v1/projects.json`
- `/api/v1/work.json`
- `/api/v1/tests.json`
- `/api/v1/knowledge.json`
- `/api/v1/relations.json`
- `/api/v1/decisions.json`
- `/api/v1/olympus-summary.json`
- graph catalog + science/client/relation graph payloads.

Gate: invalid snapshot fails without producing a deployable replacement.

## Phase 6: Three-hour Pages materialization

Workflow `materialize-ssot-pages.yml`:
1. fetch configured `SSOT_EXPORT_URL?op=export_public`;
2. validate;
3. compare/dedupe by `state_hash`;
4. skip unchanged state;
5. materialize static API;
6. deploy Pages artifact only after validation;
7. preserve last known-good Pages state on failure.

Gate: CI tests PASS; manual run PASS after private endpoint/secret are configured.

## Phase 7: Write API, later

Only after Phases 1–6 pass, add typed `ingest_result` and `mutate` with expected version, idempotency, append-only event receipt and exact readback. Reuse semantics already proven in `nexo_agent_api`.

## Phase 8: Scientific ingest, later

Keep existing GitHub Actions as compute/verification. Executor accepts verified artifact and writes through canonical API. GitHub does not become state authority.

## Phase 9: Atomic cutover, later

Only after reconciliation, API, projection and end-to-end tests pass:
- Drive SSOT becomes truth;
- Advisor/Executor/Meta/Daily change together;
- TOWER_V06 becomes frozen provenance;
- no period of dual truth.

## Verification commands

```bash
python -m unittest \
  runtime.nexo_ssot.test_schema \
  runtime.nexo_ssot.test_reconcile \
  runtime.nexo_ssot.test_public_projection \
  runtime.nexo_ssot.test_materialize -v
```

## Rollback

Before cutover: TOWER remains authority, so rollback is simply abandoning shadow changes. After cutover: preserve Drive SSOT, stop materialization, and restore prior authority only through an explicit migration decision. Never silently reconstruct truth from Pages.
