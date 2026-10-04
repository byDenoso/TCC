# NEXO state migration - stage 1

Status: executable shadow import, not a production cutover.

## Reconciled baseline

Built on TCC commit `0a89547e58a6c1a50b56a3c48060ad6c2947ac74`, after
PRs 127-130. Pantheon PR 412 supplies the existing operational MCP/Actions
control; open PR 413 repairs its Drive context scope. This stage does not
modify either integration, the Writer bundle, scientific recipes, Atlas,
credentials, automations, or the current operational authority. Existing
Atlas UI/performance work in Pantheon PRs 408, 409 and 411 is untouched.

## Model and preservation

`runtime/nexo_state/schema.sql` stores an immutable byte archive of the
captured source and every logical file. Typed `objects` hold complete payloads
and separately expose scientific, attempt-observation and review states.
The archive is recovery evidence, not an independently writable Tower.
Operational attempt ownership, new receipts and dispatch outbox are later
stages; historical battery observations must not be counted as new tests.
Reviews embedded in historical tests remain inside their full payloads.

No missing identity is generated. Mirrored IDs, missing/external references,
unknown encodings/fields and contradictory historical states survive and
appear in the inventory. A stale declared fingerprint is preserved and
reported, not repaired. Its presence requires a reconciliation decision
before cutover, not a weakened production admission rule. Paths are logical
keys and are never unpacked into arbitrary filesystem destinations.

The import accepts only a source with the existing live-Tower authority
contract, a matching caller-supplied raw SHA-256, and unambiguous bounded JSON.
The hash must be recorded independently at capture time; computing it from an
untrusted later download does not establish provenance. The source revision,
computed files digest and exact raw bytes are retained. Import uses one
transaction, is idempotent for identical bytes and rejects replacement with a
different capture. The operator must create a new shadow database for a new
capture, not overwrite a previous rehearsal.

## Commands

Run from the repository root, on a trusted service/operator filesystem:

```sh
python -m runtime.nexo_state.migration import --db /private/shadow.sqlite \
  --source /private/captured-tower.json --expected-sha256 "sha256:$CAPTURE_SHA256"
python -m runtime.nexo_state.migration inventory --db /private/shadow.sqlite
python -m runtime.nexo_state.migration compare --db /private/shadow.sqlite \
  --source /private/captured-tower.json
python -m runtime.nexo_state.migration export --db /private/shadow.sqlite \
  --destination /private/exported-tower.json
python -m runtime.nexo_state.migration backup --db /private/shadow.sqlite \
  --destination /private/backup.sqlite
python -m runtime.nexo_state.migration restore --db /private/backup.sqlite \
  --destination /private/restored.sqlite
python -m runtime.nexo_state.migration compare --db /private/restored.sqlite \
  --source /private/captured-tower.json
python -m pytest tests/test_nexo_state_migration.py -q
```

Use a persistent local filesystem with SQLite locking semantics. This CLI is
not an exposed HTTP server and never contacts Drive or Actions. It does not
assert that a selected cloud provider or automation credential works.
Keep captures, databases, exports and private reports out of Git. Never use a
public Actions artifact to transport the private Tower.

## Verification and limitations

Comparison covers all logical paths, every retained field and the wrapper,
not just counts. Raw source bytes remain directly verifiable in `snapshot`.
The exported JSON may use different whitespace; parsed JSON content and its
canonical digest must agree. Backup uses SQLite's Online Backup API, bounded
progress time, integrity/foreign-key checks and exclusive publication of a
new file. It does not copy a live `.db` while ignoring its WAL. Restoration
never replaces an existing database. Production backup storage and retention
on Drive, disk-full monitoring and restore drills on the chosen host remain
unconfigured.

The tests use synthetic data only. They cover lossless unknown-field/gzip
roundtrips, historical contradictions, mirrored/missing IDs, hash mismatch,
invalid paths/JSON, replay/conflict, atomic rollback on injected failure,
concurrent import, immutable archive, committed versus uncommitted WAL data,
bounded backup failure, restoration and schema/corruption rejection.

**Not yet a production rollback exporter:** the export preserves the captured
wrapper. After future domain writes, a cutover/rollback tool must reconcile
all new records and events, regenerate the appropriate authority metadata and
validate the receiving system. Do not upload this export over the live Tower.

Remaining acceptance includes domain authorization/receipts/CAS, recovered
attempt fencing, durable Actions dispatch and callbacks, actual scheduled MCP
writes, scientific review/consolidation, Atlas agreement, and post-write
rollback rehearsal. No production authority, schedule or credential changes
are implied by merging this additive stage.
