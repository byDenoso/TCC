# NEXO GitHub-native Orchestrator v0.1

Date: 2026-09-13
Status: DESIGN APPROVED IN CHAT, IMPLEMENTATION PENDING SPEC REVIEW
Branch: `nexo-gh-orchestrator-20260913`
Base: `run-peer-segmented-20260911`

## 1. Goal

Build a GitHub-native orchestration layer for NEXO that coordinates scientific campaigns without requiring n8n, a VM, or a new always-on service.

The orchestrator must make campaign state explicit, dispatch existing GitHub Actions jobs, validate scientific promotion criteria separately from technical job success, persist machine-readable results, and emit deterministic downstream events for NEXO Learner / SSOT / notifications.

This is an operational control-plane change. It does not alter PEER physics, likelihoods, priors, scientific interpretation, or existing scientific result authority.

## 2. Current repository context

The repository already contains many production scientific workflows, including SPT D1 MCMC, 20-chain campaigns, ACT lanes, nested sampling, and microphysics campaigns. Most are monolithic workflows rather than reusable `workflow_call` units.

The repository also already uses GitHub-native dispatch patterns. For example, `dispatch-peer-microphysics-on-pr.yml` launches another workflow with `gh workflow run`, records the resulting run ID, and creates an issue. This proves the repository can already use GitHub Actions as an event-driven coordinator without external infrastructure.

There is currently no common campaign manifest, no common state machine, no common result envelope, and no reusable orchestration contract spanning Advisor -> Executor -> Validator -> Learner.

## 3. Scope of v0.1

v0.1 is deliberately small. It will introduce the orchestration contract and one working end-to-end campaign path while preserving existing scientific workflows.

Included:

- campaign manifest schema;
- explicit campaign/test state machine;
- one NEXO orchestrator workflow;
- one executor adapter that dispatches an existing workflow rather than rewriting it;
- one validator that interprets machine-readable executor output / workflow artifacts;
- normalized result envelope;
- deterministic event routing after validation;
- concurrency and retry limits;
- dry-run mode;
- contract tests that fail closed;
- provenance linking campaign -> test -> commit -> workflow run -> artifact -> validation result.

Not included in v0.1:

- rewriting all scientific workflows to reusable `workflow_call` units;
- replacing the canonical SSOT;
- automatic scientific interpretation by an LLM inside GitHub Actions;
- Slack / Drive / Sheets credentials or direct writes unless an existing safe connector path is already available;
- arbitrary dynamic YAML execution from untrusted manifests;
- autonomous creation of unlimited new tests;
- migration of every legacy workflow in one pass.

## 4. Chosen architecture

### 4.1 Control plane

GitHub Actions becomes the NEXO operational control plane.

Flow:

`Advisor -> campaign.yaml -> Orchestrator -> Executor Adapter -> Existing Scientific Workflow -> Validator -> Result Envelope -> Event Router -> Learner/SSOT/Notification`

The orchestrator does not run the science itself. It coordinates scientific workflows that remain independently testable and auditable.

### 4.2 Why this approach

Three approaches were considered:

1. GitHub-native orchestration around existing workflows.
2. Immediate refactor of all scientific workflows into reusable `workflow_call` components.
3. External orchestration platform such as n8n / Windmill.

v0.1 selects approach 1 because it has the lowest migration risk and requires no new infrastructure. Approach 2 remains the long-term cleanup path after the orchestration contract is stable. Approach 3 remains optional if GitHub event/state limitations become a real bottleneck rather than a theoretical one.

## 5. Repository layout

Proposed files:

```text
.nexo/
  campaigns/
    example-peer-sptd1.yaml
  schemas/
    campaign.schema.json
    result.schema.json
  state/
    README.md

.github/workflows/
  nexo-orchestrator.yml
  nexo-validate.yml
  nexo-contract.yml

scripts/nexo/
  validate_campaign.py
  build_execution_plan.py
  normalize_result.py
  validate_result.py
  transition_state.py

docs/nexo/
  ORCHESTRATION.md
```

Existing scientific workflows stay in place during v0.1.

## 6. Campaign manifest contract

A campaign is declarative and versioned in Git.

Example:

