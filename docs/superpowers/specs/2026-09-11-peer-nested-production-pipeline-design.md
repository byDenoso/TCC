# PEER nested production pipeline redesign

Date: 2026-09-11
Status: Design approved in chat, pending written-spec review before implementation
Repository: `byDenoso/TCC`
Execution branch: `run-peer-segmented-20260911`

## 1. Objective

Rebuild the matched PEER nested-sampling execution path for M1 versus M3 so that the scientific model definition is immutable, the initial PolyChord bootstrap can exceed the GitHub-hosted runner time ceiling without corrupting methodology, later sampling can continue in bounded GitHub Actions segments, every continuation is cryptographically and scientifically validated, and a final Bayes-factor result is emitted only after both data evidence and prior-volume normalization pass explicit publication gates.

The redesign is intentionally conservative. Engineering may change. The scientific target must not silently change to make the runtime easier.

## 2. Existing literature and implementation baseline

This design does not introduce a new nested-sampling method.

Existing components used as-is:

- PolyChord / PolyChordLite for nested sampling.
- Cobaya 3.6.2 PolyChord wrapper and its standard evidence processing.
- Cobaya's `nprior` calibration of the unphysical fraction of prior volume.
- PolyChord resume files for post-bootstrap continuation.
- GitHub Actions artifacts as transient transport between hosted runners.
- The already validated CAMB 1.6.6 + CosmoRec 2.0.3 scientific runtime and the frozen ACT/Planck/BAO/SH0ES likelihood stack.

Cobaya documents `nprior=10nlive` as the default and recommends increasing it when the prior or likelihood contains a large unphysical region because the unphysical-volume correction is inferred from that sample. Therefore reducing `nprior` merely to fit a CI wall-clock limit is not treated as an engineering-only optimization.

### Proposed extension

The proposed work is execution orchestration around the standard sampler:

- separate the long, non-resumable bootstrap from later resumable sampling;
- encode an explicit execution state machine;
- add validated artifact restore/resume across ephemeral runners;
- make checkpoint promotion fail closed;
- isolate scientific configuration from execution configuration;
- add end-to-end resume tests and provenance manifests.

### Potential novelty

No scientific novelty is claimed. At most, the reusable orchestration pattern may be an engineering contribution for long-running nested samplers on ephemeral CI runners. It must not be described as a new inference formalism or a new evidence estimator.

## 3. Frozen scientific contract

The following science definition is immutable for the production comparison unless a separate scientific change is explicitly approved and receives a new campaign identifier.

### Models

- M1: ΛCDM + `A_lens`.
- M3: PEER + `A_lens`, with `peer_fede` sampled.

### Likelihood stack

- `act_dr6_cmbonly`
- `act_dr6_cmbonly.PlanckActCut`
- `planck_2018_lowl.TT`
- `planck_2018_lowl.EE_sroll2`
- `planck_2018_lensing.native`
- `bao.desi_dr2.desi_bao_all`
- `shoes_h0.SH0ESGaussian`

### Fixed PEER settings

- `peer_zc = 3.81`
- `peer_thetai = 2.89155`

### Priors that must remain exactly as defined by the frozen science source

- `tau`: retain the canonical campaign prior. Do not patch its lower bound in the workflow.
- `peer_fede`: `[0.0, 0.18]` for M3.
- `A_lens`: `[0.5, 1.5]` for M1 and M3.
- all remaining cosmological and calibration priors: inherit from the frozen science definition without runtime mutation.

### Sampler production target

- `nlive = 400` per model.
- production `nprior` must remain at the scientifically approved value. The previous historical `20nlive` setting is the conservative reference. Any change requires a separate validation campaign and must not be smuggled into the production workflow.
- production convergence criterion: remaining `dlogZ <= 0.1`.
- production and prior-volume seeds must be deterministic and recorded in the manifest.

A generated `science_manifest.json` must contain all model, likelihood, prior, fixed-parameter and sampler fields relevant to the evidence calculation. Its SHA256 becomes part of every checkpoint identity.

