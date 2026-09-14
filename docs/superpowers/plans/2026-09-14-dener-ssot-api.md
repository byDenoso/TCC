# DENER SSOT API + Pages Projection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the existing Drive spreadsheet the sole state Truth Owner, reconcile it with TOWER_V06, expose a safe canonical Apps Script API, materialize a sanitized static View API every 3 hours, and keep TCC GitHub Actions as scientific compute.

**Architecture:** The existing Google Spreadsheet becomes `DENER · SSOT CANONICAL` without changing its file id. Apps Script is the canonical adapter over that sheet. TCC validates/materializes a sanitized projection into static `/api/v1/*.json` artifacts on a three-hour schedule. Existing `nexo_agent_api`, `nexo_view_api`, `nexo_execution`, scientific workflows and graph contracts are extended rather than replaced.

**Tech Stack:** Google Sheets, Google Apps Script, Python 3 standard library, unittest, JSON/JSON Schema-style validation, GitHub Actions, GitHub Pages/static JSON.

**Spec:** `docs/superpowers/specs/2026-09-14-dener-ssot-api-design.md`

## Global Constraints

- Existing spreadsheet id remains `1e6s2dKOYVLNsPUguHI85RLVLwJKtlCsQZBJ1BE-UhaY`.
- Default sync cadence is every 3 hours: `0 */3 * * *`.
- No new database, agent, event bus or always-on backend in V1.
- TCC Actions remain compute/verification, not state authority.
- `TOWER_V06` is not deleted; it becomes frozen migration provenance after cutover.
- Public materialization must exclude raw Olympus private/health fields.
- A write is complete only after exact readback.
- Unchanged `state_hash` must skip materialization/deploy churn.
- Failed validation must preserve the last known-good public snapshot.
- No canonical cutover while reconciliation has unresolved material conflicts.

---

### Task 1: Freeze the target schema and reconciliation contract

**Files:**
- Create: `runtime/nexo_ssot/__init__.py`
- Create: `runtime/nexo_ssot/schema.py`
- Create: `runtime/nexo_ssot/test_schema.py`
- Create: `runtime/nexo_ssot/fixtures/drive_minimal.json`
- Create: `runtime/nexo_ssot/fixtures/tower_minimal.json`
- Modify: `docs/nexo-v06/backend_ux_contract.md`

**Interfaces:**
- Produces: `CANONICAL_SECTIONS`, `normalize_record(record)`, `validate_snapshot(snapshot) -> list[str]`.
- Later tasks consume the same normalized record keys and validation errors.

- [ ] **Step 1: Write failing schema tests**

```python
import unittest
from runtime.nexo_ssot.schema import validate_snapshot

class SnapshotSchemaTests(unittest.TestCase):
    def test_requires_revision_hash_and_sections(self):
        payload = {"schema_version": "1.0"}
        errors = validate_snapshot(payload)
        self.assertIn("ssot_revision", " ".join(errors))
        self.assertIn("state_hash", " ".join(errors))
        self.assertIn("projects", " ".join(errors))

    def test_valid_minimal_snapshot(self):
        payload = {
            "schema_version": "1.0",
            "ssot_revision": 1,
            "state_hash": "sha256:test",
            "generated_at": "2026-09-14T00:00:00Z",
            "projects": [], "work": [], "tests": [], "events": [],
            "knowledge": [], "relations": [], "decisions": [],
            "olympus_summary": [], "system": {}
        }
        self.assertEqual(validate_snapshot(payload), [])
```

- [ ] **Step 2: Run the tests and confirm failure**

Run:

```bash
python -m unittest runtime.nexo_ssot.test_schema -v
```

Expected: import/module failure because `runtime.nexo_ssot.schema` does not exist.

- [ ] **Step 3: Implement the minimal schema module**

`runtime/nexo_ssot/schema.py` must define the required top-level fields and reject missing/wrong-type values. Keep validation dependency-free.

- [ ] **Step 4: Add normalized fixture records**

Fixtures must include one project, one work item, one test and one relation using stable ids. No sensitive data goes into fixtures.

- [ ] **Step 5: Update backend contract language**

Change the authority section so the frontend contract says: Drive SSOT is state authority; GitHub is code/compute; frontend consumes materialized View API.

- [ ] **Step 6: Run tests**

