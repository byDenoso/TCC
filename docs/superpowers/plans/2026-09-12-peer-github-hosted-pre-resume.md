# PEER GitHub-Hosted Pre-Resume Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the frozen PEER M1/M3 PolyChord bootstrap resumable before the native `.resume` exists so production can run entirely on GitHub-hosted runners.

**Architecture:** Patch pinned PolyChordLite 1.20.1 only inside `GenerateLivePoints`, adding a dedicated pre-resume state and deterministic RNG fast-forward. A Python orchestration layer packages/restores that state with science/runtime lineage and a hosted workflow chains bounded segments until native PolyChord resume is available, then hands off to the existing verified continuation path.

**Tech Stack:** Python 3.11, pytest, Cobaya 3.6.2, PolyChordLite 1.20.1 Fortran, OpenMPI, GitHub Actions Ubuntu 24.04.

**Spec:** `docs/superpowers/specs/2026-09-12-peer-github-hosted-pre-resume-design.md`

## Global Constraints

- Do not alter any scientific prior, likelihood, fixed parameter, `nlive=400`, `nprior=20nlive`, or `precision_criterion=0.001`.
- Pin PolyChordLite 1.20.1 and fail if expected upstream patch anchors do not match.
- Pre-resume state is promoted only after MPI workers are drained.
- A dedicated checkpoint exit is classified `BOOTSTRAP_REQUIRED`, never `COMPLETE`.
- Native `.resume` remains the sole continuation state after live-point generation finishes.
- Production branch remains isolated; no merge without explicit approval.

---

### Task 1: Patch contract and unit gate

**Files:**
- Create: `peer_decisive_followups/polychord_bootstrap_patch.py`
- Create: `peer_decisive_followups/test_polychord_bootstrap_patch.py`
- Modify: `.github/workflows/peer-nested-segment-launch-20260911.yml`

**Interfaces:**
- Produces: `apply_bootstrap_patch(source_root: Path) -> dict[str, str]` returning upstream and patched SHA256 metadata.

- [ ] Write tests asserting pinned upstream anchors, idempotence rejection, absence of science-setting strings, and generated Fortran checkpoint markers.
- [ ] Run the new test in CI and observe RED before implementation.
- [ ] Implement strict source transformation of `src/polychord/generate.F90`.
- [ ] Run unit gate and verify GREEN.
- [ ] Commit.

### Task 2: Pre-resume artifact contract

**Files:**
- Create: `peer_decisive_followups/bootstrap_state.py`
- Create: `peer_decisive_followups/test_bootstrap_state.py`

**Interfaces:**
- Produces: `inspect_bootstrap_state(path)`, `promote_bootstrap_bundle(...)`, `restore_bootstrap_bundle(...)`.

- [ ] Test model/science/runtime mismatch, corruption, atomic restore, parent lineage and bootstrap metadata.
- [ ] Implement fail-closed bundle promotion/restore reusing existing hashing conventions.
- [ ] Run tests and commit.

### Task 3: Hosted segment runner

**Files:**
- Create: `peer_decisive_followups/bootstrap_hosted_segment.py`
- Create: `peer_decisive_followups/test_bootstrap_hosted_segment.py`

**Interfaces:**
- Consumes: patched PolyChord install, frozen production config, optional parent bootstrap bundle.
- Produces: `segment_status.json` with classification `BOOTSTRAP_REQUIRED`, `RESUMABLE`, or `FAILED` and a promoted output bundle.

- [ ] Test classification for dedicated checkpoint exit, native resume, corrupt parent and unexpected process exit.
- [ ] Implement restore -> metadata relocation -> production config -> patched sampler launch -> promotion.
- [ ] Verify the execution budget is execution-only metadata and excluded from science manifest.
- [ ] Run tests and commit.

### Task 4: Real PolyChord pre-resume E2E

**Files:**
- Create: `peer_decisive_followups/test_polychord_pre_resume_e2e.py`
- Modify: `.github/workflows/peer-nested-segment-launch-20260911.yml`

**Interfaces:**
- Uses a cheap toy Cobaya likelihood and patched PolyChord.

- [ ] Install pinned PolyChord source, apply patch and compile.
- [ ] Run a toy case with `nprior` deliberately larger than one segment budget.
- [ ] Verify first invocation creates only pre-resume state and dedicated exit.
- [ ] Restore and run second invocation to reach native `.resume`/completion.
- [ ] Run uninterrupted reference with same seed and compare prior metadata/evidence within deterministic numerical tolerance.
- [ ] Commit after E2E is green.

### Task 5: Canonical GitHub-hosted bootstrap workflow

**Files:**
- Create: `.github/workflows/peer-nested-hosted-bootstrap-20260912.yml`
- Modify: `peer_decisive_followups/test_workflow_contract.py`

**Interfaces:**
- Inputs: `campaign_id`, `model`, `segment`, optional `parent_run_id`, optional `parent_artifact`, runtime source run.
- Outputs/artifacts: one compact bootstrap/native checkpoint bundle plus status report.

- [ ] Add contract tests requiring `ubuntu-24.04`, `actions: write`, bounded timeout, pinned patch installation, artifact restore, max segment guard and self-dispatch only for `BOOTSTRAP_REQUIRED`.
- [ ] Implement workflow with one model per run and conservative default `segment_valid=1000`.
- [ ] Add launcher mode that starts independent M1/M3 segment-0 runs.
- [ ] Verify no `self-hosted` requirement remains in the canonical hosted path.
- [ ] Commit and observe CI.

### Task 6: Production preflight and launch

**Files:**
- Modify only if verification exposes defects in files above.

**Interfaces:**
- Production campaign uses frozen science branch `act-dr6-peer-test-20260729`, runtime source run `34561868964`, deterministic seeds M1 `2026076101`, M3 `2026076103`.

- [ ] Run full unit gate.
- [ ] Run real patched-PolyChord E2E.
- [ ] Verify generated workflow text contains no prior/sampler mutation beyond the frozen config builder.
- [ ] Launch M1 and M3 hosted segment-0 runs.
- [ ] Read back jobs/logs/status; only report launched after GitHub shows actual runs.
- [ ] Do not merge execution branch or persist scientific results until matched complete evidence exists.
