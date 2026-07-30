# PEER Microphysics Global Posterior Promotion Design

## Goal

Promote the existing PEER microphysics pilot into a globally converged posterior without removing the near-null corridor, changing the original prior, or conditioning on an active PEER branch.

## Scientific target

The production target preserves the pilot definition:

- stack: Planck 2018 high-l `TTTEEE_lite_native` + low-l TT + Sroll2 EE + Planck 2018 lensing native + DESI 2024 BAO;
- no SH0ES or TRGB;
- `A_lens = 1`;
- `log10(z_c) = 3.81`;
- `theta_i = 2.89155`;
- `f_PEER ~ U(0, 0.18)`;
- `n ~ U(1.05, 8)`;
- CAMB 1.6.6 + CosmoRec and Cobaya 3.6.2;
- full background and scalar perturbations evaluated directly, without a surrogate.

The prior remains the original continuous global prior. The near-null region is not cut away. The result must distinguish:

1. global branch occupancy, especially `P(f_PEER < 0.02 | D)`;
2. the conditional microphysical posterior `p(n | D, f_PEER >= 0.02)`;
3. the fact that `n` becomes weakly identifiable as `f_PEER -> 0`.

## Root cause from the pilot

The five-chain pilot reached `split R-hat max = 5.81` because chains occupied two regions with insufficient communication:

- an active PEER basin centered near `n ~ 3`;
- a near-null corridor in which the PEER amplitude vanishes and `n` becomes observationally weak.

This is a multimodal mixing and identifiability problem, not a CAMB identity failure. The fixed `n=3` implementation already reproduced the canonical PEER1P point exactly in the archived pilot gate.

## Architecture

Run four statistically independent parallel-tempering ladders. Each ladder has six temperatures and one Markov chain at each temperature:

`T = [1.0, 1.5, 2.5, 4.0, 7.0, 12.0]`.

This gives 24 chains in total:

`4 ladders x 6 temperatures = 24 chains`.

Each ladder runs as one six-rank MPI job. Adjacent temperatures attempt state swaps at fixed intervals, alternating even and odd pairs. A swap exchanges the complete state, cached prior, likelihood, derived values, and state label. The acceptance ratio uses likelihood tempering only:

`log alpha = (beta_i - beta_j) * (logL_j - logL_i)`, where `beta = 1/T`.

The cold chain at `T=1` targets the exact posterior. Hot chains exist only to move states across the barrier. Four independent cold chains are aggregated for convergence diagnostics.

## Local proposals

Each rank uses a symmetric Gaussian random-walk proposal in normalized parameter coordinates. Bounded proposals are reflected at the unit-box boundaries, preserving symmetry. Proposal covariance adapts only during a finite warm-up phase and is frozen before production samples are admitted.

Initialization is deliberately split:

- ladders 0 and 2 cold starts begin in the active PEER basin;
- ladders 1 and 3 cold starts begin in the near-null corridor;
- hotter ranks receive progressively broader perturbations while respecting the original prior.

This arrangement tests whether all cold chains recover the same branch weights rather than merely converging inside the basin where they started.

## Components

### `peer_scalar_nfree.py`

Cobaya/CAMB theory wrapper extending the validated fixed-`n=3` wrapper. It samples `peer_n` and assigns it to `EarlyQuintessence.n`. At `peer_n=3`, it must follow the same code path and reproduce the fixed model.

### `campaign.py`

Builds the exact Cobaya model dictionary, writes the production manifest, records priors and temperature ladder, and emits a one-point identity/evaluation configuration.

### `pt_core.py`

Pure numerical functions with no CAMB dependency:

- reflected proposals;
- temperature validation;
- Metropolis acceptance;
- parallel-tempering swap acceptance;
- deterministic pair scheduling;
- checkpoint serialization helpers.

### `pt_driver.py`

MPI production sampler. Each MPI rank owns one temperature. It initializes one Cobaya model per rank, performs local Metropolis updates, coordinates swaps, writes append-only chains, and resumes from atomic checkpoints.

### `diagnostics.py`

Aggregates the four cold chains and all ladder transport logs. It computes rank-normalized split R-hat, bulk/tail ESS, branch occupancy, conditional `n` summaries, state round trips, swap acceptance, and first-half/second-half stability.

### GitHub Actions workflow

A four-job ladder matrix runs the four independent ladders in parallel. Each job uses six MPI ranks and resumable time segments. A final aggregation job downloads all ladder artifacts and executes the global promotion gate.

## Promotion gates

The posterior is promoted only when all conditions pass:

- exactly four independent cold chains are present;
- rank-normalized `R-hat - 1 < 0.01` for baseline cosmological parameters, `f_PEER`, raw `n`, and `f_PEER * (n - 3)`;
- minimum bulk ESS > 1000;
- minimum tail ESS > 500;
- branch-occupancy R-hat passes the same 0.01 threshold;
- each ladder completes at least two cold-to-hot-to-cold state round trips;
- adjacent-temperature swap acceptance is between 0.10 and 0.60 for every edge;
- `P(f_PEER < 0.02)` differs by less than 0.03 between the first and second production halves;
- the four cold chains agree on active-branch occupancy within Monte Carlo uncertainty;
- the `n=3` identity gate passes before production;
- no chain is promoted from a failed or partial likelihood evaluation.

A failure of raw global `n` convergence is not hidden by reporting only the active-branch conditional. If the identifiable coordinate and branch occupancy converge but raw `n` does not, the campaign remains unpromoted and the diagnostics must identify the non-identifiable tail explicitly.

## Outputs

Each ladder artifact contains:

- six temperature-chain files;
- one cold-chain file;
- swap log;
- state-label transport log;
- atomic checkpoint per rank;
- model manifest and exact YAML-equivalent configuration;
- one-point identity and likelihood evaluation logs.

The combined artifact contains:

- four cold chains;
- `promotion_gate.json`;
- `global_summary.json`;
- branch occupancy and conditional microphysics tables;
- R-hat/ESS tables;
- round-trip and swap diagnostics;
- provenance including source commit, CAMB wheel checksum, likelihood payload checksum, seeds, temperatures, and package versions.

## Editorial use

A successful campaign supports a global statement about branch occupancy and a conditional statement about the active PEER microphysics. It does not by itself establish model selection against LambdaCDM, a frequentist detection, or an absolute Bayes factor. The strongest permitted microphysics claim is that the globally sampled posterior assigns a measured weight to the active PEER branch and, within that branch, concentrates the scalar potential index near the recovered corridor.
