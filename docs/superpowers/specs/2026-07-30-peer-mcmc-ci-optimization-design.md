# PEER MCMC CI Optimization Design

## Goal

Reduce GitHub Actions queue pressure, repeated environment setup, lost work on runner termination, and wasted MCMC evaluations without changing any likelihood, prior, cosmological parameterization, or promotion threshold.

## Scope

The first implementation targets the native ACT DR6 PEER N3 posterior campaign for M2 and M3. The optimization layer is deliberately separated from the scientific branch so it can later be reused by SPT and matched-quartet workflows.

## Scientific invariants

- Preserve the ACT DR6 + Planck low-l + Planck lensing + DESI DR2 BAO + SH0ES stack.
- Preserve `peer_fede`, `A_lens`, `peer_zc`, `peer_thetai`, calibration priors, parameter bounds, and CAMB 1.6.6 + CosmoRec.
- Preserve 20 chains per model.
- Promotion remains fail-closed and requires all 20 chains, native Cobaya convergence, rank-normalized split R-hat minus one below 0.01, bulk ESS above 1000, and tail ESS above 500.
- No surrogate likelihood and no reuse of samples across different models or likelihood stacks.

## Architecture

### 1. One immutable runtime cache

A preflight job constructs `.peer-runtime` once per frozen scientific hash. The cache contains the Python virtual environment, pinned ACT likelihood wheel, byte-verified CAMB wheel, official likelihood packages, CosmoRec databases, and copied GSL runtime libraries. Shard jobs restore this cache instead of repeating apt, pip, artifact downloads, and ACT cloning.

The cache key includes the source run ID, ACT commit, Python version, Cobaya version, and the runtime action hash. An exact miss rebuilds the cache. Partial restore keys are not used for scientific binaries.

### 2. Five-runner ceiling

The campaign retains five shards per model with four MPI chains per shard, but sets `max-parallel: 5` across the full model-shard matrix. This matches the user's runner budget and prevents queue multiplication.

### 3. Segmented resumable MCMC

Each shard runs up to four 65-minute segments. The first segment uses `force: true`; subsequent segments use `resume: true`. After each segment, an independent diagnostic reads chains and the native checkpoint. A converged shard exits early. A workflow input can point to a previous run ID and restore shard artifacts for cross-run resume.

### 4. Better sampler geometry

The target distribution is unchanged. Sampling uses Cobaya's supported fast/slow machinery:

- `measure_speeds: true`;
- `drag: true`;
- `oversample_power: 0.4`;
- `proposal_scale: 1.9`;
- `learn_proposal: true`;
- `burn_in: 50`;
- `Rminus1_stop: 0.01`;
- `Rminus1_cl_stop: 0.05`.

These settings alter proposal efficiency only, not the posterior.

### 5. Independent global gate

A repository-local diagnostic reconstructs Cobaya's run-length encoded traces, computes rank R-hat, bulk/tail ESS and relative MCSE using ArviZ, and refuses promotion when a diagnostic is missing or non-finite. The global 20-chain gate is stricter than any single shard's native checkpoint.

### 6. Queue hygiene

The workflow uses a concurrency group with `cancel-in-progress: false`. It permits one active and one pending campaign for the same ref, preventing successive commits from creating an unbounded queue while preserving the active scientific run.

## Error handling

- Cache mismatch or failed binary verification stops before sampling.
- Missing prior-run artifact during requested resume stops the shard rather than silently starting fresh.
- A timed-out segment uploads its checkpoint and chains.
- Missing or empty chains remain `INCOMPLETE`.
- Non-finite diagnostics are serialized as JSON `null` and cannot pass the gate.

## Testing

Pure tests cover run-length expansion, rank-diagnostic pass/fail fixtures, MCSE and ESS thresholds, checkpoint parsing, and sampler-config invariants. Workflow structure tests verify the five-runner ceiling, cache use, segmented resume, exact model list, and unchanged scientific assertions.

## Deliberate non-goals

- No Docker/GHCR image in this first iteration. The immutable cache provides most of the setup benefit without creating a second runtime authority.
- No automatic cancellation of an active scientific run.
- No reduction in chain count or weakening of convergence gates.
