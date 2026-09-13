# NEXO GitHub-native Orchestrator v0.1 — Implementation Status

Date: 2026-09-13
Branch: `nexo-gh-orchestrator-20260913`
Base: `run-peer-segmented-20260911`
Status: IMPLEMENTED ON FEATURE BRANCH, PENDING INTEGRATION

## Implemented

- Declarative campaign and result schemas.
- Strict campaign validation with executor/validator registries.
- Dependency graph validation and cycle detection.
- Explicit campaign/test state machines.
- Deterministic planner with max-parallel and retry-budget enforcement.
- JSON-safe result envelopes with non-finite fail-closed behavior.
- Separate technical execution and scientific promotion states.
- Deterministic correlation IDs and duplicate-dispatch reuse/fail-closed logic.
- GitHub Actions REST client for workflow dispatch, run correlation, completion polling, artifact listing, and JSON artifact extraction.
- Campaign runner that preserves technical failure receipts.
- Cheap no-op executor and static pass/fail fixtures.
- `nexo-orchestrator.yml` with `dry_run=true` by default and least-privilege `contents: read`, `actions: write` permissions.
- CI contract with unit/structural tests plus an end-to-end dry-run.
- Operational documentation in `docs/nexo/ORCHESTRATION.md`.

## Implementation path deviation

The design/plan initially proposed Python modules under `scripts/nexo/`. The implemented package is `nexo_control/` because repository connector policy rejected writes under the proposed executable script path. The public interfaces and architecture are unchanged; only the package location differs.

## Fresh verification evidence

GitHub Actions run `34772323997` on commit `41d75c32abf712bc6765d0494b9466e0b3df2f07` completed successfully.

Evidence from the run:

- `python -m pytest -q tests/nexo`: **48 passed**.
- deterministic dry-run E2E: **PASS**.
- campaign `NEXO-NOOP-001`: 1 runnable prediction, 0 real dispatches in dry-run.
- declarative `.nexo` JSON/YAML parse: **PASS**.

Comparison with base `run-peer-segmented-20260911` shows the feature branch is ahead only by new NEXO control-plane files, tests, and documentation. No existing PEER scientific workflow, physics implementation, likelihood, prior, or SSOT logic is modified by v0.1.

## Remaining integration gate

The real child `workflow_dispatch` path is intentionally not claimed as live-proven on the feature branch. GitHub requires workflow-dispatch availability through the repository's registered workflow surface; the no-op executor is new in this branch. After integration, the first production-side check is:

1. run `NEXO GitHub orchestrator` with the example campaign and `dry_run=true`;
2. inspect the campaign receipt;
3. run the same example with `dry_run=false`;
4. confirm exact correlation to one no-op child run, artifact retrieval, normalized result envelope, and `ready_for_learning=true`.

No CAMB/MCMC workflow should enter the executor registry until that cheap live dispatch check passes.
