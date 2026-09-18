# NEXO Control Plane v0.3 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a shadow-first deterministic NEXO control plane that supports asynchronous science/engineering workers without role drift, duplicate execution, or global blocking.

**Architecture:** A small Python standard-library package models work, strict state transitions, dependencies, scoped locks, capacity/backpressure, routing, external execution/result envelopes, verification gates, and reconciliation. The public TCC repository contains only generic control-plane code/tests/docs; canonical state remains in Google Sheets/Drive and live ChatGPT automations are changed only after shadow verification.

**Tech Stack:** Python 3.13 standard library, `unittest`, GitHub Actions, Google Sheets SSOT.

**Spec:** `docs/superpowers/specs/2026-09-11-nexo-control-plane-v03-design.md`

## Global Constraints

- Preserve the existing five NEXO roles; Core is deterministic infrastructure, not a sixth conversational agent.
- Advisor is science-only and cannot directly create engineering implementation work.
- GitHub Actions is a subordinate backend and never a scientific truth owner.
- Unknown/ambiguous state fails closed.
- Routine execution uses scoped resource locks, not a global lock.
- Existing WORK A:R and EVENTS A:K remain backward compatible.
- No secrets or canonical user/state payloads are committed to the public repository.
- Live automations remain unchanged until shadow tests and SSOT readback pass.

---

### Task 1: Contract models and strict state machine

**Files:**
- Create: `nexo_control_plane/models.py`
- Create: `nexo_control_plane/state_machine.py`
- Create: `nexo_control_plane/__init__.py`
- Test: `tests/test_state_machine.py`

**Interfaces:**
- Produces: `WorkDomain`, `WorkStatus`, `Role`, `Backend`, `WorkRecord`, `can_transition(old, new, external_material=True)`, `transition(work, new_status)`.

- [ ] Write tests proving valid async transitions work, invalid jumps fail closed, and externally executed material work cannot jump from RESULT_AVAILABLE to DONE.
- [ ] Run `python -m unittest tests.test_state_machine -v` and verify RED because package/functions do not yet exist.
- [ ] Implement minimal enums/dataclass/state-transition table.
- [ ] Run the test again and verify GREEN.

### Task 2: Dependencies and scoped locks

**Files:**
- Create: `nexo_control_plane/dependencies.py`
- Create: `nexo_control_plane/locks.py`
- Test: `tests/test_dependencies_and_locks.py`

**Interfaces:**
- Consumes: `WorkRecord`, `WorkStatus`.
- Produces: `dependencies_satisfied(work, by_id) -> bool`, `dependency_gate(work, by_id) -> WorkStatus`, `conflicts(a, b) -> bool`, `acquireable(work, active) -> bool`.

- [ ] Write tests proving missing/unfinished dependency yields WAIT_DEPENDENCY, DONE/VERIFIED satisfies dependencies, failed dependency blocks, and disjoint resource keys do not conflict.
- [ ] Run targeted tests and verify RED.
- [ ] Implement minimal dependency and set-intersection lock logic.
- [ ] Run targeted tests and verify GREEN.

### Task 3: Role policy and deterministic routing

**Files:**
- Create: `nexo_control_plane/policy.py`
- Create: `nexo_control_plane/router.py`
- Test: `tests/test_policy_and_router.py`

**Interfaces:**
- Produces: `may_create_work(role, domain) -> bool`, `engineering_from_signal(signal_type, parent) -> WorkRecord`, `route(work) -> Backend`.

- [ ] Write tests proving Advisor may create SCIENCE but not ENGINEERING, Core may create ENGINEERING only from the typed signal allow-list (including bounded `PROCEDURAL_HYPOTHESIS`), heavy SCIENCE routes to GITHUB_SCIENCE, ENGINEERING code/runtime routes to GITHUB_ENGINEERING, and OLYMPUS defaults LOCAL.
- [ ] Verify RED.
- [ ] Implement minimum policy/routing logic.
- [ ] Verify GREEN.

### Task 4: Scheduler capacity and backpressure

**Files:**
- Create: `nexo_control_plane/scheduler.py`
- Test: `tests/test_scheduler.py`

**Interfaces:**
- Produces: `CapacityProfile`, `SchedulerSnapshot`, `eligible_dispatches(ready, active, snapshot, profile) -> list[WorkRecord]`.

- [ ] Write tests for global=8, per-lane=3, speculative=2, verification backlog stopping speculative work, ready-queue pressure stopping speculative work, and preserving an engineering blocker slot when engineering backlog exists.
- [ ] Verify RED.
- [ ] Implement deterministic sort by blocker/priority/domain reservation and enforce limits.
- [ ] Verify GREEN.

### Task 5: Execution/result envelopes and verification gate

