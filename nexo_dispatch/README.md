# NEXO dispatch inbox

Each commit to `nexo/dispatch-runtime` may add exactly one JSON request under `nexo_dispatch/requests/`. Requests contain only non-secret execution metadata and select an adapter from the code allow-list. Arbitrary shell commands are not accepted. Results are emitted as GitHub Actions artifacts and remain non-canonical until NEXO verification and Drive readback.
