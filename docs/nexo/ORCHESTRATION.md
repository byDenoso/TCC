# NEXO GitHub-native Orchestration v0.1

NEXO v0.1 uses GitHub Actions as an operational control plane. It does not replace the scientific SSOT, change PEER physics, or require an always-on VM.

## What is implemented

The control plane lives in four repository surfaces:

- `.nexo/`: declarative campaign/result schemas, fixtures, and campaign manifests.
- `nexo_control/`: validation, dependency planning, state transitions, dispatch registry, GitHub Actions API client, result normalization, validators, and campaign runner.
- `.github/workflows/nexo-orchestrator.yml`: manual orchestrator entry point.
- `.github/workflows/nexo-contract.yml`: TDD/contract CI plus a real dry-run path that proves planning emits zero dispatches.

Existing scientific workflows are untouched in v0.1.

## Campaign lifecycle

A campaign manifest is validated as data, then converted into a deterministic execution plan. Only executor aliases and validators registered in repository code are accepted. Arbitrary shell commands in manifests are rejected.

Campaign states are explicit: `PLANNED -> READY -> RUNNING -> VALIDATING -> LEARNING -> CLOSED`, with `BLOCKED` and `FAILED` branches.

Test states are explicit: `PLANNED -> READY -> DISPATCHED -> RUNNING -> VALIDATING -> PASSED`, with terminal `NOT_PROMOTED`, `FAILED`, or `BLOCKED` outcomes.

A successful GitHub Actions job is not equivalent to scientific promotion. `PASSED` is only emitted by a registered promotion validator.

## Dry-run

The orchestrator defaults to `dry_run=true`. Dry-run validates the campaign, dependency graph, budgets, registry membership, and predicted dispatches, then writes a receipt without launching a child workflow.

The CI contract runs the same dry-run path on `.nexo/campaigns/example-noop.yaml` and asserts:

- the plan is marked dry-run;
- `dispatches` is empty;
- exactly one no-op execution is predicted;
- executed dispatch count is zero;
- a `ready_for_learning` field exists in the campaign summary.

## Execution

When `dry_run=false`, the runner uses the GitHub Actions REST API directly. It never constructs arbitrary shell commands from campaign data.

The v0.1 executor registry contains one adapter:

`nexo_noop -> .github/workflows/nexo-noop-executor.yml`

Every dispatch receives a deterministic correlation ID:

`NEXO_<campaign>_<test>_<attempt>_<commit8>`

Before dispatching, the runner checks for an existing workflow run with the exact correlation ID and ref. A single existing run is reused, zero matches triggers one dispatch, and multiple matches fail closed. This makes a repeated attempt idempotent rather than blindly spawning duplicate work.

The runner waits for the exact correlated run, waits for completion, resolves the exact expected artifact, reads `executor-result.json`, runs the registered validator, and emits a normalized result envelope.

## Result receipts

Each test result contains:

- campaign/test identity;
- workflow name and exact run ID;
- executor head SHA;
- artifact names;
- validation status and metrics;
- campaign commit and validator commit.

Non-finite values are converted to JSON `null` and cannot silently become valid scientific diagnostics.

Technical errors are persisted as `FAILED` result envelopes instead of losing the execution receipt. Scientific gate failures are `NOT_PROMOTED`, which stays distinct from infrastructure failure.

## Learning handoff

`campaign-summary.json` contains `ready_for_learning`. It becomes true only when all executed tests have terminal non-technical outcomes (`PASSED` or `NOT_PROMOTED`). `FAILED` or unresolved execution keeps it false.

v0.1 stops at this machine-readable handoff. It does not write automatically to Sheets/Drive/Slack and does not invoke an LLM. Those integrations should consume the stable receipt contract after the control plane is merged and proven.

## Running it

From GitHub Actions, open `NEXO GitHub orchestrator` and use `workflow_dispatch`.

For the first run, keep:

- campaign path: `.nexo/campaigns/example-noop.yaml`
- dry run: `true`
- attempt: `1`

Inspect the uploaded `nexo-campaign-receipt-<run_id>` artifact. Only after dry-run is clean should the same campaign be run with `dry_run=false`.

## Adding an executor

Adding a scientific executor requires all of the following before automatic dispatch is allowed:

1. add a stable alias to `WORKFLOW_REGISTRY`;
2. ensure the target workflow accepts deterministic correlation metadata;
3. provide a machine-readable artifact contract;
4. add or select a registered validator;
5. add unit/structural tests;
6. pass dry-run before production execution.

A workflow that cannot be correlated to one exact run is not eligible for NEXO automatic dispatch.

## Current v0.1 boundary

The no-op executor proves the orchestration plumbing cheaply. Scientific workflows such as CAMB/MCMC remain outside the registry until an adapter is deliberately added and tested. That avoids using multi-hour compute as a glorified integration test, a surprisingly easy way to turn cloud credits into decorative smoke.
