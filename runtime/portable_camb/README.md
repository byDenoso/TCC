# Portable CAMB / CosmoRec runtime

Canonical source/provenance and executable adapter for the Portable CAMB cold-start launcher repair.

## V2 2026-09-11

- scientific payload unchanged from `PEER_CAMB_PLATFORM_PORT_20260802`
- original archive SHA256: `c2b7a5dc64bf437e10e5136a72a8bab3bbe33702ef89f6a1bc4c4f96711e1121`
- V2 archive SHA256: `b56341c3b7b0183a24a6172c5b82c6f90a07941231692c6a287129815973ccc8`
- V2 Drive file: `1lh9G1cCPjcA9F9CtPHSx_JU_tmVp_AVH`
- `camblib.so` SHA256 unchanged: `1945f5fc40acb8ed954b587c40691ec5f4743bf21af051ee5ec0b02413222ad9`
- CAMB 1.6.6 / CosmoRec 2.0.3
- launcher SHA256: `8287536468790c22000a5610cc5540ae5f14a9ae102b42fe00c906ae182eb75f`

## NEXO execution capability

Execution contracts may opt in with:

```json
"required_capabilities": ["peer.camb.exact_v2"]
```

Before the scientific task starts, `runtime.nexo_execution.core.LocalProvider` resolves the capability through `runtime.portable_camb.runtime.prepare_portable_camb`. The adapter exports:

- `NEXO_CAPABILITY_PEER_CAMB_EXACT_V2=READY`
- `NEXO_CAPABILITY_PEER_CAMB_EXACT_V2_LAUNCHER`
- `NEXO_PEER_CAMB_RUNTIME_ROOT`
- `NEXO_PEER_CAMB_VERSION`
- `NEXO_PEER_COSMOREC_VERSION`
- `NEXO_PEER_CAMB_ARCHIVE_SHA256`
- `NEXO_PEER_CAMB_CAMBLIB_SHA256`

Source resolution is deterministic and fail-closed. A verified expanded `runtime/portable_camb/payload` may be used directly. Otherwise an exact archive must be supplied through `NEXO_PEER_CAMB_ARCHIVE` or `NEXO_PEER_CAMB_ARCHIVE_URL`. The archive SHA256 and `camblib.so` SHA256 are checked before task launch. There is no fallback to a system CAMB, `pip install camb`, or a different solver.

The V2 canonical archive is currently stored as a private Drive asset. GitHub Actions therefore requires an authenticated/pre-materialized archive source or an immutable runner-accessible mirror before a CAMB-requiring contract can execute there autonomously. The capability fails before scientific execution when that transport is absent.

Observed compiled/runtime relocation prefixes resolved by the launcher:

- `/tmp/peer-camb-runtime-xx`
- `/home/runner/worer/work/TCC/TCC`
- `/home/runner/work/TCC/TCC`

The launcher creates missing aliases to the bundled `cosmorec` tree and fails closed if an existing path is not the expected symlink.

Verification performed before promotion:

- 383 non-wrapper/non-manifest files byte-identical to the original archive
- deterministic archive rebuild SHA match
- fresh archive extraction cold-start replay x2
- identical outputs on both runs: age `13.792469149904035`, rdrag `147.06890381937413`, thetastar `1.0412400262761543`
- conflict test exits 70 and preserves the conflicting path

GitHub remains source/provenance and an execution surface. Canonical scientific state/evidence ownership remains governed by NEXO/TOWER and its readback rules.