**Files:**
- Create: `nexo_control_plane/envelopes.py`
- Create: `nexo_control_plane/verification.py`
- Test: `tests/test_envelopes_and_verification.py`

**Interfaces:**
- Produces: `ExecutionEnvelope`, `ResultEnvelope`, `build_execution_envelope(work, source_revision, input_hash, seed=None)`, `result_is_verifiable(result)`, `can_learn(work)`, `can_close(work)`.

- [ ] Write tests proving required identifiers/hashes are enforced, unverified result cannot teach/close, VERIFIED can teach, and DONE requires verified external work.
- [ ] Verify RED.
- [ ] Implement immutable dataclasses plus gate functions.
- [ ] Verify GREEN.

### Task 6: Idempotent reconciliation and transition events

**Files:**
- Create: `nexo_control_plane/reconcile.py`
- Create: `nexo_control_plane/events.py`
- Test: `tests/test_reconcile.py`
- Test: `tests/test_events.py`

**Interfaces:**
- Produces: `ExternalRunState`, `ReconcileDecision`, `reconcile(work, external) -> ReconcileDecision`, `EventRecord`, and `make_transition_event(...) -> EventRecord`.

- [ ] Write tests for RUNNING→RESULT_AVAILABLE on successful completion, failed-with-checkpoint→CHECKPOINTED, missing run after dispatch→BLOCKED, duplicate correlation/run conflict→BLOCKED, and idempotent NO_OP when already aligned.
- [ ] Write tests proving transition event IDs/dedupe keys are stable for identical causal inputs and change when the transition identity changes.
- [ ] Verify RED.
- [ ] Implement pure reconciliation and deterministic event identity logic with no provider calls.
- [ ] Verify GREEN.

### Task 7: Shadow planner CLI

**Files:**
- Create: `nexo_control_plane/shadow.py`
- Create: `nexo_control_plane/cli.py`
- Create: `tests/fixtures/shadow_snapshot.json`
- Test: `tests/test_shadow.py`

**Interfaces:**
- Produces: `build_shadow_plan(snapshot) -> dict` and `python -m nexo_control_plane.cli shadow <snapshot.json>`.

- [ ] Write test fixture with independent science, engineering blocker, dependency-bound work, and speculative work.
- [ ] Write tests proving output contains dispatch candidates, waits, conflicts, and pressure signals without mutating input.
- [ ] Verify RED.
- [ ] Implement pure shadow planner and JSON CLI.
- [ ] Verify GREEN.

### Task 8: CI and operator documentation

**Files:**
- Create: `.github/workflows/nexo-control-plane-ci.yml`
- Create: `nexo_control_plane/README.md`

**Interfaces:**
- CI command: `python -m unittest discover -s tests -v` on Python 3.13.

- [ ] Add PR/push/manual CI with `actions/checkout@v7` and `actions/setup-python@v7`.
- [ ] Document role boundaries, state machine, shadow operation, capacity defaults, rollback, and the rule that no secrets/state payloads belong in the public repo.
- [ ] Run full local verification command and require zero failures.

### Task 9: Backward-compatible SSOT migration

**Files:**
- Modify Google Sheet `NEXO · SSOT CANONICAL`, WORK row 1 and EVENTS row 1.
- Modify SYSTEM policy rows by superseding current GitHub-science and global-lock semantics without deleting provenance.

**Interfaces:**
- WORK S:Z = domain, execution_backend, external_run_id, dependency_ids, resource_keys, attempt, checkpoint_ref, verification_status.
- EVENTS L:U = correlation_id, source_role, target_role, state_from, state_to, payload_ref, resource_key, severity, dedupe_key, acknowledged_at.

- [ ] Write headers only into unused columns; preserve all existing A:R/A:K content.
- [ ] Add/supersede SYSTEM rows for subordinate GitHub compute backend, scoped locks, control-plane version, capacity profile, and verification gate.
- [ ] Read back exact ranges and verify all values.

### Task 10: Live automation contract update after shadow verification

**Files:**
- Modify prompts of Advisor, Executor, Learner, Emergent, Daily via Automations only after Tasks 1–9 verify.

**Interfaces:**
- Advisor: science strategy only; emits typed CAPABILITY_GAP instead of coding.
- Executor: scheduler/router semantics; asynchronous external runs; no blocking wait; scoped locks/dependencies; verification before DONE.
- Learner: OBJECT/PROCEDURAL namespaces; verified evidence bundles only.
- Emergent: checks active/in-flight work before proposing; procedural hypothesis routes through Core; obeys exploration/backpressure budget.
- Daily: material-delta aggregation only.

- [ ] Snapshot current prompts/IDs for rollback.
- [ ] Update prompts without changing schedules or automation count.
- [ ] Read back automation definitions and verify role boundaries and causal order remain intact.
- [ ] If any prompt readback is incomplete or ambiguous, restore the previous prompt and report the blocker.
