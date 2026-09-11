# PEER Nested Production Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the M1/M3 PolyChord production path so frozen science is immutable, long bootstrap can run outside the GitHub-hosted ceiling, and every later GitHub segment performs validated restore → resume → stop → promote with reproducible evidence lineage.

**Architecture:** Move scientific identity, checkpoint state, restore/promotion, and evidence normalization into explicit Python modules under `peer_decisive_followups/`. Keep GitHub Actions as an orchestration layer only. The production workflow consumes a pre-existing validated bootstrap bundle, never mutates priors or sampler evidence settings, and emits compact child checkpoints or a final COMPLETE result.

**Tech Stack:** Python 3.11, pytest, PyYAML, Cobaya 3.6.2, PolyChordLite 1.20.1, CAMB 1.6.6 + CosmoRec, GitHub Actions, SHA256 manifests.

**Spec:** `docs/superpowers/specs/2026-09-11-peer-nested-production-pipeline-design.md`

## Global Constraints

- M1 = ΛCDM + `A_lens`; M3 = PEER + `A_lens` with `peer_fede` sampled.
- Likelihood stack is exactly ACT DR6 TTTEEE + PlanckActCut + Planck low-l TT + Sroll2 EE + Planck lensing + DESI DR2 BAO + SH0ES.
- `peer_zc=3.81`, `peer_thetai=2.89155`, `peer_fede=[0,0.18]`, `A_lens=[0.5,1.5]`.
- Do not patch `tau` or any other scientific prior in execution code.
- `nlive=400`; production `nprior=20nlive`; remaining `dlogZ <= 0.1` publication gate.
- Python 3.11, Cobaya 3.6.2, PolyChordLite 1.20.1, CAMB 1.6.6 + CosmoRec 2.0.3/2.0.3b, ACT-lite commit `627aeafb88ae5ad1aa66b406bea2d65cfa66a27d`.
- A timeout is RESUMABLE only if a validated data checkpoint exists after the sampler has stopped; otherwise FAILED.
- No execution-only PR merge without explicit approval.
- Do not persist incomplete/speculative evidence as canonical science state.

---

### Task 1: Freeze scientific identity and state machine

**Files:**
- Create: `peer_decisive_followups/production_contract.py`
- Create: `peer_decisive_followups/test_production_contract.py`

**Interfaces:**
- Produces: `build_science_manifest(model: str, config: dict) -> dict`, `canonical_json(data: dict) -> bytes`, `sha256_json(data: dict) -> str`, `classify_lane(*, complete: bool, resumable: bool, fatal: bool) -> str`, `quadrature(*sigmas: float) -> float`.

- [ ] Write failing tests asserting deterministic manifest hashes, rejection of model values outside M1/M3, state transitions, and quadrature uncertainty.
- [ ] Run `python -m pytest -q peer_decisive_followups/test_production_contract.py` and confirm failure.
- [ ] Implement the minimal deterministic contract/state helpers.
- [ ] Run the test file and confirm PASS.
- [ ] Commit `feat: freeze PEER production science contract`.

### Task 2: Build fail-closed checkpoint bundle and restore

**Files:**
- Replace: `peer_decisive_followups/checkpoint_manager.py`
- Replace: `peer_decisive_followups/test_checkpoint_manager.py`

**Interfaces:**
- Consumes: `sha256_json` from Task 1.
- Produces: `inspect_raw_checkpoint(raw: Path) -> dict`, `promote_checkpoint(...) -> dict`, `verify_bundle(bundle: Path, expected: dict) -> dict`, `restore_bundle(bundle: Path, destination: Path, expected: dict) -> dict`.

- [ ] Write failing tests for: live-only state not resumable; missing/zero-size `.resume` rejected; manifest mismatch rejected; corrupt file rejected; restore is atomic; unexpected/path-traversal entries rejected.
- [ ] Run checkpoint tests and confirm failure.
- [ ] Implement canonical bundle layout: `raw/`, `chain.input.yaml`, `chain.updated.yaml`, optional `chain.stats`, `science_manifest.json`, `runtime_manifest.json`, `checkpoint_manifest.json`, `segment_status.json`.
- [ ] Hash every promoted file and include `parent_checkpoint_digest`, `checkpoint_digest`, model, segment ordinal, science/runtime hashes.
- [ ] Restore only after complete verification into a temporary destination, then atomically replace destination.
- [ ] Run tests and confirm PASS.
- [ ] Commit `feat: add verified PEER checkpoint bundle lifecycle`.

### Task 3: Replace timeout wrapper with controlled segmented runner

**Files:**
- Replace: `peer_decisive_followups/run_segment.py`
- Create: `peer_decisive_followups/test_run_segment.py`

**Interfaces:**
- Consumes checkpoint manager from Task 2.
- Produces: `run_segment(command, ..., seconds, grace_seconds) -> dict` with classifications `COMPLETE`, `RESUMABLE`, `FAILED`.

- [ ] Write failing tests using a small child process that writes a synthetic resume file, covering controlled TERM, grace wait, post-stop promotion, and timeout-without-resume => FAILED.
- [ ] Run tests and confirm failure.
- [ ] Implement with `subprocess.Popen(start_new_session=True)`, monotonic deadline, SIGTERM to process group, bounded grace period, SIGKILL fallback, then snapshot only after process exit.
- [ ] Never return success solely because exit code is 124; classification derives from final complete/resumable/fatal state.
- [ ] Run tests and confirm PASS.
- [ ] Commit `feat: add controlled resumable PolyChord segments`.

### Task 4: Create explicit production config builder and preflight

