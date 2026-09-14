# DENER SSOT API + Pages Projection Design

## Objective

Unify operational state currently split between Google Drive and GitHub into the existing Google Spreadsheet `NEXO · SSOT CANONICAL`, renamed at cutover to `DENER · SSOT CANONICAL`, while preserving its existing private Drive identity.

The concrete spreadsheet identifier, sheet identifiers, deployment URL and credentials are private configuration. They MUST NOT appear in this public repository. The Apps Script adapter reads them from private Script Properties; GitHub consumes only the configured `SSOT_EXPORT_URL` secret.

GitHub remains code, schemas, execution contracts, scientific compute and deployment. GitHub Pages remains a read-only visualization surface. No new database, agent or always-on backend is introduced.

## Authority model after cutover

- `DENER · SSOT CANONICAL` in Google Drive: canonical state Truth Owner.
- `byDenoso/TCC`: public generic code, schemas, compute, validation and Pages build logic.
- Private Apps Script/Drive configuration: concrete SSOT adapter and identifiers.
- `byDenoso/NEXO-Obsidian-Vault/TOWER_V06`: frozen migration provenance / compatibility projection only.
- GitHub Pages: sanitized read model only.
- Heavy datasets and durable artifacts: Google Drive files referenced from canonical records.

There is no bidirectional state synchronization. Pages is rebuilt from SSOT. Scientific Actions return result envelopes; they do not become state authority.

## Canonical logical tables

`SYSTEM`, `PROJECTS`, `WORK`, `TESTS`, `EVENTS`, `KNOWLEDGE`, `RELATIONS`, `DECISIONS`, `OLYMPUS`.

Physical sheet names may differ during SHADOW migration. The adapter maps private storage to these logical names so frontend consumers never depend on row/column coordinates or concrete sheet names.

## Reconciliation precedence

1. Newer v0.6 operational NEXO/Science work and interdomain state: GitHub TOWER_V06 wins.
2. Olympus client/state records: Drive wins unless a newer verified record is explicitly identified.
3. Historical science programs/campaigns/test registry: Drive is preserved.
4. Verified execution artifact/result envelope: verified artifact wins for result fields.
5. Unresolved semantic conflicts: emit `CONFLICT`; never silently overwrite.

The migration produces `DRIVE_ONLY`, `GIT_ONLY`, `EQUAL`, `MERGED` and `CONFLICT` classifications before cutover. No timestamp-only last-write-wins rule is allowed across domains.

## Canonical API

Reuse the existing Apps Script/NEXO ONE pattern and bind it privately to the unified SSOT spreadsheet.

V1 read surface:
- `health`
- `export_public`
- `export_internal`

V1.1 write surface, enabled only after read path and reconciliation pass:
- `ingest_result`
- `mutate`

Writes are typed, version-aware and idempotent. `accepted=true` is not terminal success without `readback=PASS`.

## View API for the app

GitHub Pages never reads Sheets directly. Every three hours a GitHub Action calls the configured private `export_public` endpoint, validates the payload, compares `state_hash`, and materializes static JSON only when state changed.

Default cadence: `0 */3 * * *` plus `workflow_dispatch`.

Public contract:
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
- `/api/v1/graphs/clients.json`
- `/api/v1/graphs/relations.json`

## Privacy boundary

Pages receives only an explicit allowlist summary for the private client domain. Full private client state remains inside Drive/SSOT. Public source code contains no concrete Drive identifiers.

## Scientific execution

Existing `runtime/nexo_execution` and TCC Actions remain compute:

`SSOT frozen work -> Executor -> execution contract -> GitHub Action -> artifact + verification -> Executor acceptance -> SSOT ingest + readback`.

Actions do not independently adjudicate science and do not write arbitrary spreadsheet cells.

## Reliability invariants

1. One state Truth Owner after cutover.
2. Typed mutation only.
3. Version/CAS-style conflict detection.
4. Exact readback required after writes.
5. Idempotency key required for result ingestion.
6. Deterministic `state_hash` excluding volatile timestamps.
7. Public projection is allowlist-based.
8. Invalid export never replaces last known-good Pages snapshot.
9. Every public snapshot exposes `schema_version`, `ssot_revision`, `generated_at` and `state_hash`.
10. No cutover with unresolved material conflicts.
11. Concrete SSOT identifiers live only in private configuration.

## Non-goals for V1

No new database, no event bus, no live per-request Sheets backend for Pages, no new NEXO agent, no direct Action write into arbitrary SSOT cells, no full private client UI on public Pages, and no deletion of historical TOWER/legacy tabs during initial cutover.

## Success criteria

1. Reconciliation has zero unresolved material conflicts.
2. Existing spreadsheet is declared sole state authority only after explicit cutover.
3. `export_public` returns deterministic validated projection.
4. Three-hour materialization publishes View API and skips unchanged state.
5. App renders exclusively from `/api/v1/*`.
6. One scientific result completes Action -> verification -> SSOT ingest -> readback -> projection.
7. One private-domain update reaches Pages only through allowed summary fields.
8. TOWER_V06 is frozen as provenance.