```yaml
schema_version: 1
campaign_id: PEER-SPTD1-001
domain: cosmology
question: "Does PEER retain support under the SPT-3G D1 matched stack?"
status: PLANNED
budget:
  max_tests: 6
  max_parallel: 2
  max_retries_per_test: 1
  max_runtime_minutes: 720

tests:
  - test_id: T-DE001
    executor: github_workflow
    workflow: peer-n31p-spt3g-mcmc.yml
    ref: run-peer-segmented-20260911
    inputs:
      model: N31P
    depends_on: []
    promotion:
      require_workflow_success: true
      require_artifact: true
      validator: peer_mcmc_convergence

  - test_id: T-DE002
    executor: github_workflow
    workflow: peer-n31p-spt3g-mcmc.yml
    ref: run-peer-segmented-20260911
    inputs:
      model: N31P_ALENS
    depends_on: []
    promotion:
      require_workflow_success: true
      require_artifact: true
      validator: peer_mcmc_convergence
```

The manifest may select only executor types and validators registered in repository code. It cannot embed arbitrary shell commands.

## 7. State machine

Campaign states:

```text
PLANNED -> READY -> RUNNING -> VALIDATING -> LEARNING -> CLOSED
              \        \          \
               \        -> FAILED   -> BLOCKED
                -> BLOCKED
```

Test states:

```text
PLANNED -> READY -> DISPATCHED -> RUNNING -> VALIDATING -> PASSED
                                     |           |
                                     |           -> NOT_PROMOTED
                                     -> FAILED
```

`PASSED` means the scientific promotion contract passed.

`NOT_PROMOTED` means execution may have produced useful artifacts, but scientific acceptance gates did not pass.

`FAILED` means execution or validation failed technically.

`BLOCKED` means a dependency, budget, missing input, or policy prevents execution.

A green GitHub job is never sufficient by itself to mark a scientific test `PASSED`.

## 8. Result envelope

Every test must normalize to one machine-readable result document.

Example:

```json
{
  "schema_version": 1,
  "campaign_id": "PEER-SPTD1-001",
  "test_id": "T-DE001",
  "execution": {
    "status": "COMPLETED",
    "workflow": "peer-n31p-spt3g-mcmc.yml",
    "run_id": 34760996447,
    "head_sha": "...",
    "artifact_names": ["peer-n31p-spt3g-d1-N31P-20260912"]
  },
  "validation": {
    "status": "NOT_PROMOTED",
    "validator": "peer_mcmc_convergence",
    "metrics": {
      "n_chains": 4,
      "rhat_minus1_max": 0.014
    },
    "reasons": ["RHAT_GATE_FAILED"]
  },
  "provenance": {
    "campaign_commit": "...",
    "validator_commit": "..."
  }
}
```

The envelope must remain valid even for technical failure. Missing metrics are `null`; non-finite numeric values must never be emitted as invalid JSON.

## 9. Orchestrator behavior

`nexo-orchestrator.yml` runs by `workflow_dispatch` and optionally by push to a campaign manifest path.

Its responsibilities are:

1. checkout the exact campaign commit;
2. validate the manifest against the schema;
3. validate budget and dependency graph;
4. compute runnable tests;
5. enforce `max_parallel`;
6. dispatch only registered workflows;
7. capture run IDs deterministically;
8. persist execution receipts as artifacts;
9. invoke or signal validation after execution;
10. never promote a result by workflow conclusion alone.

v0.1 may use `gh workflow run` for adapters because the repository already uses this pattern. Future versions may replace adapters with reusable `workflow_call` units where advantageous.

## 10. Dispatch identity and race prevention

Dispatch must not identify a launched run by simply asking for "the latest run" after sleeping.

Each dispatch must carry a unique correlation ID, for example:

`NEXO_<campaign_id>_<test_id>_<attempt>_<short_sha>`

Where supported, the target workflow receives this ID as an input or environment-derived execution label. The adapter must resolve the matching run using correlation data plus creation time and commit/ref constraints.

If deterministic resolution is not possible for a target workflow, that workflow is not eligible for automatic NEXO dispatch until adapted.

## 11. Validation

Validation is separate from execution.

The validator registry maps names to repository-owned validators, for example:

- `peer_mcmc_convergence`;
- `nested_sampling_completion`;
- `artifact_presence_only`;
- `contract_test_pass`.

Each validator returns:

- `PASSED`;
- `NOT_PROMOTED`;
- `FAILED`;
- `BLOCKED`.

Validators fail closed on malformed, missing, non-finite, or contradictory diagnostics.

## 12. Event routing