## 4. Runtime contract

The pipeline must use a single validated runtime identity rather than rebuilding or hot-patching the solver on every sampling segment.

Required runtime provenance:

- Python 3.11.
- Cobaya 3.6.2.
- CAMB 1.6.6.
- CosmoRec 2.0.3/2.0.3b payload matching the validated scientific runtime.
- PolyChordLite 1.20.1.
- ACT DR6 lite commit `627aeafb88ae5ad1aa66b406bea2d65cfa66a27d`.
- immutable hashes for CAMB shared library, CosmoRec databases and official likelihood payload.

The existing Portable CAMB/CosmoRec V2 provenance may be reused only after the production pipeline performs a cold-start smoke test of the complete matched likelihood stack, not merely a CAMB import.

Runtime identity is recorded in `runtime_manifest.json`. A continuation refuses to run if its runtime manifest does not match the checkpoint manifest.

## 5. Execution architecture

### 5.1 State machine

Each model lane has exactly four operational states:

1. `BOOTSTRAP_REQUIRED`
2. `RESUMABLE`
3. `COMPLETE`
4. `FAILED`

There is no ambiguous "timeout but green" state.

State transition rules:

- no valid data `.resume` -> `BOOTSTRAP_REQUIRED`;
- valid `.resume` + matching manifests/hashes -> `RESUMABLE`;
- valid final `.stats`, valid evidence output and convergence gate passed -> `COMPLETE`;
- any manifest mismatch, corrupted checkpoint, incompatible runtime, non-recoverable sampler error or timeout with no valid resume -> `FAILED`.

A wall-clock timeout exit code is not success by itself.

### 5.2 Bootstrap stage

The first PolyChord stage is allowed to exceed the GitHub-hosted runner ceiling because current evidence shows the sampler can spend more than one hosted-run window generating prior/live points before producing a resumable data state.

The bootstrap must run in an execution environment that:

- has no approximately six-hour hard job limit;
- uses the exact frozen science manifest and runtime manifest;
- stores output on persistent disk during the process;
- periodically inspects the raw PolyChord directory;
- promotes a checkpoint only when a valid data resume state exists;
- may continue beyond 5h30 until either a valid resumable state exists or the run fails scientifically/technically.

The bootstrap does not alter priors, `nprior`, `nlive`, likelihoods or precision to fit a wall-clock budget.

After a valid resume state appears, the bootstrap exports a compact checkpoint bundle and terminates cleanly. From then on, GitHub Actions becomes eligible for segmented continuation.

### 5.3 GitHub continuation stage

Each hosted segment runs for at most about 5h20 of sampler time, leaving margin for setup, checkpoint validation, graceful stop, packaging and artifact upload within the GitHub job ceiling.

Each segment performs this sequence:

1. checkout orchestration code;
2. materialize and validate the frozen runtime;
3. download exactly one previous checkpoint bundle for that model;
4. verify schema, model, science-manifest hash, runtime-manifest hash, seed, PolyChord settings and file hashes;
5. restore the raw PolyChord state to the exact output prefix expected by Cobaya;
6. set resume semantics without forcing output deletion;
7. run a short resume smoke test or structural preflight that does not advance the scientific chain materially;
8. run the bounded data segment;
9. stop with a controlled termination path before the outer job timeout;
10. snapshot only after the sampler process is no longer writing;
11. validate the newly produced checkpoint;
12. upload the compact checkpoint bundle and readback report;
13. classify the lane as `RESUMABLE`, `COMPLETE` or `FAILED`.

If the run completes naturally, the final evidence files are parsed immediately and the lane enters `COMPLETE` only after validation.

## 6. Checkpoint bundle

The artifact passed between segments contains only state required to resume or verify the scientific run.

Required contents:

