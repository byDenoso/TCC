# PEER Detection Battery V1

## Scope

Implement the frozen D00-D25 detection contract as an executable NEXO scientific gate layer. The battery does not claim novelty for profile likelihoods, parametric bootstrap, Bayesian evidence, SBC, posterior predictive checks, ablations, injection-recovery, holdouts, or model comparison. Those are established methods. The project-specific extension is the audited composition of those methods into one PEER decision contract with fixed stopping rules and final classification.

## Scientific question

Do the data require a non-zero PEER contribution globally and reproducibly, rather than only under a local scan, a specific distance-ladder anchor, a prior choice, one experiment/tracer, or a known rival early-sector freedom?

## Final classes

- `NO_DETECTION`: PEER is not required after global calibration.
- `ANCHOR_CONDITIONED_SIGNAL`: preference exists only after an H0 anchor is imposed.
- `MODEL_CLASS_DETECTION`: an early-sector extension is supported but PEER is not distinguished from rival model classes.
- `PEER_SPECIFIC_DETECTION`: PEER survives global calibration, prior/anchor/data splits, rival models, calibration tests, and independent prediction.
- `INCONCLUSIVE`: required evidence is missing or an execution/calibration gate is unresolved.

## Frozen campaign policy

The numerical thresholds below are campaign governance choices, not universal laws of statistics.

- global evidence gate: `p_global < 0.0027`
- 5-sigma reporting level: `p_global < 2.87e-7`
- strong Bayes evidence diagnostic: `delta_lnZ >= 5`
- PPC admissible interval: `0.01 <= p <= 0.99`
- cross-split consistency default: `max_pairwise_z <= 2.5`
- release/code-path shift default: `< 1 sigma`
- minimum optimizer/seed repetitions: `5`

## Execution order and stop rule

Cheap/diagnostic gates run before expensive calibration:

`D00 -> D01 -> D04 -> D09 -> D11 -> D13 -> D02 -> D03 -> D07 -> D08 -> D05 -> D06 -> D18 -> D19 -> D20 -> D21 -> D15 -> D16 -> D17 -> D22 -> D23 -> D24 -> D25`

If D09 establishes `ANCHOR_CONDITIONED_SIGNAL`, the expensive global-null and evidence-calibration phase may be skipped for an anchor-independent detection claim. The skipped gates are recorded as `SKIPPED_BY_POLICY`, never silently treated as passes.

## Gate map

| Gate | Purpose | Evaluation primitive | Required upstream evidence |
|---|---|---|---|
| D00 | Freeze/preregister | manifest/hash validation | gate registry + policy |
| D01 | Same-stack baseline | nested fit comparison | null/PEER chi2 on identical stack |
| D02 | Boundary-aware global null | empirical parametric-bootstrap tail | observed qmax + null qmax simulations |
| D03 | Look-elsewhere correction | global max-statistic tail | local statistic + scan maxima under null |
| D04 | Profile likelihood | interior minimum + f=0 degradation | profile points in f_PEER |
| D05 | Bayesian evidence | delta lnZ | reproducible log-evidence estimates |
| D06 | Prior sensitivity | qualitative stability grid | repeated fits under frozen prior grid |
| D07 | Injection-recovery | bias/coverage/FPR/FNR | null and PEER injections |
| D08 | SBC | rank/coverage calibration | simulation-based calibration summary |
| D09 | SH0ES ablation | anchor-free survival | with-anchor and no-anchor fits |
| D10 | Anchor swap | calibrator consistency | Cepheid/TRGB/no-anchor fits |
| D11 | CMB experiment split | cross-experiment consistency | Planck/ACT/SPT summaries |
| D12 | CMB sub-block attribution | dominance audit | TT/TE/EE/lensing/low-l contributions |
| D13 | DESI tracer ablation | leave-one-tracer-out stability | tracer/bin ablations |
| D14 | SN substitution | dataset robustness | Pantheon+/DESY5/Union3 summaries |
| D15 | Growth prediction | new-tension audit | growth/lensing/clusters/eROSITA predictions |
| D16 | Posterior predictive checks | blockwise PPC | replicated-data discrepancy p-values |
| D17 | Holdout prediction | out-of-selection predictive score | delta ELPD/log predictive density |
| D18 | A_lens rival | rival comparison | PEER vs LambdaCDM+A_lens |
| D19 | EDE/pNGB rival | model-class discrimination | PEER vs EDE/pNGB |
| D20 | Neff/recombination rival | acoustic-sector discrimination | PEER vs Neff/recombination freedoms |
| D21 | Lambda-free comparator | structural rival comparison | PEER+Lambda vs Lambda-free/two-field |
| D22 | Data-release robustness | normalized parameter/likelihood shifts | PR3/PR4/NPIPE/likelihood variants |
| D23 | Code-path replication | numerical equivalence | CAMB/Cobaya vs CLASS/MontePython |
| D24 | Seeds/minimizers | basin reproducibility | >=5 independent seeds/optimizers |
| D25 | Global synthesis | deterministic decision matrix | canonical results D00-D24 |

## Runtime contract

Every gate is executable through one frozen code path, but each gate has its own capability ID and task ID. Scientific inputs are work-bound, provenance-hashed bindings, not baked into the capability definition. Missing evidence must produce a valid `INCONCLUSIVE` result, not synthetic support.

Gate output schema:

```json
{
  "schema": "peer.detection.gate-result.v1",
  "battery_id": "PEER_DETECTION_V1",
  "gate_id": "D02",
  "gate_status": "PASS|FAIL|INCONCLUSIVE|SKIPPED_BY_POLICY",
  "metrics": {},
  "classification_hint": null,
  "reason_codes": [],
  "input_digest": null,
  "policy_digest": "...",
  "nexo_verification": {
    "status": "PASS",
    "decision": "VERIFIED|INCONCLUSIVE",
    "reason_code": "...",
    "scope": "SCIENTIFIC"
  }
}
```

`VERIFIED` means the gate evaluation is valid and reproducible, not that PEER is scientifically supported.

## Priority/state-of-art boundary

Existing literature already uses the constituent methods and currently shows dataset/prior/anchor dependence for early-dark-energy-like fits; recent ACT/SPT/DESI results do not establish a universal early-sector detection. The novelty claim, if any, can only arise from a PEER-specific scientific result that survives the full frozen contract, not from the gate methodology itself.