# PEER Microphysics Global Parallel-Tempering Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and launch a 24-chain, four-ladder parallel-tempering campaign that samples the original global PEER microphysics posterior and promotes it only after strict convergence and transport gates pass.

**Architecture:** Four independent MPI jobs each run one six-temperature ladder. A custom MPI Metropolis driver evaluates the exact Cobaya model, performs adjacent-temperature swaps, preserves atomic checkpoints, and emits four independent cold chains for a global rank-Rhat/ESS gate.

**Tech Stack:** Python 3.11, NumPy, SciPy, pandas, PyYAML, mpi4py, ArviZ, Cobaya 3.6.2, CAMB 1.6.6 + CosmoRec, GitHub Actions.

## Global Constraints

- Preserve `f_PEER ~ U(0, 0.18)` and `n ~ U(1.05, 8)`.
- Preserve Planck 2018 TTTEEE-lite native + low-l TT + Sroll2 EE + Planck lensing native + DESI 2024 BAO.
- Exclude SH0ES and TRGB.
- Fix `A_lens=1`, `log10(z_c)=3.81`, `theta_i=2.89155`.
- No surrogate likelihood.
- Promotion requires `R_rank - 1 < 0.01`, bulk ESS > 1000, tail ESS > 500, stable branch occupancy, and successful ladder round trips.
- Do not classify configured or partially sampled chains as converged.

---

### Task 1: Pure parallel-tempering kernel

**Files:**
- Create: `peer_microphysics_global_pt_20260729/test_pt_core.py`
- Create: `peer_microphysics_global_pt_20260729/pt_core.py`

**Interfaces:**
- Produces `reflect_unit_box(x)`, `validate_temperatures(values)`, `swap_log_alpha(beta_a, beta_b, loglike_a, loglike_b)`, `pair_schedule(step, size)`, `metropolis_accept(log_alpha, uniform)`.

- [ ] **Step 1: Write the failing tests**

```python
import numpy as np
import pytest
from pt_core import (
    metropolis_accept,
    pair_schedule,
    reflect_unit_box,
    swap_log_alpha,
    validate_temperatures,
)


def test_reflection_preserves_unit_box_and_symmetry():
    x = np.array([-0.2, 0.2, 1.3, 2.2])
    assert np.allclose(reflect_unit_box(x), [0.2, 0.2, 0.7, 0.2])


def test_temperature_ladder_starts_at_one_and_is_strictly_increasing():
    assert validate_temperatures([1, 1.5, 2.5]) == (1.0, 1.5, 2.5)
    with pytest.raises(ValueError):
        validate_temperatures([1, 1, 2])
    with pytest.raises(ValueError):
        validate_temperatures([1.2, 2])


def test_swap_ratio_uses_likelihood_only():
    assert swap_log_alpha(1.0, 0.5, -10.0, -8.0) == pytest.approx(1.0)


def test_pair_schedule_alternates_disjoint_edges():
    assert pair_schedule(0, 6) == [(0, 1), (2, 3), (4, 5)]
    assert pair_schedule(1, 6) == [(1, 2), (3, 4)]


def test_metropolis_accept_is_deterministic_for_supplied_uniform():
    assert metropolis_accept(-1.0, 0.2)
    assert not metropolis_accept(-1.0, 0.9)
```

- [ ] **Step 2: Verify RED**

Run: `pytest peer_microphysics_global_pt_20260729/test_pt_core.py -q`
Expected: import failure because `pt_core.py` does not exist.

- [ ] **Step 3: Implement the minimal pure kernel**

Implement vector reflection by period-two folding, strict temperature validation, the standard likelihood-only PT swap ratio, alternating disjoint edge scheduling, and log-space Metropolis acceptance.

- [ ] **Step 4: Verify GREEN**

Run: `pytest peer_microphysics_global_pt_20260729/test_pt_core.py -q`
Expected: 5 passed.

- [ ] **Step 5: Commit**

`git commit -m "feat: add tested parallel-tempering kernel"`

### Task 2: n-free CAMB wrapper and exact campaign model

**Files:**
- Create: `peer_microphysics_global_pt_20260729/peer_scalar_nfree.py`
- Create: `peer_microphysics_global_pt_20260729/campaign.py`
- Create: `peer_microphysics_global_pt_20260729/test_campaign.py`

**Interfaces:**
- Produces `PEERScalarNFree` and `build_info(packages_path: str) -> dict`.

- [ ] **Step 1: Write structural failing tests**

Tests assert that the theory accepts `peer_n`, sets the EarlyQuintessence index from the sampled value, preserves fixed `peer_zc` and `peer_thetai`, includes exactly the required Planck+DESI likelihoods, excludes SH0ES/TRGB/ACT/SPT, and preserves original bounds.

- [ ] **Step 2: Verify RED**

Run: `pytest peer_microphysics_global_pt_20260729/test_campaign.py -q`
Expected: missing module failure.

- [ ] **Step 3: Implement wrapper and model builder**