- raw PolyChord resume files;
- raw live/dead state files required by PolyChord resume;
- Cobaya `input` and `updated` YAML needed to prove compatibility;
- final `.stats` if present;
- `science_manifest.json`;
- `runtime_manifest.json`;
- `checkpoint_manifest.json` with per-file SHA256 and sizes;
- `segment_status.json`;
- compact stdout/stderr tails plus full compressed sampler logs when feasible.

Excluded contents:

- CAMB/CosmoRec runtime payload;
- official likelihood packages;
- source checkouts;
- package caches;
- unrelated previous evidence directories.

The checkpoint artifact should therefore be substantially smaller than the approximately 70 MB artifacts produced by earlier workflows.

## 7. Checkpoint consistency

Checkpoint creation is fail-closed.

The sampler process must be stopped or allowed to exit before the canonical promoted snapshot is created. Periodic watcher snapshots may be used only for diagnostics and emergency recovery candidates; they are not automatically promoted as canonical checkpoints while the sampler may still be writing.

Promotion requires:

- at least one expected `.resume` file;
- all required companion files present;
- non-zero file sizes where applicable;
- successful SHA256 computation;
- exact output prefix match;
- manifest compatibility;
- no active sampler process writing to the source directory.

The promoted snapshot is built in a temporary directory and renamed atomically after validation.

## 8. Restore semantics

Restore is a first-class operation, not an incidental `cp` command.

A restore command must:

- unpack a checkpoint into a temporary directory;
- verify all hashes before modifying the destination;
- verify model and manifest identity;
- reject path traversal or unexpected files;
- restore to a clean raw-output destination;
- preserve the exact PolyChord file root expected by Cobaya;
- set Cobaya/PolyChord to resume mode and disable destructive force behavior;
- perform a post-restore readback before the sampler starts.

A failed restore leaves the previous destination untouched.

## 9. Prior-volume normalization

Prior-volume normalization is separated from the long data sampler and treated as its own reproducible scientific calculation.

For each model:

- use the same frozen model/likelihood prior definition relevant to the normalization method;
- store its own manifest and seed;
- run to its required precision independently;
- cache and reuse a verified normalization result only when its science-manifest identity matches exactly.

The final normalized evidence is computed only after both data and prior-volume evidence are complete.

For independent uncertainty estimates, propagation uses quadrature:

`σ_norm = sqrt(σ_data^2 + σ_prior^2)`

If the implementation intentionally uses a different covariance model, that covariance must be explicit and justified. A simple linear sum of standard deviations is not accepted as the default uncertainty propagation.

For the model comparison:

`ΔlogZ = logZ_norm(M3) - logZ_norm(M1)`

and, absent measured covariance between model evidence estimates:

`σ_Δ = sqrt(σ_M3^2 + σ_M1^2)`.

## 10. Workflow consolidation

The production path is consolidated into one canonical continuation workflow plus one bootstrap entrypoint. Historical workflows remain available as provenance until the new pipeline is validated, but they are not used as concurrent production authorities.

The canonical workflow must not modify historical Python source with `str.replace` at runtime. Production configuration is supplied through explicit parameters/config files with schema validation.

Triggers must include the orchestration code, tests and workflow file, so Python changes cannot silently fail to launch CI.

Use `concurrency` keyed by campaign + model to prevent two continuation jobs from advancing the same checkpoint lineage simultaneously.

## 11. Provenance and lineage

Every segment gets:

- campaign ID;
- model ID;
- segment ordinal;
- parent checkpoint digest;
- produced checkpoint digest;
- Git commit SHA;
- science-manifest SHA;
- runtime-manifest SHA;
- sampler settings;
- start/end UTC timestamps;
- exit classification;
- GitHub run/job IDs when executed on Actions.

This forms a single append-only lineage from bootstrap to final evidence.

A child checkpoint with the wrong parent digest is rejected.

## 12. Testing strategy

### Unit tests

- checkpoint inspection distinguishes bootstrap/live-only from resumable states;
- manifest hashing is deterministic;
- invalid or missing resume files fail promotion;
- restore rejects mismatched science/runtime/model hashes;
- restore rejects corrupted files;
- uncertainty propagation uses quadrature;
- state transition logic is exhaustive.

