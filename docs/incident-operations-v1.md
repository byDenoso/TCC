# Incident operations v1

Incident learning and operational recovery are independent. Existing `state` and
`next_owner` retain their learning semantics; `learning_state` and
`learning_next_owner` are explicit aliases. No scientific verdict, frozen TEST
criterion, recovery routing or ACK mutation rule changes.

## Read-time projection

`evolution.incidents[].operational` is derived from current canonical entities.
It is not a queue, creates no WORK, and does not persist an operational status
that could become stale between Writer reconciliation and publication.

- `policy`: `INCIDENT_OPERATIONS_V1`
- `state`: `UNLINKED`, `OPEN`, or `RESOLVED`
- `work_ids`: existing linked WORK identities
- `items`: `{work_id, test_id, current_owner, assigned_to, ownership_state,
  accepted, validation_state}`
- `ownership_state`: `ACCEPTED`, `ASSIGNED_UNACCEPTED`, or `UNRECORDED`
- `validation_state`: `PENDING`, `EVIDENCE_REQUIRED`, `REVALIDATION_REQUIRED`,
  or `PREREQUISITES_VALIDATED`
- `suggested_owner`: cause-based routing suggestion only when no visible WORK
  is linked; it does not establish assignment or acceptance
- `reason_code`: reviewed code below, otherwise `OTHER`
- `next_action_code`: `LINK_EXISTING_WORK`, `COMPLETE_RECOVERY`,
  `VERIFY_INCIDENT_CRITERION`, or `RESOLVED`
- `resolution_scope`: `EXECUTION_PREREQUISITES` when resolved, otherwise null
- `scientific_effect`: always `NONE`

The private view additionally lists `unresolved_refs`. Public projection excludes
private WORK and private or missing linked TESTs. It never serializes handoff
IDs, acceptance receipts, source links, candidate artifact references, raw causes,
free-text next actions, private evidence, or unresolved references. Role values
and public cause/action codes are allowlisted.

## Canonical linkage and ownership

Links come from exact signal `work_id` / `work_ids`, TEST-to-WORK references,
WORK `incident_id` / `linked_incident_ids`, or WORK-to-TEST references matching
the incident's TEST identities. Referenced entities must exist. Topic similarity,
same owner, error text and a later successful run never establish a link.
Open legacy incidents recover explicit WORK references from their own existing
signal artifacts. Closed incident evidence remains frozen.

`current_owner` is canonical WORK ownership. `assigned_to` is the current recovery
target. `accepted` requires the canonical private ACK event, matching WORK,
acceptance source, frozen recovery identity and route generation, using the same
checks as the handoff implementation. An assignment or fabricated acceptance
label alone cannot establish acceptance. Public summaries contain no ACK details.

Existing recovery routes remain authoritative: definition/conflict → LEARNER;
recipe/preflight → ADVISOR; inputs → EXECUTOR. A visible linked recovery supersedes
a general cause suggestion.

## Bounded operational resolution

Only `INPUT_PROVENANCE_INCOMPLETE`, `RECIPE_BINDING_MISSING`,
`RECIPE_OR_SMOKE_MISSING` and `RECIPE_OR_SMOKE_INVALID` are resolved by the existing
readiness verifier. Every linked WORK must be DONE with `READINESS_VALIDATED`
evidence bound to the same TEST, preregistration hash, recovery fingerprint and
recipe hash, and prerequisites must pass again at projection time. A terminal
TEST is not schedulable, but `TERMINAL_TEST` alone does not invalidate an already
verified prerequisite repair; all other readiness blockers still prevent closure. All incident TEST
references must be covered. Missing, stale or incomplete evidence leaves it open.
The check attests recorded prerequisites, not remote bytes or a scientific result.

The five historical codes are also public, but require their own stronger
criterion and never resolve from a prerequisite repair or PROMOTED alone:

- `INDEPENDENT_EVALUATORS_UNAVAILABLE`: independent eligible assessments
- `RUNNER_ARTIFACT_EXECUTOR_UNAVAILABLE`: same-run artifact provenance/read-back
- `PRE_RESULT_TEMPORAL_ORDER_UNRESOLVED`: canonical pre-result temporal order
- `EMPTY_FRONTIER_ACTIVE_ROADMAP`: verified roadmap frontier condition
- `READY_INPUTS_NOT_MATERIALIZED`: verified materialization, beyond recorded binding

Until a cause-specific verifier is implemented and evidence exists, these stay
OPEN or UNLINKED. A later run or learning lesson does not silently close them.
This version intentionally does not backfill missing real-world WORK links or
write the live Tower.

## Offline verification

Run `python -m pytest tests runtime/nexo_agent_api runtime/nexo_execution -q` and
`python scripts/build_gpt_writer_bundle.py`. The focused suite is
`python -m unittest tests.test_incident_operations -v`.
