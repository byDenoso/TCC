# NEXO Adaptive Governance L4 Design

## Goal
Enable automatic improvement of NEXO operational policy through L4 while keeping L5 human-owned.

## Levels
- L0: execution.
- L1: learning from results.
- L2: strategy and prioritization.
- L3: evaluation of strategy quality.
- L4: automatic tuning of allowlisted operational governance parameters.
- L5: human-only authority, permissions, truth ownership, constitutional boundaries, and the definition of the L4 allowlist.

## Architecture
Keep the existing five NEXO roles and the canonical mutation bus. Add a governance gate before canonical mutations are written.

L4 may automatically tune only these policy families: retry limits, parallelism, test budgets, ranking weights, lane priority, promotion thresholds, quarantine thresholds, rollback windows, and shadow-evaluation cycles.

L4 may not change code, tool permissions, repository permissions, writer authority, truth owners, human override, the autonomy ceiling, protected-field lists, or L5 rules.

## L4 evidence gate
An L4 policy mutation must carry baseline_ref, hypothesis_ref, one or more evidence_refs, a metric, positive observed_gain, regression_passed=true, and rollback_ref. Missing evidence rejects the mutation.

## L5 gate
Requests that target constitutional entity kinds or protected authority fields are rejected for autonomous roles regardless of any caller-declared level.

## Compatibility
Existing mutation requests without autonomy metadata keep current behavior. Ordinary work mutations remain L0. The effective level is inferred from target and changed fields, so a request cannot relabel an L5 change as L0.

## Observability
Mutation receipts expose the effective autonomy level and governance gate result.

## Tower state
The Tower stores mutable L4 policy as a governance entity and stores L5 constitution outside the autonomous entity tree.

## Success criteria
Existing mutation tests remain green; L5 bypass attempts fail; L4 without evidence fails; L4 with evidence and allowlisted keys follows normal versioned mutation/readback; non-allowlisted L4 keys fail; receipts expose level and gate.
