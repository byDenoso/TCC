# NEXO dispatch inbox

Each commit to `nexo/dispatch-runtime` may add exactly one JSON request under `nexo_dispatch/requests/`. Requests contain only non-secret execution metadata and select an adapter from the code allow-list. Arbitrary shell commands are not accepted.

Scientific intake uses the **TOWER_FIRST_DISPATCH** invariant. A request for `nexo_submit_scientific_tests_v1` is eligible for this inbox only after the corresponding TEST exists in `byDenoso/NEXO-Obsidian-Vault@main:TOWER_V06` and exact readback has confirmed its fingerprint and READY state.

One scientific TEST maps to one dispatch-request commit. Multiple tests from one chat message are therefore persisted independently and dispatched as independent commits so the workflow's exactly-one-request guard remains meaningful.

Results are emitted as GitHub Actions artifacts and remain non-canonical until NEXO verifies identity/schema/hash and persists RESULT/EVIDENCE back to Tower with exact readback. Hourly Autoconsistente reconciliation is a fallback; hosted event-driven closure is the target production path.
