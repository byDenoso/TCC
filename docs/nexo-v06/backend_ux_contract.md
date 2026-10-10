# NEXO Backend UX Contract

## Goal

Keep one canonical state while making it readable by agents and frontend consumers without coupling the UI to storage internals.

## Authority

1. `DENER · SSOT CANONICAL` in Google Drive is the target state Truth Owner after explicit cutover.
2. Until cutover completes, TOWER_V06 remains the live authority and the new SSOT operates in SHADOW mode.
3. GitHub/TCC owns code, compute, validation and static projections; it is not the post-cutover state authority.
4. Heavy artifacts and private source material remain in Drive.
5. TOWER_V06 is preserved as migration provenance after cutover.

## Read model

1. The frontend consumes a View API, never raw spreadsheet coordinates or storage scanning.
2. The public View API is a sanitized static projection materialized from `export_public`.
3. Every public snapshot carries `schema_version`, `ssot_revision`, `state_hash` and `generated_at`.
4. `state_hash` is deterministic and excludes volatile timestamps.
5. Invalid exports never replace the last known-good public snapshot.
6. Raw Olympus private/health fields never enter the public projection.

## Operational semantics

1. `READY` is not equal to `executor_eligible`.
2. Provider pulse and material execution are separate states.
3. Every blocker uses a typed `blocking_code`.
4. Every graph uses a stable `graph_id`.
5. Writes use typed mutations with expected version, event emission and exact readback.
6. `accepted=true` without `readback=PASS` is not a completed canonical write.

## View API v1

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
- `/api/v1/graphs/:graph_id.json`

The HTTP/static transport may change later without changing this consumer contract.
