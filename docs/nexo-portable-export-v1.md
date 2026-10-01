# NEXO portable export v1

This is an **offline recovery/inspection format**, independent of subscription,
activator count and hosting provider. It neither replaces the live Drive format
nor enables autonomous execution. No schema migration or live Tower write occurs.

## Run

Python 3.10+ and this TCC checkout are sufficient; no added packages or service.

```
python scripts/nexo_tower.py export --source private-snapshot.json --out private-export
python scripts/nexo_tower.py verify-export private-export --manifest-sha256 HASH_FROM_EXPORT
python scripts/nexo_tower.py restore private-export --dest empty-new-root --allow-incomplete
```

Omit `--source` only to use the existing authorized Drive transport. The export
records that transport's revision as `AUTHORIZED_DRIVE_HEAD`. Local input is a
frozen `LOCAL_BYTES_UNAUTHENTICATED` snapshot, not a claim about the current head;
hash verification proves byte integrity, not source authentication. Both routes
require the canonical Tower file identity. Destinations must not exist and are
reserved without replacing a path created concurrently. Publication is not an
atomic directory rename: verified children move under the reserved name; a
process crash can leave an incomplete destination that verification rejects and
a later run will not replace. Retain the returned
manifest hash separately: the sidecar is always checked, while the retained hash
also detects malicious replacement of both manifest and sidecar. Read-only permissions prevent accidental modification, not
an owner's deliberate chmod; these files are not WORM storage or encrypted.
Store them privately. Credentials are never collected from environment or account
stores. The existing snapshot itself must be reviewed before export if it may
contain credentials; do not send it to a public artifact store.

`--attachments mapping.json` maps known dependency IDs to already authorized local
files. Their bytes must match a pinned dependency SHA256. URLs and missing bytes
are not accepted as a completed download. The tool never fetches external data,
installs or executes the CAMB archive, or replays mutations/proposals.

## Verification boundary

The original source bytes are preserved verbatim. Both declared Tower hashes must
match recomputation; the tolerant legacy reader's stale-header warning is not
accepted here. Every embedded entry (JSON, text, base64) has a byte length/hash;
unknown encodings, unsafe paths, Windows-reserved names, case collisions and
file-versus-directory-prefix collisions fail closed before writing. IDs and named references are
inventoried with JSON pointers; the entire source, relationships, queues, receipts
and previously applied proposals remain byte/semantically intact. JSON entry
materialization is deterministic, not a claim to recover pre-bundle whitespace.

External dependency discovery currently covers the artifact registry and pinned
CAMB v2 archive. Coverage is explicitly PARTIAL_CONTRACT_CATALOG: execution
contracts, data_binding inputs and arbitrary attachments need a contract-specific
closure audit before declaring executable recovery. Merely finding a citation
must not trigger downloading papers (EVIDENCE_REFERENCE_V06 forbids corpus).
COMPLETE_KNOWN_DEPENDENCIES means only the catalogued bytes are present; it never
means every dependency is discovered, science can execute, or the whole system
is independently bootable. Missing known bytes produce INCOMPLETE_EXTERNAL_BYTES
and restore requires explicit `--allow-incomplete` for data-only inspection.

Restore creates a sealed read-only root with `.nexo-isolated.json` and a private
copy of the export. No writer, integration, schedule, executor or inbox application
is invoked. Applied receipts are evidence, never new execution requests. There
is deliberately no activation command. Re-enabling operation needs separate
review, fresh credentials through approved channels, dependency closure checks,
compatibility checks and explicit authorization. This is not an OS sandbox:
copying files elsewhere or changing permissions can deliberately bypass it.

## Hot/cold growth policy (proposal, no migration)

- Keep current mutable operational state and bounded indexes in the hot Tower
- Preserve historical scientific records by exact ID; archival age alone never
  authorizes deleting or changing their scientific status
- Future cold segments are immutable, content-addressed export objects with
  counts, byte lengths, hashes and ID-to-segment indexes, referenced by hot state
- Resolve references transparently across both tiers; no change to entity IDs,
  relationship semantics, evidence or applied-request deduplication
- Add projects/domains as contract-governed data; do not fork a platform per domain
- Activator presets 5/10 affect orchestration capacity, not storage or ID layout
- Measure bytes, load time and contract counts before choosing segment thresholds;
  Drive capacity alone does not establish runtime/API throughput
- Before any live switch: full dependency closure audit, clean offline restore,
  exact-ID/relationship/receipt parity, old-reader compatibility, CAS/readback and
  reversible cutover approved by owner

Current implementation is a full frozen snapshot, not incremental sharding. It
makes no promise that plan changes or 3–4 days unattended operation are safe;
those also require orchestration, budget, failure and recovery acceptance tests.