```bash
python -m unittest runtime.nexo_ssot.test_schema runtime.nexo_view_api.test_reader -v
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add runtime/nexo_ssot docs/nexo-v06/backend_ux_contract.md
git commit -m "feat: define unified SSOT schema contract"
```

---

### Task 2: Build the one-time Drive × TOWER reconciliation engine

**Files:**
- Create: `runtime/nexo_ssot/reconcile.py`
- Create: `runtime/nexo_ssot/test_reconcile.py`
- Create: `scripts/reconcile_dener_ssot.py`

**Interfaces:**
- Consumes: normalized Drive export and TOWER_V06 export.
- Produces: `ReconciliationResult` JSON containing `candidate`, `items`, `material_conflict_count`.
- Statuses: `DRIVE_ONLY`, `GIT_ONLY`, `EQUAL`, `MERGED`, `CONFLICT`.

- [ ] **Step 1: Write failing precedence tests**

```python
class ReconcileTests(unittest.TestCase):
    def test_git_wins_for_newer_operational_work(self): ...
    def test_drive_wins_for_olympus_client_state(self): ...
    def test_verified_result_wins_result_fields(self): ...
    def test_semantic_disagreement_becomes_conflict(self): ...
```

Each test must assert both winning payload and reconciliation class.

- [ ] **Step 2: Verify failures**

```bash
python -m unittest runtime.nexo_ssot.test_reconcile -v
```

Expected: FAIL because reconciler is absent.

- [ ] **Step 3: Implement deterministic reconciliation**

Rules are copied exactly from the design spec. Never use timestamp-only last-write-wins across domains. `CONFLICT` retains both source payloads and an explicit reason.

- [ ] **Step 4: Implement CLI**

Command:

```bash
python scripts/reconcile_dener_ssot.py \
  --drive-export /tmp/drive.json \
  --tower-export /tmp/tower.json \
  --output /tmp/reconciliation.json
```

Exit code must be non-zero when `material_conflict_count > 0`.

- [ ] **Step 5: Test idempotence**

Running the reconciler twice with identical inputs must produce byte-identical canonical candidate content after excluding `generated_at`.

- [ ] **Step 6: Commit**

```bash
git add runtime/nexo_ssot/reconcile.py runtime/nexo_ssot/test_reconcile.py scripts/reconcile_dener_ssot.py
git commit -m "feat: add deterministic Drive Tower reconciliation"
```

---

### Task 3: Convert the existing NEXO ONE Apps Script into the read-only SSOT adapter

**Files:**
- Create: `runtime/nexo_ssot/apps_script/Code.gs`
- Create: `runtime/nexo_ssot/apps_script/Export.gs`
- Create: `runtime/nexo_ssot/apps_script/Sanitize.gs`
- Create: `runtime/nexo_ssot/apps_script/Hash.gs`
- Create: `runtime/nexo_ssot/apps_script/appsscript.json`
- Create: `runtime/nexo_ssot/apps_script/README.md`
- Create: `runtime/nexo_ssot/test_public_export.py`

**Interfaces:**
- Reuses concepts from Drive file `NEXO_ONE_v39_NexoOneCore.gs`.
- `doGet/doPost` support `health`, `export_public`, `export_internal`.
- `export_public` returns the static View API source payload.

- [ ] **Step 1: Write a public-export contract test in Python**

The test loads a fixture of Apps Script output and asserts:

```python
self.assertNotIn("labs", serialized)
self.assertNotIn("medication", serialized)
self.assertIn("olympus_summary", payload)
self.assertIn("state_hash", payload)
self.assertIn("ssot_revision", payload)
```

- [ ] **Step 2: Implement `Code.gs` routing**

Use explicit operation allowlist only. Unknown operations return JSON error with HTTP-compatible status metadata in the body.

- [ ] **Step 3: Implement canonical Sheet readers**

Read only the canonical logical tabs: `SYSTEM`, `PROJECTS`, `WORK`, `TESTS`, `EVENTS`, `KNOWLEDGE`, `RELATIONS`, `DECISIONS`, `OLYMPUS`.

During migration, missing target tabs return a structured `SCHEMA_NOT_READY` error rather than silently reading legacy tabs.

- [ ] **Step 4: Implement sanitization**

Public Olympus allowlist:

```text
id,label,status,program,checkin_status,freshness,next_action
```

All other Olympus fields are excluded by construction, not by blacklist.

- [ ] **Step 5: Implement deterministic hash**

