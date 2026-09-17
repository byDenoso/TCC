# NEXO Lean-MIN Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Remove administrative blockers from NEXO execution while preserving frozen science, authorization boundaries, irreversible-conflict protection, provenance, persistence, and canonical readback.

**Architecture:** Keep NDMK/TOWER_V06 as the only operational truth owner. Reduce execution admission to scientific-definition, authorization, and irreversible-conflict blockers; treat all other missing operational metadata as derivable or repairable. Keep the current runtime and automation set, but reconcile scheduling, campaign discovery, hydration, and role loops around canonical state and event cursors.

**Tech Stack:** Python stdlib/unittest, GitHub Actions, TOWER_V06 JSON contracts and entities.

**Spec:** User-approved Lean-MIN specification supplied 2026-09-17.

## Global Constraints

- Do not create a second Kernel, router, memory subsystem, truth store, or fifth principal automation.
- Preserve frozen scientific choices and fail closed only when a material scientific definition is genuinely missing.
- Preserve canonical persistence and exact readback before DONE.
- Prefer recovery/resume over duplicate runs.
- Administrative identifiers may be derived but may not block otherwise valid work.

---

### Task 1: Make checkpoint state resumable and work-conserving

**Files:**
- Modify: `runtime/nexo_execution/test_campaign_executor.py`
- Modify: `runtime/nexo_execution/campaign_executor.py`
- Modify: `runtime/nexo_agent_api/test_campaign_continuation.py`
- Modify: `runtime/nexo_agent_api/campaign_continuation.py`

**Behavior:** CHECKPOINTED work does not consume active compute capacity and is returned as recovery/resume work before fresh dispatch.

- [ ] Add failing tests for checkpointed TEST and RUN semantics.
- [ ] Verify the old implementation fails those tests.
- [ ] Split active-compute from resumable checkpoint semantics.
- [ ] Run focused tests and verify green.

### Task 2: Make campaign discovery canonical and compatibility-safe

**Files:**
- Modify: `runtime/nexo_agent_api/test_campaign_continuation.py`
- Modify: `runtime/nexo_agent_api/campaign_continuation.py`

**Behavior:** A canonical campaign stored as `entities/test_group/<id>.json` is readable without duplicating it into `entities/campaign`.

- [ ] Add failing test for test_group-backed campaign discovery.
- [ ] Add read-only compatibility fallback.
- [ ] Verify no duplicate write path is introduced.

### Task 3: Remove administrative executor admission gates

**Files:**
- Modify: Agent API executor routing tests discovered in repository.
- Modify: `runtime/nexo_agent_api/service.py`

**Behavior:** READY/RUNNING work is not hidden merely because `binding_verified`, `dependencies_resolved`, `runtime_available`, `resource_lock_available`, `validation_ref`, or manifest registration metadata is absent. Scientific blockers and explicit manual/authorization blockers remain effective.

- [ ] Add failing routing tests.
- [ ] Replace administrative admission tuple with semantic executability checks.
- [ ] Keep explicit blockers and frozen-test completeness checks.
- [ ] Verify role queue is work-conserving.

### Task 4: Reuse verifiable evidence without mandatory evidence_id or recipe_id

**Files:**
- Modify: `runtime/nexo_execution/test_dependency_producer.py`
- Modify: `runtime/nexo_execution/dependency_producer.py`

**Behavior:** Dependency entries carrying sufficient inline provenance (`source_ref` plus hash/fingerprint and valid status) bind directly. Canonical evidence may also be matched by provenance/fingerprint when no explicit evidence_id is declared. Recipe remains necessary only for real production work.

- [ ] Add failing tests for inline evidence and deterministic evidence identity.
- [ ] Implement evidence matching/derivation without weakening hash/provenance validation.
- [ ] Ensure missing operational metadata does not become WAITING_BINDING when reusable evidence exists.
- [ ] Run dependency producer tests.

### Task 5: Align capability resolution with runtime truth

**Files:**
- Modify: `runtime/nexo_agent_api/test_capability_resolution.py`
- Modify: `runtime/nexo_agent_api/capability_resolution.py`
- Read-only dependency: `runtime/nexo_execution/core.py`

**Behavior:** A known allowlisted runtime task can be resolved even when the capability manifest lacks a duplicate entry. Capability manifests remain useful metadata, not existence gates.

- [ ] Add failing test using an allowlisted runtime task absent from manifest.
- [ ] Resolve via runtime task registry fallback.
- [ ] Preserve explicit blocker handling.

### Task 6: Put lean suites in CI

**Files:**
- Modify: `.github/workflows/nexo-execution-tests.yml`

**Behavior:** CI runs campaign executor, campaign continuation, capability resolution, executor routing, and dependency producer regression suites.

- [ ] Inspect current workflow.
- [ ] Add omitted suites without removing existing coverage.
- [ ] Verify workflow syntax and commit status.

### Task 7: Reconcile the four principal automations by canonical cursor

**State:** Existing principal automations only: Scientific Executor, Scientific Core, Guardian, Journal.

**Behavior:** Each pulse consumes canonical delta since its cursor, writes only material changes, and becomes NO-OP on an unchanged second pass. The loop is state-mediated, never private-message-mediated.

- [ ] Read current automation definitions.
- [ ] Remove legacy administrative gates and full-scan requirements where canonical delta is sufficient.
- [ ] Keep Executor recovery-first, Core reconciliation, Guardian material-risk checks, Journal durable-learning-only.
- [ ] Preserve existing four automation identities and schedules unless a schedule conflict materially prevents convergence.

### Task 8: Canonical smoke, rollback and complexity readback

**Behavior:** Validate one real campaign without modifying frozen science.

- [ ] Run focused and aggregate tests.
- [ ] Use a campaign with already frozen/recoverable scientific contract as smoke.
- [ ] Verify persistence/readback and a second no-delta pass.
- [ ] Compare branch to base and report removed gates, remaining legitimate blockers, commits, and complexity reduction.
