# NEXO Handoff Bus Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a canonical directed handoff protocol over Tower events and project actionable handoffs into each role bootstrap inbox.

**Architecture:** Extend `AgentService` with append-only handoff emission, transition and inbox projection over `TOWER_V06/events`. Extend role-view materialization to preserve the inbox while leaving work queues unchanged. Use TDD and keep the implementation file-backed and dependency-free.

**Tech Stack:** Python 3.12, `unittest`, JSON files, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-09-13-nexo-handoff-bus-design.md`

## Global Constraints
- No new service, database or persistent queue.
- Work entities remain canonical work state; events only coordinate roles.
- Inbox limit is 5.
- States are `PENDING`, `ACK`, `DONE`, `FAILED`.
- Runtime recipients are `DAILY`, `ADVISOR`, `EXECUTOR`, `LEARNER`, `EMERGENT`; `DIRECTOR` is allowed only as sender.
- Existing Executor mechanical eligibility remains unchanged.

---

### Task 1: Handoff state machine

**Files:**
- Modify: `runtime/nexo_agent_api/test_service.py`
- Modify: `runtime/nexo_agent_api/service.py`

**Interfaces:**
- Produces: `AgentService.emit_handoff(...) -> dict`, `AgentService.transition_handoff(...) -> dict`, `AgentService.inbox_for(role) -> list[dict]`.

- [ ] **Step 1: Write failing tests** for recipient routing and `PENDING -> ACK -> DONE`, asserting that DONE disappears from actionable inboxes and DIRECTOR can be sender.
- [ ] **Step 2: Run** `python -m unittest runtime.nexo_agent_api.test_service -v` and verify failures are caused by missing handoff methods.
- [ ] **Step 3: Implement minimal event scan/state reduction and transition validation** in `service.py`.
- [ ] **Step 4: Re-run** `python -m unittest runtime.nexo_agent_api.test_service -v` and require zero failures.

### Task 2: Bootstrap inbox projection

**Files:**
- Modify: `runtime/nexo_agent_api/test_service.py`
- Modify: `runtime/nexo_agent_api/service.py`
- Modify: `runtime/nexo_agent_api/views.py`

**Interfaces:**
- `AgentService.bootstrap(role)` returns `inbox`, `inbox_count`, `inbox_limit`.
- `materialize_role_views(root)` writes those fields unchanged into `bootstrap/<role>.json`.

- [ ] **Step 1: Write failing test** that emits six handoffs and verifies recipient bootstrap contains five actionable items while queue behavior remains unchanged.
- [ ] **Step 2: Run** `python -m unittest runtime.nexo_agent_api.test_service -v` and verify the new test fails for missing inbox projection/cap.
- [ ] **Step 3: Implement bootstrap inbox fields and limit 5** without altering queue eligibility.
- [ ] **Step 4: Re-run** `python -m unittest runtime.nexo_agent_api.test_service -v` and require zero failures.

### Task 3: Full runtime regression

**Files:**
- No new production files.

**Interfaces:** Existing runtime contracts must remain green.

- [ ] **Step 1: Run** `python -m unittest runtime.nexo_execution.test_execution -v`.
- [ ] **Step 2: Run** `python -m unittest runtime.nexo_agent_api.test_service -v`.
- [ ] **Step 3: Run** `python -m unittest runtime.nexo_agent_api.test_executor_capability_gate -v`.
- [ ] **Step 4: Run** `python -m unittest runtime.nexo_agent_api.test_mutations -v`.
- [ ] **Step 5: Run** `python -m unittest runtime.nexo_agent_api.test_legacy_routing -v`.
- [ ] **Step 6: Run** `python -m unittest discover -s runtime/nexo_core -p 'test_*.py' -v`.
- [ ] **Step 7: Confirm GitHub Actions `NEXO Runtime Tests` succeeds on the feature branch.

### Task 4: GZ-01 operational handoff

**Files:**
- Tower state after code merge; no runtime code change required unless capability binding is missing.

**Interfaces:** Advisor/Director emits `WORK_READY` handoff; Executor consumes inbox and returns terminal handoff to Learner.

- [ ] **Step 1: Materialize a mechanically eligible GZ-01 work item for DESI DR1 + KiDS + eROSITA with pinned task/capability references.
- [ ] **Step 2: Emit `WORK_READY` to EXECUTOR and verify it appears in Executor inbox.
- [ ] **Step 3: Execute the bounded battery work-conserving: DESI DR1, KiDS, eROSITA in independent lanes, then cross-probe consistency, then robustness only if residual tension exists.
- [ ] **Step 4: Persist artifacts/hashes/readback and emit terminal handoff to LEARNER.
- [ ] **Step 5: Verify Tower entity/event history and GitHub Actions artifacts before reporting scientific results.