**Files:**
- Create: `peer_decisive_followups/production_config.py`
- Create: `peer_decisive_followups/test_production_config.py`
- Modify: `peer_decisive_followups/orchestrate_segment.py`

**Interfaces:**
- Produces: `build_production_configs(science_dir, model, packages, root, seed) -> dict` and `validate_frozen_config(data_yaml: Path, model: str) -> dict`.

- [ ] Write failing tests proving no runtime `tau` mutation, `nlive==400`, `nprior=='20nlive'`, `precision_criterion<=0.1` target, expected likelihood set, fixed PEER values, intended M1/M3-only parameter differences, `resume=True`, `force=False` only for continuation.
- [ ] Run tests and confirm failure.
- [ ] Refactor orchestration so it imports/builds explicit config rather than `str.replace` patching historical source files.
- [ ] Make preflight emit `science_manifest.json` and reject any mismatch before sampling.
- [ ] Run tests and confirm PASS.
- [ ] Commit `refactor: make PEER production config explicit and immutable`.

### Task 5: Add bootstrap entrypoint and portable runtime contract

**Files:**
- Create: `peer_decisive_followups/bootstrap_production.py`
- Create: `peer_decisive_followups/runtime_contract.py`
- Create: `peer_decisive_followups/test_runtime_contract.py`

**Interfaces:**
- Produces: `build_runtime_manifest(...) -> dict`, `verify_runtime(...) -> dict`, CLI `python -m peer_decisive_followups.bootstrap_production ...`.

- [ ] Write failing tests for runtime-manifest determinism, CAMB/CosmoRec/ACT commit mismatch, and bootstrap refusal to promote before a real resumable checkpoint exists.
- [ ] Run tests and confirm failure.
- [ ] Implement long-running bootstrap with no internal 5h30 ceiling; same frozen science/sampler contract; persistent work directory; periodic diagnostics only; canonical promotion only after sampler exit/pause and valid `.resume`.
- [ ] Reuse the validated portable runtime identity where available; require full matched Cobaya preflight for M1/M3 before production bootstrap.
- [ ] Run tests and confirm PASS.
- [ ] Commit `feat: add long-running PEER production bootstrap`.

### Task 6: Separate prior normalization and final evidence calculation

**Files:**
- Create: `peer_decisive_followups/evidence.py`
- Create: `peer_decisive_followups/test_evidence.py`

**Interfaces:**
- Produces: `normalize_evidence(data_logz, data_sigma, prior_logz, prior_sigma) -> dict`, `compare_models(m3: dict, m1: dict) -> dict`, `parse_polychord_stats(path: Path) -> dict`.

- [ ] Write failing tests for quadrature propagation and `Delta logZ = M3 - M1` with quadrature model uncertainty.
- [ ] Run tests and confirm failure.
- [ ] Implement parsers/calculations and reject incomplete/non-finite inputs.
- [ ] Require final convergence metadata to satisfy the production gate before emitting `COMPLETE` comparison.
- [ ] Run tests and confirm PASS.
- [ ] Commit `fix: make PEER evidence normalization statistically explicit`.

### Task 7: Replace production workflow with artifact restore/resume pipeline

**Files:**
- Create: `.github/workflows/peer-nested-production.yml`
- Modify: `.github/workflows/peer-nested-segment-launch-20260911.yml` to become a non-production compatibility notice or disable automatic production triggering.

**Interfaces:**
- Consumes a bootstrap checkpoint artifact/path supplied as workflow input.
- Produces compact `peer-nested-production-<campaign>-<model>-segment-<n>` artifacts.

- [ ] Add `workflow_dispatch` inputs for campaign ID, model, segment ordinal, parent artifact/run ID, and expected parent digest.
- [ ] Add `concurrency: peer-nested-${campaign}-${model}` with `cancel-in-progress: false`.
- [ ] Trigger CI on changes to workflow plus `peer_decisive_followups/**` tests/code.
- [ ] Preflight runtime/science manifests, download exactly one parent checkpoint, verify and restore it, run ~5h20 segment with setup/upload margin, classify state, upload only compact checkpoint/log bundle.
- [ ] Keep M1/M3 independent; never modify priors or `nprior` in YAML shell snippets.
- [ ] Add a lightweight CI-only toy lifecycle job exercising real PolyChord checkpoint→restore→resume when dependencies are available; otherwise fail explicitly rather than silently skip production verification.
- [ ] Commit `ci: replace PEER nested execution with verified continuation pipeline`.

### Task 8: Verification and migration readback

**Files:**
- Modify: `docs/superpowers/specs/2026-09-11-peer-nested-production-pipeline-design.md` only if implementation exposes a real contract discrepancy; otherwise leave unchanged.

- [ ] Run the full focused suite: `python -m pytest -q peer_decisive_followups/test_production_contract.py peer_decisive_followups/test_checkpoint_manager.py peer_decisive_followups/test_run_segment.py peer_decisive_followups/test_production_config.py peer_decisive_followups/test_runtime_contract.py peer_decisive_followups/test_evidence.py`.
- [ ] Run `python -m peer_decisive_followups.orchestrate_segment --help` and `python -m peer_decisive_followups.bootstrap_production --help`.
- [ ] Inspect workflow syntax and GitHub readback for the new commit.
- [ ] Confirm no production file contains workflow-side mutations of `tau`, `nlive`, or `nprior` beyond the frozen explicit configuration.
- [ ] Confirm legacy run artifacts remain untouched and PR #22 is not merged.
- [ ] Report the remaining external blocker honestly: first >6h bootstrap requires an authorized persistent/self-hosted executor; do not claim M1/M3 evidence completion until that bootstrap and later convergence actually occur.