Canonicalize JSON by recursively sorting object keys and preserving array order defined by stable ids. Exclude `generated_at` from the hash input. Prefix result with `sha256:`.

- [ ] **Step 6: Document deployment**

`README.md` must specify the existing spreadsheet id, Apps Script deployment steps, required Script Properties for future write auth, and smoke URLs/operations.

- [ ] **Step 7: Run tests**

```bash
python -m unittest runtime.nexo_ssot.test_public_export -v
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add runtime/nexo_ssot/apps_script runtime/nexo_ssot/test_public_export.py
git commit -m "feat: add read-only Drive SSOT adapter"
```

---

### Task 4: Create the shadow canonical state inside the existing Spreadsheet

**Files:**
- Modify deployed Apps Script from Task 3.
- Produce migration artifact: `reconciliation-YYYYMMDD.json` outside the public repo if it contains private state.

**Interfaces:**
- Consumes: reconciliation candidate from Task 2.
- Produces: canonical tabs in the same spreadsheet id and `SYSTEM.ssot_revision`.

- [ ] **Step 1: Snapshot the current spreadsheet before mutation**

Create a Drive backup/copy and record its file id in the migration event. No legacy tab is deleted.

- [ ] **Step 2: Create missing canonical tabs only**

Ensure these exact logical tabs exist:

```text
SYSTEM PROJECTS WORK TESTS EVENTS KNOWLEDGE RELATIONS DECISIONS OLYMPUS
```

Reuse existing tabs with the same name. Do not create `WORK_V2`-style parallel truths.

- [ ] **Step 3: Load the reconciliation candidate into shadow mode**

Add to `SYSTEM`:

```text
SSOT_SCHEMA_VERSION=1.0
SSOT_MODE=SHADOW
TRUTH_OWNER=PENDING_CUTOVER
SSOT_REVISION=<monotonic integer>
```

- [ ] **Step 4: Read back every canonical section**

Export the shadow state through `export_internal` and compare counts + stable ids against the reconciliation candidate.

- [ ] **Step 5: Gate on conflicts**

Do not proceed if `material_conflict_count != 0` or if any expected stable id is missing after readback.

- [ ] **Step 6: Record migration receipt**

Append one `EVENTS` row containing source hashes/versions, backup id, reconciliation status and readback status.

---

### Task 5: Extend the existing Python View API into a static materializer

**Files:**
- Modify: `runtime/nexo_view_api/reader.py`
- Create: `runtime/nexo_view_api/materializer.py`
- Create: `runtime/nexo_view_api/test_materializer.py`
- Create: `scripts/materialize_ssot_view.py`

**Interfaces:**
- Consumes: validated `export_public` JSON.
- Produces directory tree rooted at `build/ssot-view/api/v1/`.

- [ ] **Step 1: Write failing materialization tests**

Assert the materializer creates:

```text
health.json
snapshot.json
projects.json
work.json
tests.json
knowledge.json
relations.json
decisions.json
olympus-summary.json
graphs/catalog.json
graphs/science.json
graphs/olympus.json
graphs/interdomain.json
```

- [ ] **Step 2: Verify test failure**

```bash
python -m unittest runtime.nexo_view_api.test_materializer -v
```

- [ ] **Step 3: Implement materializer**

`materialize(payload, output_dir)` first calls `validate_snapshot`. It writes to a temporary directory and atomically replaces the target only after all files validate.

- [ ] **Step 4: Reuse graph contracts**

Preserve stable `graph_id` behavior from the existing Tower reader. Build graph nodes/edges from normalized `projects`, `work` and `relations`; do not scan arbitrary storage.

- [ ] **Step 5: Implement CLI**

```bash
python scripts/materialize_ssot_view.py --input /tmp/public.json --output build/ssot-view/api/v1
```

- [ ] **Step 6: Regression test existing reader**

```bash
python -m unittest runtime.nexo_view_api.test_reader runtime.nexo_view_api.test_materializer -v
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add runtime/nexo_view_api scripts/materialize_ssot_view.py
git commit -m "feat: materialize SSOT static view API"
```

---

### Task 6: Add the 3-hour GitHub Action materialization pipeline

**Files:**
- Create: `.github/workflows/materialize-ssot-pages.yml`
- Create: `scripts/fetch_ssot_public.py`
- Create: `runtime/nexo_ssot/test_fetch_public.py`

