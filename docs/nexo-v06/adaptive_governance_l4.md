# NEXO Autonomy Boundary

L0 execution, L1 learning, and L2 strategy may run automatically under their existing contracts.

L3 meta-evaluation may also run automatically, but it is observable by contract: before execution it must declare `l3_intent` with summary, reason, and metric; after a successful mutation the receipt must expose `l3_report` with the declared intent, requested changes, resulting entity version, readback, and event id.

L4 operational policy tuning is proposal-first and human-approved. The runtime may validate an L4 candidate against the canonical `NEXO_RSI_POLICY` target, operational-key allowlist, evidence requirements, regression pass, and rollback reference. A valid candidate without approval stops at `L4_APPROVAL_REQUIRED` and returns a `proposal_hash`. Execution is allowed only when `human_approval` explicitly approves that exact hash. Changing the proposal invalidates the approval.

L5 remains human-only. Human override, authority roots, truth ownership, writer authority, permission boundaries, repository/tool permissions, autonomy ceiling, the L4 allowlist, and constitutional rules cannot be changed by autonomous mutation requests.

The enforcement point is `runtime/nexo_agent_api/governance.py`, invoked by the canonical mutation bus before any entity write. Semantic classification overrides a caller-declared autonomy level, so protected L5 changes cannot be relabeled as L0-L4.
