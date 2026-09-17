# Portable CAMB Execution Capability Design

## Goal

Make `peer.camb.exact_v2` an executable, fail-closed scientific runtime capability for NEXO jobs, including GitHub Actions, without changing frozen scientific contracts or silently falling back to an unpinned CAMB installation.

## Architecture

`ExecutionContract` gains an optional `required_capabilities` list. Before executing a task, the runtime resolves each required capability through a small execution-capability registry. `peer.camb.exact_v2` resolves to a portable-runtime adapter that verifies `PORT_MANIFEST.v2.json`, materializes the immutable runtime payload from an explicit archive source, verifies the archive and `camblib.so` hashes, and exposes a launcher path through environment variables.

The task command itself remains frozen. Tasks opt in only by declaring `required_capabilities: ["peer.camb.exact_v2"]`. The executor injects `NEXO_CAPABILITY_PEER_CAMB_EXACT_V2_LAUNCHER` and related provenance variables. A task that requires exact CAMB must fail before scientific execution if the capability cannot be verified.

## Capability source policy

Resolution order is deterministic:

1. already-expanded local runtime under `runtime/portable_camb/payload` when hashes verify;
2. explicit immutable archive path from `NEXO_PEER_CAMB_ARCHIVE`;
3. explicit immutable archive URL from `NEXO_PEER_CAMB_ARCHIVE_URL`.

No implicit `pip install camb`, system CAMB, alternate solver, or network search is permitted. The expected archive SHA256, CAMB/CosmoRec versions, and `camblib.so` SHA256 come from `PORT_MANIFEST.v2.json`/canonical metadata and are verified before use.

## GitHub Actions

`nexo-execution.yml` continues to run `runtime.nexo_execution.runner`. Capability materialization happens inside the runner before the task starts, so workflow logic stays generic. GitHub jobs that need the portable runtime must provide `NEXO_PEER_CAMB_ARCHIVE_URL` or a pre-expanded verified payload. Secrets are not embedded in contracts.

## Compatibility

Existing v1/v2 contracts without `required_capabilities` behave exactly as before. Capability resolution is execution infrastructure only and does not alter task parameters, seeds, datasets, likelihood definitions, gates, or decision rules.

## Verification

Tests must prove: contracts parse without the new field; required capability is prepared before task execution; exact-CAMB jobs fail closed when the payload is absent or hash-invalid; verified payload exports the launcher/provenance environment; tasks not requiring CAMB never materialize it.