# NEXO v0.6 Backend UX Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make agent boot, queue selection, mutation, and ref resolution one backend contract instead of repeated prompt ceremony.

**Architecture:** Add a dependency-free `nexo_agent_api` service over the Tower filesystem. Discovery comes from a compact active-work index overlaid by hydrated entity files; writes auto-hydrate, apply expected-version control, emit material events, and verify readback. Derived role bootstraps/queues are materialized for one-fetch agent startup.

**Tech Stack:** Python standard library, JSON/JSONL, GitHub Tower.

**Spec:** `docs/superpowers/specs/2026-09-12-nexo-v06-backend-ux-design.md`

## Global Constraints
- GitHub Tower remains canonical.
- Legacy Sheets are read-only fallback only.
- No new DB/service dependency.
- Events only for material transitions.
- Executor eligibility is mechanical.

---

### Task 1: Agent service
**Files:** Create `runtime/nexo_agent_api/service.py`; create `runtime/nexo_agent_api/test_service.py`; create `runtime/nexo_agent_api/__init__.py`.
- [x] Write failing tests for executor eligibility, CAS mutation/readback, stale version rejection, bootstrap and artifact resolution.
- [x] Verify tests fail because service is absent.
- [x] Implement minimal service.
- [x] Verify tests pass.

### Task 2: Indexed discovery and lazy hydration
**Files:** Modify `runtime/nexo_agent_api/service.py`; modify `runtime/nexo_agent_api/test_service.py`.
- [x] Write failing tests for `indexes/active-work.json` discovery and first-write hydration.
- [x] Verify failures.
- [x] Implement index overlay and lazy hydration.
- [x] Verify full suite passes.

### Task 3: Role views
**Files:** Create `runtime/nexo_agent_api/views.py`; create `scripts/build_agent_views.py`.
- [x] Write failing materialization test.
- [x] Implement derived bootstraps and queues.
- [x] Verify full suite passes.

### Task 4: Tower cutover views
**Files:** Add private Tower contract, active-work/decision indexes, role profiles, queues and bootstraps.
- [ ] Materialize current active state from the frozen v0.6 migration bundle.
- [ ] Validate counts and conservative ownership mapping.
- [ ] Read back private GitHub files.

### Task 5: Automation simplification
**Files:** Update five active automation prompts.
- [ ] Point each role at its single bootstrap plus central contract.
- [ ] Remove duplicated CAS/hydration/storage boilerplate.
- [ ] Confirm all five remain enabled and scheduled.

### Task 6: Verification and merge
- [ ] Run agent API tests.
- [ ] Open PR, verify diff and CI.
- [ ] Merge only after green verification.
