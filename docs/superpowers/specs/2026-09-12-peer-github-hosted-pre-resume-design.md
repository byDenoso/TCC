# PEER GitHub-hosted pre-resume bootstrap design

Date: 2026-09-12
Status: Approved in chat for implementation
Repository: `byDenoso/TCC`
Execution branch: `run-peer-segmented-20260911`

## Goal

Run the frozen M1/M3 production bootstrap entirely on GitHub-hosted runners without reducing `nlive`, `nprior`, likelihood content, priors, fixed PEER parameters, or evidence precision.

## Existing behavior

PolyChordLite 1.20.1 writes its native `.resume` only after `GenerateLivePoints` finishes. With production `nlive=400` and `nprior=20nlive`, the matched PEER likelihood can remain in this phase longer than one GitHub-hosted job. `_phys_live.txt` is monitoring output, not a sufficient native resume state.

## Extension

Patch only the execution behavior of pinned PolyChordLite 1.20.1. During `GenerateLivePoints`, a hosted segment may stop at a deterministic valid-point budget before `nprior` is reached. The patch writes a dedicated pre-resume bootstrap state containing all accepted live-point rows plus cumulative attempt counters, generation ordering and timing diagnostics. A later hosted segment reloads this state, deterministically fast-forwards the root RNG from the unchanged sampler seed, and continues generating prior/live points.

When `nprior` is finally reached, the patched path returns to unmodified PolyChord flow. PolyChord then writes its standard prior metadata and native `.resume`; all later continuation uses the already-verified native checkpoint pipeline.

## Scientific invariants

The patch MUST NOT alter the target distribution or evidence settings. Production remains:

- M1 = ΛCDM + `Alens`.
- M3 = PEER + `Alens`, `peer_fede` sampled.
- `tau=[0.0,0.10]`.
- `Alens=[0.5,1.5]`.
- `peer_fede=[0.0,0.18]` for M3.
- `peer_zc=3.81`, `peer_thetai=2.89155`.
- full frozen ACT/Planck/lensing/DESI/SH0ES likelihood stack.
- `nlive=400`.
- `nprior=20nlive`.
- `precision_criterion=0.001`.
- explicit deterministic seed per model.

The bootstrap segment budget is execution metadata and is excluded from the science manifest.

## Bootstrap state contract

A pre-resume state is valid only when written after all MPI workers have been drained for that segment. It records:

- schema/version marker;
- `nDims`, `nDerived`, `nlive`, `nprior` compatibility values;
- number of accepted live points;
- cumulative attempted prior points (`ndiscarded` semantics);
- next generation-order identifier;
- cumulative valid likelihood-call count;
- cumulative timing diagnostic;
- every accepted `RTI%live` row including birth-order field.

On restore, dimension/settings mismatches are hard failures. The process is initialized with the same seed and the root RNG is advanced by the cumulative number of attempted prior draws before new draws are requested.

## Segment semantics

`POLYCHORD_BOOTSTRAP_SEGMENT_VALID=N` is the only new execution control. For a restored state with `k` accepted points, the current segment target is `min(nprior, k+N)`.

If the target is below `nprior`, all workers are drained, cumulative counters are reduced, the bootstrap state is atomically replaced, and the sampler exits with a dedicated checkpoint exit code. GitHub treats this as `BOOTSTRAP_REQUIRED`, not success or failure.

If the target reaches `nprior`, the bootstrap state is deleted after successful completion of live-point generation and standard PolyChord execution proceeds until a stable native `.resume` exists. At that point the existing checkpoint manager promotes the standard resume bundle.

## GitHub orchestration

A canonical hosted-bootstrap workflow runs one model per workflow run and self-dispatches the next segment with `actions: write` when classification remains `BOOTSTRAP_REQUIRED`. The first push/launcher starts M1 and M3 independently. Each run stays comfortably below the six-hour hosted-job ceiling by using a conservative accepted-point budget and preserves one artifact lineage per model.

The workflow pins the PolyChordLite source/version, applies the repository patch, compiles it, restores the previous pre-resume artifact when present, validates science/runtime identity, runs the segment, uploads the compact state, and dispatches the child segment. A maximum segment ordinal prevents infinite recursion.

## Validation

Required before production launch:

1. unit tests for patch application and state classification;
2. compile the patched PolyChordLite 1.20.1 on Ubuntu 24.04;
3. toy-likelihood E2E: uninterrupted reference vs at least two pre-resume segments followed by native resume; compare final evidence within deterministic/numerical tolerance and confirm the segmented path reaches the same accepted prior sequence for a fixed seed;
4. existing 42-test production gate remains green;
5. no workflow-side science mutation is introduced.

## Novelty classification

Existing literature/software: nested sampling, PolyChord live-point generation, Cobaya unphysical-volume correction and native PolyChord resume.

Proposed extension: engineering-only resumability of PolyChord's initial live/prior generation on ephemeral CI runners.

Potential novelty: none claimed scientifically. The patch is infrastructure and must not be presented as a new inference method.
