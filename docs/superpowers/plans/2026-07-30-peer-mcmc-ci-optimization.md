# PEER MCMC CI Optimization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an optimized, resumable ACT DR6 MCMC workflow that preserves the posterior and strict promotion gates while removing repeated runtime setup and limiting GitHub concurrency to five runners.

**Architecture:** A composite action restores or constructs one immutable scientific runtime cache. Five model-shard jobs run four MPI chains each in short resumable segments. A repository-local diagnostic performs the global 20-chain rank-Rhat, ESS and MCSE promotion gate.

**Tech Stack:** GitHub Actions, Python 3.11, Cobaya 3.6.2, CAMB 1.6.6 + CosmoRec, ACT DR6 lite, OpenMPI, NumPy, pandas, PyYAML, ArviZ, pytest.

## Global Constraints

- Do not change the likelihood stack, priors, parameter bounds, fixed PEER coordinates, or CAMB/CosmoRec implementation.
- Preserve 20 chains per model for M2 and M3.
- Allow at most five MCMC shard jobs to execute concurrently.
- Promotion requires 20 readable chains, native checkpoint convergence, rank R-hat minus one below 0.01, bulk ESS at least 1000, and tail ESS at least 500.
- Missing, non-finite, partial, timed-out, or malformed outputs remain incomplete.

---

### Task 1: Independent convergence gate

**Files:**
- Create: `peer_ci_optimization/convergence_gate.py`
- Create: `peer_ci_optimization/test_convergence_gate.py`

**Interfaces:**
- Produces `diagnose(root, burn_fraction, params, rhat_limit, ess_bulk_limit, ess_tail_limit, mcse_relative_limit) -> dict`.
- CLI writes `convergence_gate.json` and exits zero only when every gate passes.

- [ ] **Step 1: Write tests for converged and split synthetic chains**
- [ ] **Step 2: Run `pytest peer_ci_optimization/test_convergence_gate.py -q` and verify RED**
- [ ] **Step 3: Implement weighted-trace expansion, checkpoint parsing, ArviZ diagnostics and JSON-safe output**
- [ ] **Step 4: Run the test and verify GREEN**
- [ ] **Step 5: Commit `feat: add strict reusable MCMC convergence gate`**

### Task 2: Runtime cache composite action

**Files:**
- Create: `.github/actions/peer-runtime-cache/action.yml`
- Create: `peer_ci_optimization/test_runtime_action.py`

**Interfaces:**
- Inputs: `source-run-id`, `act-commit`, `python-version`, `cache-version`.
- Outputs: `runtime-root`, `python`, `packages-path`, `cache-hit`.
- Produces `.peer-runtime/venv`, `.peer-runtime/packages`, `.peer-runtime/validated`, `.peer-runtime/Rec_database`, `.peer-runtime/Development`, and `.peer-runtime/lib`.

- [ ] **Step 1: Write structural tests for exact cache key, binary verification and non-editable ACT installation**
- [ ] **Step 2: Verify RED**
- [ ] **Step 3: Implement the composite action using `actions/cache@v4` and a fail-closed build on cache miss**
- [ ] **Step 4: Verify GREEN**
- [ ] **Step 5: Commit `ci: add immutable PEER runtime cache action`**

### Task 3: Optimized production workflow

**Files:**
- Create: `.github/workflows/peer-n31p-act-20chains-optimized.yml`
- Create: `peer_ci_optimization/test_workflow_structure.py`

**Interfaces:**
- Manual input `resume_run_id`, empty by default.
- Matrix `model: [M2, M3]`, `shard: [0,1,2,3,4]`, `max-parallel: 5`.
- Uses four MPI ranks per shard and up to four 65-minute resumable segments.

- [ ] **Step 1: Write workflow structure tests**
- [ ] **Step 2: Verify RED**
- [ ] **Step 3: Add preflight, cache restore, optional prior-run artifact restore, sampler tuning, segmented execution and aggregation**
- [ ] **Step 4: Verify YAML parsing and structure tests GREEN**
- [ ] **Step 5: Commit `ci: add optimized resumable ACT posterior workflow`**

### Task 4: CI verification and execution isolation

**Files:**
- Create: `.github/workflows/peer-ci-optimization-tests.yml`
- Create: `.github/launch/README.md`

**Interfaces:**
- PR workflow runs pure tests only.
- Production workflow is triggered by manual dispatch or a dedicated launch marker, never by ordinary code commits.

- [ ] **Step 1: Add test-only PR workflow**
- [ ] **Step 2: Open a draft PR to `main`**
- [ ] **Step 3: Confirm the unit-test workflow run and inspect failures**
- [ ] **Step 4: Fix failures without changing scientific invariants**
- [ ] **Step 5: Record verified status in the PR body**

## Plan self-review

- Spec coverage: cache, concurrency, resume, sampler geometry, diagnostics, queue hygiene and scientific invariants each map to a task.
- Placeholder scan: no TBD or undefined implementation step remains.
- Type consistency: file names, CLI output, workflow matrix and gate thresholds are consistent across tasks.
