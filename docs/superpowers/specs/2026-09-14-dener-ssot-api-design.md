# DENER SSOT API + Pages Projection Design

## Objective

Unify the operational state currently split between Google Drive and GitHub into the existing Google Spreadsheet `NEXO · SSOT CANONICAL` (file id `1e6s2dKOYVLNsPUguHI85RLVLwJKtlCsQZBJ1BE-UhaY`), rename it to `DENER · SSOT CANONICAL` without changing its file id, and make it the single state Truth Owner.

GitHub remains code, schemas, execution contracts, scientific compute and deployment. GitHub Pages remains a read-only visualization surface. No new database, agent or always-on backend is introduced.

## Current-state findings

- Drive contains richer historical science/program/campaign state and the substantive Olympus client registry.
- GitHub `NEXO-Obsidian-Vault/TOWER_V06` contains newer operational work, interdomain and v0.6 control state.
- TCC main already contains `runtime/nexo_view_api`, `runtime/nexo_agent_api`, typed mutation/readback semantics, `runtime/nexo_execution`, graph/template assets and scientific Actions.
- Drive already contains `NEXO_ONE_v39_NexoOneCore.gs`, which provides a reusable Apps Script snapshot/projection pattern.

## Authority model after cutover

- `DENER · SSOT CANONICAL` in Google Drive: canonical state Truth Owner.
- `byDenoso/TCC`: code, schemas, compute, validation and Pages build logic.
- `byDenoso/NEXO-Obsidian-Vault/TOWER_V06`: frozen migration provenance / compatibility projection only.
- GitHub Pages: sanitized read model only.
- Heavy datasets and durable artifacts: Google Drive files referenced by stable IDs/URLs from SSOT records.

There is no bidirectional state synchronization. Pages is rebuilt from SSOT. Scientific Actions return result envelopes; they do not become state authority.

## Canonical logical tables

The target logical model is:

1. `SYSTEM` — SSOT version, revision, authority, schema, last successful materialization and health.
2. `PROJECTS` — active projects/programs/campaigns across science, Olympus and engineering.
3. `WORK` — actionable units and ownership.
4. `TESTS` — frozen tests, runs, terminal outcomes and evidence refs.
5. `EVENTS` — append-only material event trail.
6. `KNOWLEDGE` — verified object/procedural learning.
7. `RELATIONS` — intra-domain and interdomain relations.
8. `DECISIONS` — material decisions and supersession.
9. `OLYMPUS` — private Olympus/client state.

Existing legacy tabs may remain during migration but are labeled `LEGACY` or `PROJECTION` and excluded from the canonical API contract.

## Reconciliation precedence

One-time reconciliation is explicit rather than last-write-wins:

1. Newer v0.6 operational NEXO/Science work and interdomain state: GitHub TOWER_V06 wins.
2. Olympus client/state records: Drive wins unless a newer verified record is explicitly identified.
3. Historical science programs/campaigns/test registry: Drive is preserved.
4. Verified execution artifact/result envelope: verified artifact wins for result fields.
5. Unresolved semantic conflicts: write a `CONFLICT` reconciliation record; never silently overwrite.

The migration produces an entity-level report with `DRIVE_ONLY`, `GIT_ONLY`, `EQUAL`, `MERGED` and `CONFLICT` classes before cutover.

## Canonical API

Reuse the existing Apps Script/NEXO ONE pattern and bind it to the unified SSOT spreadsheet.

V1 read surface:

- `GET/POST health`
- `POST export_public` — sanitized deterministic projection for Pages.
- `POST export_internal` — authenticated full export for migration/operations.

V1.1 write surface, enabled only after read path and reconciliation pass:

- `POST ingest_result`
- `POST mutate`

Writes are typed, version-aware and idempotent. A mutation is successful only after exact readback. `accepted=true` without `readback=PASS` is not terminal success.

## View API for the app

GitHub Pages never reads Sheets directly. Every three hours a GitHub Action calls `export_public`, validates the payload, computes/compares `state_hash`, and, only on change, materializes static JSON endpoints into the Pages artifact.

Default cadence: `0 */3 * * *` plus `workflow_dispatch` for manual rebuild.

Target read paths:

- `/api/v1/health.json`
- `/api/v1/snapshot.json`
- `/api/v1/projects.json`
- `/api/v1/work.json`
- `/api/v1/tests.json`
- `/api/v1/knowledge.json`
- `/api/v1/relations.json`
- `/api/v1/decisions.json`
- `/api/v1/olympus-summary.json`
- `/api/v1/graphs/catalog.json`
- `/api/v1/graphs/science.json`
- `/api/v1/graphs/olympus.json`
- `/api/v1/graphs/interdomain.json`

The frontend depends on this contract, never on Sheet row/column coordinates.

## Privacy boundary

Pages receives no raw labs, medication/protocol detail, photos, private notes, full client measurements or other sensitive Olympus content. `olympus-summary.json` contains only fields approved for dashboard display, such as internal id/label, status, program, freshness and next action.

The full Olympus state stays inside Drive/SSOT.

## Scientific execution

Existing `runtime/nexo_execution` and TCC GitHub Actions remain the compute path:

`SSOT frozen work -> Executor -> execution contract -> GitHub Action -> artifact + verification -> Executor acceptance -> SSOT ingest + readback`.

GitHub Actions do not independently adjudicate science and do not write arbitrary Sheet cells.

## Reuse policy

MERGE / EXTEND / SUPERSEDE / CREATE:

- MERGE: Drive content + TOWER_V06 current state during one-time reconciliation.
- EXTEND: `NEXO_ONE_v39_NexoOneCore.gs`, `runtime/nexo_view_api`, `runtime/nexo_agent_api`, existing graph/template code and `nexo_execution`.
- SUPERSEDE: TOWER_V06 as Truth Owner; old two-spreadsheet NEXO ONE source model.
- CREATE only: SSOT schemas/reconciler, Apps Script adapter changes, Pages materializer workflow and minimal app adapter.

## Reliability invariants

1. One state Truth Owner after cutover.
2. Typed mutation only.
3. Version/CAS-style conflict detection on canonical entities.
4. Exact readback required after writes.
5. Idempotency key required for result ingestion.
6. Deterministic `state_hash` on exports.
7. Public projection sanitized before leaving Drive.
8. Invalid export does not replace the last good Pages snapshot.
9. Every Pages payload exposes `ssot_revision`, `generated_at`, `state_hash` and schema version.
10. No migration cutover until reconciliation contains zero unresolved material conflicts.

## Non-goals for V1

- No new database.
- No event-driven Drive->GitHub webhook.
- No live per-request Sheets backend for Pages.
- No new NEXO agent.
- No direct GitHub Action scientific write into arbitrary SSOT cells.
- No private full Olympus UI on GitHub Pages.
- No deletion of historical TOWER_V06 or legacy Drive tabs during initial cutover.

## Success criteria

The migration is complete when:

1. Drive/Git reconciliation report has no unresolved material conflict.
2. Existing spreadsheet retains its file id and is declared sole state authority.
3. `export_public` returns a validated deterministic sanitized snapshot.
4. Scheduled materialization every 3 hours publishes the View API and skips unchanged state.
5. The app renders only from `/api/v1/*` and no longer reconstructs state from raw stores.
6. One real scientific result completes Action -> verification -> SSOT ingest -> readback -> Pages projection.
7. One Olympus update appears in the private SSOT and only its allowed summary fields reach Pages.
8. TOWER_V06 is frozen/archived as provenance and no longer receives canonical mutations.