### Integration tests

Use a cheap toy likelihood with PolyChord to execute a real lifecycle:

1. start a sampler;
2. produce an actual PolyChord `.resume`;
3. terminate at a controlled boundary;
4. package checkpoint;
5. restore into a clean directory;
6. resume;
7. finish;
8. compare final result with an uninterrupted reference within expected sampler stochastic tolerance.

This test validates the actual Cobaya + PolyChord resume contract rather than synthetic files only.

### Production preflight

Before spending hours on M1/M3:

- materialize runtime;
- verify hashes;
- import CAMB/CosmoRec/PolyChord;
- run matched Cobaya `--test` for M1 and M3;
- generate science manifests;
- assert M1/M3 differ only in the intended model parameterization;
- assert no workflow-side prior mutation exists;
- assert artifact restore path works with a tiny fixture.

## 13. Failure handling

- dependency/bootstrap error before sampling: `FAILED`, no production checkpoint;
- outer timeout before valid resume exists: `FAILED`, bootstrap must continue in long-running environment rather than pretending the segment can resume;
- bounded continuation timeout with a validated post-stop resume: `RESUMABLE`;
- artifact upload failure: segment is not promoted; parent checkpoint remains canonical;
- manifest mismatch: hard fail before sampler execution;
- science configuration change: new campaign ID, never resume an old checkpoint;
- corrupted checkpoint: hard fail and retain last verified parent.

## 14. Performance optimizations allowed

Allowed because they do not alter the posterior target/evidence definition:

- reuse immutable validated runtime instead of rebuilding it;
- reuse immutable likelihood payload by hash;
- cache Python/PolyChord build dependencies where reproducible;
- reduce artifact scope to checkpoint state only;
- eliminate duplicate source checkouts when not needed;
- avoid running prior-volume normalization repeatedly when an identical verified result exists;
- parallelize M1 and M3 as independent lanes;
- leave thread oversubscription disabled;
- reserve setup/upload margin rather than letting GitHub kill the job first.

Not allowed as engineering optimizations:

- narrowing scientific priors;
- lowering `nprior` without separate evidence-bias validation;
- changing likelihood composition;
- changing `nlive`, evidence precision or PEER fixed parameters silently;
- using approximate evidence estimators as a replacement for the production nested result.

## 15. Acceptance criteria

The redesign is accepted only when all of the following are demonstrated with fresh evidence:

1. production science manifest matches the frozen campaign definition;
2. no workflow patches scientific priors or sampler evidence settings at runtime;
3. full matched runtime smoke tests pass for M1 and M3;
4. real PolyChord toy-run checkpoint -> artifact -> restore -> resume -> completion integration test passes;
5. bootstrap can produce and promote a valid M1/M3 data checkpoint in a long-running environment;
6. a GitHub continuation can consume that checkpoint and produce a child checkpoint with valid lineage;
7. timeout without checkpoint is classified `FAILED`, while controlled segment stop with checkpoint is `RESUMABLE`;
8. checkpoint artifact excludes runtime/likelihood payload and is materially smaller than legacy artifacts;
9. prior-volume normalization is reproducible and separately verified;
10. uncertainty propagation is corrected and tested;
11. final M1 and M3 results both satisfy the publication convergence gate;
12. final `ΔlogZ` is computed from matched, complete, normalized evidence only;
13. no result is persisted as canonical science state until the complete matched rerun and audit are finished.

## 16. Rollback

All implementation work remains isolated on an execution branch until validation. Historical workflows and artifacts are not deleted during migration. If the new pipeline fails acceptance, the branch can be abandoned without changing the canonical science definition or existing provenance.

No execution-only PR is merged without explicit user approval.

## 17. Non-goals

- inventing a new nested-sampling algorithm;
- changing PEER physics;
- reinterpreting previous incomplete evidence values as final;
- making GitHub Actions the scientific source of truth;
- introducing another NEXO kernel, memory or authority layer.