Fork the validated `peer_scalar_n3.py` logic and add `peer_n`. Use `planck_2018_highl_plik.TTTEEE_lite_native`, `planck_2018_lowl.TT`, `planck_2018_lowl.EE_sroll2`, `planck_2018_lensing.native`, and `bao.desi_2024_bao_all`.

- [ ] **Step 4: Verify GREEN**

Run: `pytest peer_microphysics_global_pt_20260729/test_campaign.py -q`
Expected: all tests pass.

- [ ] **Step 5: Commit**

`git commit -m "feat: add exact n-free PEER model"`

### Task 3: MPI production sampler

**Files:**
- Create: `peer_microphysics_global_pt_20260729/pt_driver.py`
- Create: `peer_microphysics_global_pt_20260729/test_checkpoint.py`

**Interfaces:**
- CLI: `python pt_driver.py --root PATH --ladder-id INT --steps INT --swap-every INT --checkpoint-every INT [--resume]`.
- Produces `chains/temp_<rank>.csv`, `checkpoints/rank_<rank>.npz`, `swap_log.csv`, and `ladder_manifest.json`.

- [ ] **Step 1: Write failing checkpoint and state-transport tests**

Tests create a synthetic state, save it atomically, reload it, and verify exact parameter, RNG, state-label, acceptance-counter, and step recovery.

- [ ] **Step 2: Verify RED**

Run: `pytest peer_microphysics_global_pt_20260729/test_checkpoint.py -q`
Expected: missing driver helpers.

- [ ] **Step 3: Implement the driver**

Use one Cobaya `Model` per MPI rank. Temper only the likelihood. Freeze adaptive proposal covariance after finite warm-up. Swap complete cached states using alternating adjacent pairs. Write append-only CSV and atomic NPZ checkpoints.

- [ ] **Step 4: Verify checkpoint GREEN and MPI smoke test**

Run: `pytest peer_microphysics_global_pt_20260729/test_checkpoint.py -q`
Run: `mpirun --oversubscribe -np 6 python peer_microphysics_global_pt_20260729/pt_driver.py --self-test`
Expected: checkpoint tests pass and synthetic six-rank swap test exits zero.

- [ ] **Step 5: Commit**

`git commit -m "feat: add resumable MPI tempered sampler"`

### Task 4: Global diagnostics and promotion gate

**Files:**
- Create: `peer_microphysics_global_pt_20260729/diagnostics.py`
- Create: `peer_microphysics_global_pt_20260729/test_diagnostics.py`

**Interfaces:**
- CLI: `python diagnostics.py --input downloads --output combined`.
- Produces `promotion_gate.json`, `global_summary.json`, `rhat_ess.csv`, `branch_occupancy.csv`, and `transport.csv`.

- [ ] **Step 1: Write failing synthetic diagnostics tests**

Generate four converged synthetic cold chains and one intentionally split set. Assert that the first passes and the second fails the promotion gate. Assert branch occupancy and half-chain stability calculations.

- [ ] **Step 2: Verify RED**

Run: `pytest peer_microphysics_global_pt_20260729/test_diagnostics.py -q`
Expected: missing diagnostics module.

- [ ] **Step 3: Implement diagnostics**

Use ArviZ rank R-hat and bulk/tail ESS after 30% burn-in. Diagnose baseline parameters, `peer_fede`, `peer_n`, `peer_fede*(peer_n-3)`, and binary active-branch occupancy. Parse swap logs and state labels for edge acceptance and round trips.

- [ ] **Step 4: Verify GREEN**

Run: `pytest peer_microphysics_global_pt_20260729/test_diagnostics.py -q`
Expected: synthetic pass/fail cases classified correctly.

- [ ] **Step 5: Commit**

`git commit -m "feat: add global microphysics promotion gate"`

### Task 5: Production workflow and launch

**Files:**
- Create on `main`: `.github/workflows/peer-microphysics-global-pt.yml`

**Interfaces:**
- Matrix `ladder: [0,1,2,3]`.
- Checks out `peer-microphysics-global-pt-20260729`.
- Reuses validated CAMB/CosmoRec wheel and likelihood payload from run `30455821484`.

- [ ] **Step 1: Add workflow structural checks**

The workflow runs all pure tests, checks the n=3 identity path structurally, initializes the full likelihood once, and only then launches sampling.

- [ ] **Step 2: Run each ladder**

Each matrix job runs two resumable time segments with `mpirun --oversubscribe -np 6`. Artifacts upload even on failure.

- [ ] **Step 3: Aggregate**

A final job downloads all four ladder artifacts and runs `diagnostics.py`. It exits nonzero unless the complete promotion gate passes.

- [ ] **Step 4: Commit and confirm trigger**

Commit message: `ci: launch global PEER microphysics tempering campaign`.
Confirm a workflow run ID before claiming the campaign is running.

## Plan self-review

- Spec coverage: exact prior, stack, 24 chains, swaps, checkpoints, diagnostics, and editorial boundary are each assigned to a task.
- Placeholder scan: no TBD/TODO instructions remain.
- Type consistency: the driver and diagnostics paths and CLI names are consistent across tasks and workflow.
