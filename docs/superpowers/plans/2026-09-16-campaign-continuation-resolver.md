# Campaign Continuation Resolver V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make any canonical NEXO campaign resumable from TOWER state without campaign-specific prompt logic, while preserving existing execution routing and scientific contract locks.

**Architecture:** Add a pure campaign frontier resolver and a pure capability resolver beside the existing TEST registry and executor service. Keep `register_test()` as identity ingress and the existing execution router as dispatch owner; do not create another state owner, cursor service, agent, or scheduler.

**Tech Stack:** Python 3, unittest, file-backed TOWER_V06 entities, JSON capability manifests.

**Spec:** `docs/superpowers/specs/2026-09-16-campaign-continuation-resolver-design.md`

## Global Constraints

- TOWER_V06 remains the sole operational truth owner.
- No new agent, scheduler, kernel, memory authority, or truth store.
- Existing `task_id` dispatch remains compatible.
- No duplicate RUN creation when an active/recoverable RUN exists.
- Unknown semantic capability returns `NEEDS_ADAPTER`; never invent dispatch.
- Scientific fields are read-only to these resolvers.

---

### Task 1: Campaign frontier resolver

**Files:**
- Create: `runtime/nexo_agent_api/campaign_continuation.py`
- Create: `runtime/nexo_agent_api/test_campaign_continuation.py`

**Interfaces:**
- Produces: `CampaignFrontierResolver(root).resolve(campaign_id: str) -> dict`
- Output keys: `campaign_id`, `status`, `active`, `recoverable`, `ready`, `blocked`, `completed`, `terminal`, `next_test_ids`.

- [ ] Write failing tests covering dependency ordering, active RUN preference, and terminal campaign detection.
- [ ] Run `python -m unittest runtime.nexo_agent_api.test_campaign_continuation -v` and verify failures are caused by missing resolver.
- [ ] Implement minimal entity reads and deterministic classification.
- [ ] Re-run the unit test and verify PASS.

### Task 2: Capability execution resolver

**Files:**
- Create: `runtime/nexo_agent_api/capability_resolution.py`
- Create: `runtime/nexo_agent_api/test_capability_resolution.py`

**Interfaces:**
- Produces: `CapabilityExecutionResolver(capabilities: dict).resolve(test: dict) -> dict`
- Resolution result: `status` in `RESOLVED | NEEDS_ADAPTER | BLOCKED`, plus optional `capability_id`, `task_id`, `backend`, `reason`.

- [ ] Write failing tests for exact `task_id`, semantic capability match, and unknown capability.
- [ ] Run `python -m unittest runtime.nexo_agent_api.test_capability_resolution -v` and verify RED.
- [ ] Implement REUSE and semantic ADAPT resolution only; no auto-generated adapters.
- [ ] Re-run tests and verify PASS.

### Task 3: Integrate with AgentService without breaking task-id routing

**Files:**
- Modify: `runtime/nexo_agent_api/service.py`
- Modify: `runtime/nexo_agent_api/test_executor_capability_gate.py`

**Interfaces:**
- Add: `AgentService.campaign_frontier(campaign_id: str) -> dict`
- Add: `AgentService.resolve_test_execution(test: dict) -> dict`
- Existing `queue_for("EXECUTOR")` behavior remains unchanged for concrete `task_id` and frozen-test paths.

- [ ] Add failing compatibility tests asserting old registered-task behavior still passes and new semantic resolution is callable.
- [ ] Run the focused tests and verify RED only for missing new methods.
- [ ] Add thin service wrappers around the two pure resolvers.
- [ ] Re-run focused tests and verify PASS.

### Task 4: Feature flags and canonical contract documentation

**Files:**
- Modify: `runtime/nexo_agent_api/service.py`
- Modify: `manifests/capabilities.json` only if a schema-compatible semantic field example is required by tests.
- Create or modify test file as needed for flag behavior.

**Interfaces:**
- Resolver mode read from environment/config with default `SHADOW`; `OFF` disables automatic resolver use while leaving explicit methods readable.

- [ ] Write failing test that `OFF` prevents automatic continuation selection but does not affect legacy queue routing.
- [ ] Implement minimal flag parsing.
- [ ] Verify tests PASS.

### Task 5: Full verification

**Files:** none unless a defect is found.

- [ ] Run focused resolver tests.
- [ ] Run `python -m unittest discover runtime/nexo_agent_api -p 'test_*.py' -v`.
- [ ] Confirm no legacy executor/canonical registry regressions.
- [ ] Inspect diff for forbidden second truth/cursor/scheduler machinery.
- [ ] Open PR with design, tests, implementation and rollback notes.
