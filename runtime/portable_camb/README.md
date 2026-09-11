# Portable CAMB / CosmoRec runtime

Canonical source/provenance for the Portable CAMB cold-start launcher repair.

## V2 2026-09-11

- scientific payload unchanged from `PEER_CAMB_PLATFORM_PORT_20260802`
- original archive SHA256: `c2b7a5dc64bf437e10e5136a72a8bab3bbe33702ef89f6a1bc4c4f96711e1121`
- V2 archive SHA256: `b56341c3b7b0183a24a6172c5b82c6f90a07941231692c6a287129815973ccc8`
- V2 Drive file: `1lh9G1cCPjcA9F9CtPHSx_JU_tmVp_AVH`
- `camblib.so` SHA256 unchanged: `1945f5fc40acb8ed954b587c40691ec5f4743bf21af051ee5ec0b02413222ad9`
- CAMB 1.6.6 / CosmoRec 2.0.3
- launcher SHA256: `8287536468790c22000a5610cc5540ae5f14a9ae102b42fe00c906ae182eb75f`
- manifest SHA256: `b6a112e97c48aeec3fce03f16766a05c5bf660840b56c82b3ea259eed4ab4263`

Observed compiled/runtime relocation prefixes resolved by the launcher:

- `/tmp/peer-camb-runtime-xx`
- `/home/runner/worer/work/TCC/TCC`
- `/home/runner/work/TCC/TCC`

The launcher creates missing aliases to the bundled `cosmorec` tree and fails closed if an existing path is not the expected symlink.

Verification performed locally before promotion:

- 383 non-wrapper/non-manifest files byte-identical to the original archive
- deterministic archive rebuild SHA match
- fresh archive extraction cold-start replay x2
- identical outputs on both runs: age `13.792469149904035`, rdrag `147.06890381937413`, thetastar `1.0412400262761543`
- conflict test exits 70 and preserves the conflicting path

GitHub is source/provenance only. Scientific compute authority remains NEXO_RUNTIME and persistent evidence remains Drive + readback.