**Interfaces:**
- `fetch_ssot_public.py --url "$SSOT_PUBLIC_EXPORT_URL" --output /tmp/public.json`.
- Workflow validates, materializes and publishes only a valid changed snapshot.

- [ ] **Step 1: Test fetch behavior with a local HTTP stub**

Cover success, malformed JSON, timeout and non-2xx response. No third-party Python dependency.

- [ ] **Step 2: Implement fetch helper**

Use `urllib.request`, explicit timeout and maximum payload size. Validate with `validate_snapshot` before writing the output file.

- [ ] **Step 3: Add scheduled workflow**

Trigger block:

```yaml
on:
  schedule:
    - cron: '0 */3 * * *'
  workflow_dispatch:
```

- [ ] **Step 4: Add hash short-circuit**

Compare new `state_hash` to the last successfully published metadata. If unchanged, report `NO_CHANGE` and exit successfully without Pages rebuild.

- [ ] **Step 5: Preserve last good snapshot on failure**

Validation/fetch failure must fail the job before replacing any Pages artifact. Never publish partial output.

- [ ] **Step 6: Publish Pages-compatible artifact**

The Pages artifact contains the app build plus `/api/v1/` static JSON, or, if the app is deployed from a different Pages repo, expose `build/ssot-view/api/v1` as a standalone artifact for that repo's deploy job. Do not commit generated snapshots to `main`.

- [ ] **Step 7: Run unit tests and workflow syntax validation**

```bash
python -m unittest runtime.nexo_ssot.test_fetch_public runtime.nexo_view_api.test_materializer -v
```

- [ ] **Step 8: Commit**

```bash
git add .github/workflows/materialize-ssot-pages.yml scripts/fetch_ssot_public.py runtime/nexo_ssot/test_fetch_public.py
git commit -m "ci: materialize SSOT view every three hours"
```

---

### Task 7: Enable typed result ingestion by extending existing mutation semantics

**Files:**
- Create: `runtime/nexo_ssot/apps_script/Ingest.gs`
- Create: `runtime/nexo_ssot/apps_script/Auth.gs`
- Create: `runtime/nexo_ssot/test_ingest_contract.py`
- Modify: `runtime/nexo_agent_api/mutations.py`
- Modify: `runtime/nexo_agent_api/test_mutations.py`

**Interfaces:**
- Reuses existing `request_id`, expected version/readback and typed mutation ideas from `nexo_agent_api`.
- Apps Script operation: `ingest_result`.
- Required keys: `request_id`, `idempotency_key`, `work_id`, `test_id`, `run_id`, `verification`, `result_ref`.

- [ ] **Step 1: Write failing ingestion contract tests**

Cases:

```text
same idempotency key twice -> one canonical write, second returns original receipt
verification != PASS -> rejected
unknown work_id -> rejected
version mismatch -> WRITE_CONFLICT_RETRY_REQUIRED
successful ingest -> readback=PASS and event id returned
```

- [ ] **Step 2: Add HMAC request envelope for writes**

Request body:

```json
{
  "auth": {"timestamp": "...", "nonce": "...", "signature": "..."},
  "request": {"operation": "ingest_result", "request_id": "..."}
}
```

Signature is computed over `timestamp + "\n" + nonce + "\n" + canonical_json(request)` using an Apps Script Property secret. Reject stale timestamps and repeated nonce.

- [ ] **Step 3: Implement idempotent transaction**

Order:

```text
validate -> locate work/test -> check idempotency -> apply typed changes -> append event -> readback -> persist receipt -> return PASS
```

- [ ] **Step 4: Keep scientific Actions write-free**

Do not add Drive credentials to `nexo-execution.yml`. Executor or an explicit acceptance step calls `ingest_result` only after verification.

- [ ] **Step 5: Run regression tests**

```bash
python -m unittest runtime.nexo_agent_api.test_mutations runtime.nexo_ssot.test_ingest_contract -v
```

- [ ] **Step 6: Commit**

```bash
git add runtime/nexo_ssot/apps_script runtime/nexo_ssot/test_ingest_contract.py runtime/nexo_agent_api/mutations.py runtime/nexo_agent_api/test_mutations.py
git commit -m "feat: add typed SSOT result ingestion"
```

---

### Task 8: Perform the authority cutover without breaking compute

**Files:**
- Modify: `NEXO-Obsidian-Vault/TOWER_V06/CONTROL.json`
- Modify the four active automation prompts/configs outside the TCC repo.
- Modify: `DENER · SSOT CANONICAL / SYSTEM` rows.

