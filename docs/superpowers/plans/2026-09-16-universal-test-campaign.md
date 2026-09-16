# Universal Test Campaign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Canonicalize campaigns/tests/runs before dispatch and expose generic campaign drill-down in Atlas without project-specific frontend logic.

**Architecture:** Extend the existing Tower mutation path with first-class campaign/run/result/artifact creation and a universal `register_test` ingress that resolves hierarchy before dispatch. Extend the generic graph projection with route/status metadata, then make Atlas render/navigate campaign nodes from those generic fields.

**Tech Stack:** Python unittest/runtime modules in `byDenoso/TCC`; React/TypeScript/Node tests in `byDenoso/Pantheon`.

**Spec:** `docs/superpowers/specs/2026-09-16-universal-test-campaign-design.md`

## Global Constraints

- TEST and CHECK remain semantically distinct; only TEST is graph-visible by default.
- Operational and analytical status are separate fields.
- Executors do not invent TEST identity.
- Frontends consume entity types/relations/domain, never project-specific names.
- Campaign/test routes are derived generically from entity type/id.

---

### Task 1: Canonical campaign/run creation

**Files:**
- Modify: `runtime/nexo_agent_api/mutations.py`
- Test: `runtime/nexo_agent_api/test_universal_test_ingress.py`

**Interfaces:**
- Consumes: `apply_mutation_request(root, request)`
- Produces: canonical create support for `campaign`, `run`, `result`, `artifact`, `project`

- [ ] Write failing tests creating CAMPAIGN and RUN through mutation writer with exact readback.
- [ ] Run focused unittest and verify failure because entity kinds are not creatable.
- [ ] Extend `_CREATABLE_ENTITY_KINDS` minimally.
- [ ] Run focused unittest and verify pass.

### Task 2: Universal register_test ingress

**Files:**
- Create: `runtime/nexo_agent_api/test_registry.py`
- Test: `runtime/nexo_agent_api/test_universal_test_ingress.py`
- Modify: `runtime/nexo_agent_api/__init__.py`

**Interfaces:**
- Produces: `register_test(root, *, test_id, domain, title, objective, campaign_id, campaign_title=None, test_group_id=None, test_group_title=None, parent_id=None, project_id=None, capability_id=None, writer_role="ADVISOR", correlation_id=None) -> dict`
- Returns: `test_id`, `run_id`, `campaign_id`, optional `test_group_id`, mutation receipts, `readback="PASS"`

- [ ] Write failing test asserting campaign/test-group/test/run exist before return, parent relations are canonical refs, and TEST has separate `operational_status`/`analytical_status`.
- [ ] Verify RED.
- [ ] Implement minimal registry using canonical mutation writer; reuse existing entities rather than overwrite.
- [ ] Verify GREEN and regression tests.

### Task 3: Generic graph projection metadata

**Files:**
- Modify: `runtime/nexo_core/projection.py`
- Create/Test: `runtime/nexo_core/test_campaign_projection.py`

**Interfaces:**
- Projection node fields add `route`, `operational_status`, `analytical_status`, `campaign_id`, `test_group_id`, `parent_id`, `project_id` when available.

- [ ] Write failing projection test with COSMOLOGY and OLYMPUS campaigns/tests.
- [ ] Verify roots remain domain-driven and routes are derived generically.
- [ ] Implement route derivation and metadata passthrough.
- [ ] Verify snapshot validation and regression suite.

### Task 4: Atlas campaign drill-down contract

**Files (Pantheon):**
- Modify: `atlas-control-tower/src/graph-engine/graph-entity-contract.ts`
- Modify: `atlas-control-tower/src/graph-engine/live-projection.ts`
- Modify: `atlas-control-tower/src/graph-engine/GraphExplorer.tsx`
- Create/Modify tests under: `atlas-control-tower/test/`

**Interfaces:**
- Campaign nodes expose generic `route` and domain-derived grouping.
- Selecting a CAMPAIGN exposes an action to navigate to `/campaigns/:id` and linked tests.

- [ ] Add failing contract tests for CAMPAIGN type, domain root, and derived route.
- [ ] Verify RED.
- [ ] Extend entity contract/projection without PEER/Olympus special cases.
- [ ] Add generic campaign action in GraphExplorer.
- [ ] Verify unit/contract tests and TypeScript build.

### Task 5: Campaign detail route

**Files (Pantheon):**
- Modify: `atlas-control-tower/src/App.tsx` or current router source
- Create: `atlas-control-tower/src/pages/CampaignPage.tsx`
- Test: route/page contract test

**Interfaces:**
- Route: `/campaigns/:campaignId`
- Reads generic live graph/campaign data and lists TEST_GROUP/TEST children.

- [ ] Write failing route/page test.
- [ ] Verify RED.
- [ ] Implement generic campaign page and navigation.
- [ ] Verify GREEN, TypeScript, production build.

### Task 6: Verification and persistence

- [ ] Run TCC focused + full runtime tests available in CI.
- [ ] Run Pantheon unit/contract tests, TypeScript and production build through CI.
- [ ] Inspect CI/status for both feature branches.
- [ ] Only after green, fast-forward/merge into `main` or report any external deployment blocker.