v0.1 emits explicit machine-readable events instead of relying on periodic polling.

Logical events:

- `nexo.test.dispatched`;
- `nexo.test.completed`;
- `nexo.test.validated`;
- `nexo.campaign.ready_for_learning`;
- `nexo.campaign.blocked`;
- `nexo.campaign.closed`.

Initial implementation may represent these as artifacts plus GitHub workflow dispatches / repository dispatches where permissions allow.

The Learner is invoked only after required tests are terminal and campaign policy says the campaign is ready for synthesis.

## 13. Retry and budget policy

Retries are explicit and bounded.

Default v0.1 policy:

```yaml
max_retries_per_test: 1
retry_on:
  - INFRASTRUCTURE_FAILURE
  - TRANSIENT_NETWORK_FAILURE
  - RUNNER_FAILURE
never_auto_retry_on:
  - SCIENTIFIC_GATE_FAILED
  - INVALID_CAMPAIGN
  - INVALID_RESULT
  - POLICY_BLOCK
```

A convergence failure is not automatically retried unless the campaign explicitly authorizes continuation/resume logic for that validator/executor pair.

## 14. Concurrency

GitHub concurrency groups prevent duplicate execution of the same campaign/test/attempt.

Suggested key:

`nexo-${campaign_id}-${test_id}-${attempt}`

Campaign-level `max_parallel` is enforced by the execution planner rather than by creating an unbounded dynamic matrix.

## 15. Security and trust boundaries

Campaign manifests are data, not executable code.

The following are forbidden:

- arbitrary `run:` blocks in campaign manifests;
- arbitrary workflow filenames outside the executor registry;
- arbitrary external repository dispatch targets;
- secrets printed into result envelopes;
- automatic writes to scientific SSOT before validation;
- treating pull-request code from untrusted forks as authorized production execution.

The orchestrator uses least-privilege GitHub permissions.

## 16. Dry-run mode

`dry_run=true` validates the campaign, dependency graph, budgets, registered executors, registered validators, and predicted execution plan without dispatching science jobs.

Dry-run is required before first production execution of a new campaign schema version.

## 17. Testing strategy

Implementation follows TDD.

Required contract tests:

1. valid campaign accepted;
2. unknown executor rejected;
3. unknown validator rejected;
4. cyclic dependencies rejected;
5. missing dependency rejected;
6. budget overflow rejected;
7. duplicate test IDs rejected;
8. arbitrary command injection rejected;
9. non-finite result metrics serialize safely and fail closed;
10. workflow success without scientific validation cannot become `PASSED`;
11. `NOT_PROMOTED` remains distinct from technical `FAILED`;
12. retry budget cannot be exceeded;
13. dry-run never dispatches a workflow.

The first end-to-end integration test should use a cheap/no-op registered executor, not CAMB/MCMC compute.

## 18. Migration plan

### Phase A: control-plane skeleton

Implement schemas, state transitions, dry-run planner, result envelope, and contract tests.

### Phase B: one real adapter

Adapt one existing scientific workflow to deterministic NEXO dispatch and result normalization. Prefer an inexpensive workflow first; do not use the long SPT D1 MCMC as the first orchestration integration test.

### Phase C: validator integration

Wire one scientific validator and prove `PASSED` vs `NOT_PROMOTED` behavior using preserved artifacts.

### Phase D: event-driven handoff

Emit ready-for-learning events and attach normalized result bundles.

### Phase E: gradual workflow refactor

Only after the control-plane contract is stable, convert high-value duplicated scientific workflows into reusable `workflow_call` components.

## 19. Success criteria for v0.1

v0.1 is complete when:

- a campaign manifest can be validated and dry-run deterministically;
- a registered existing workflow can be dispatched and correlated to its exact run ID;
- its result can be normalized to the result schema;
- technical success and scientific promotion are demonstrably independent;
- the state machine reaches a correct terminal state;
- provenance includes campaign commit, executor run ID, executor commit, artifact identity, and validator commit;
- duplicate dispatch is prevented;
- contract tests pass;
- no VM, n8n, or always-on service is required.

## 20. Operational principle

NEXO uses AI for planning, synthesis, and interpretation, but uses deterministic GitHub-owned contracts for execution state, retries, provenance, promotion gates, and routing.

The orchestrator must reduce ambiguity. If adding it makes the system harder to understand than the workflows it coordinates, the design has failed.