**Interfaces:**
- New authority marker: `GOOGLE_DRIVE_SSOT_V1`.
- TOWER marker: `FROZEN_MIGRATION_PROVENANCE`.

- [ ] **Step 1: Run pre-cutover verification**

Must all pass:

```text
material_conflict_count = 0
export_internal validates
export_public validates
public sanitization test PASS
materializer test PASS
3-hour workflow manual dispatch PASS
one no-change rerun returns NO_CHANGE
```

- [ ] **Step 2: Freeze TOWER writes**

Update TOWER control so its state is clearly read-only/provenance. Do not delete entities or history.

- [ ] **Step 3: Promote Drive SSOT atomically**

Set in `SYSTEM`:

```text
SSOT_MODE=ACTIVE
TRUTH_OWNER=GOOGLE_DRIVE_SSOT_V1
SSOT_SCHEMA_VERSION=1.0
```

Rename the spreadsheet to `DENER · SSOT CANONICAL` while preserving file id.

- [ ] **Step 4: Update Advisor/Executor/Meta/Daily read path**

All four read canonical state from the Drive SSOT. Existing GitHub Actions remain callable for scientific execution.

- [ ] **Step 5: Run one real scientific closure test**

Required observed path:

```text
SSOT WORK -> execution contract -> TCC Action -> verification PASS -> ingest_result -> readback PASS -> next 3h materialization -> Pages View API reflects terminal result
```

- [ ] **Step 6: Run one Olympus privacy test**

Change a private Olympus field plus an allowed summary field. Verify private field stays absent from public JSON and the allowed summary field changes.

- [ ] **Step 7: Record cutover decision/event**

Append canonical `DECISIONS` + `EVENTS` entries with prior Truth Owner, new Truth Owner, hashes, backup id and verification receipts.

---

### Task 9: Remove only proven-obsolete routing, not history

**Files:**
- Modify: `runtime/nexo_agent_api/service.py`
- Modify: `runtime/nexo_agent_api/views.py`
- Modify: `runtime/nexo_view_api/reader.py`
- Modify tests in both packages.

**Interfaces:**
- Existing classes may remain as compatibility wrappers, but normal runtime must no longer require a mutable filesystem-backed TOWER.

- [ ] **Step 1: Add tests proving Drive-derived snapshot is sufficient**

Agent/view logic must operate from normalized SSOT snapshot fixtures without reading `TOWER_V06/entities/*`.

- [ ] **Step 2: Extract storage-independent selectors**

Move queue/routing selection to pure functions over normalized `work` records. Do not rewrite governance semantics in the same task.

- [ ] **Step 3: Keep a compatibility reader for archived Tower state**

Legacy replay remains possible, but is not in the normal boot path.

- [ ] **Step 4: Run full NEXO Python suite**

```bash
python -m unittest discover runtime -p 'test_*.py' -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add runtime/nexo_agent_api runtime/nexo_view_api
git commit -m "refactor: decouple NEXO runtime from mutable Tower storage"
```

---

## Release Gates

Do not promote to production unless all of the following are demonstrated with receipts:

```text
R1 reconciliation conflicts = 0
R2 Drive internal export validates
R3 public export sanitization PASS
R4 deterministic hash replay PASS
R5 3-hour workflow manual run PASS
R6 unchanged state -> NO_CHANGE
R7 invalid export preserves last good projection
R8 scientific result ingest readback PASS
R9 Olympus private-field leak test PASS
R10 TOWER frozen and four core roles reading the new SSOT
```

## Rollback

Rollback is deliberately small:

1. Disable `materialize-ssot-pages.yml` schedule.
2. Restore the pre-cutover Drive spreadsheet copy only if canonical data itself was corrupted; otherwise leave data intact and revert authority markers.
3. Re-enable the frozen TOWER authority marker only through an explicit rollback decision.
4. Point the app back to the last known-good static View API artifact.
5. Scientific TCC workflows remain unchanged throughout, so compute does not require rollback.

## Recommended execution order

Execute Tasks 1-6 first and keep the entire system in SHADOW. Review the reconciliation report and static API in the app before enabling any write path. Then execute Task 7, verify with non-destructive fixtures, and perform Task 8 cutover only after the release gates pass. Task 9 is cleanup after stable operation, not a prerequisite for cutover.
