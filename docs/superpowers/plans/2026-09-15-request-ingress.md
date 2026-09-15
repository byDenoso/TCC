# NEXO Request Ingress Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an idempotent, compact, task-only request ingress that binds requests from any chat to canonical NEXO WORK.

**Architecture:** Add a focused `ingress.py` protocol installed on `AgentService`. It accepts structured material intent, fingerprints it deterministically, resolves explicit continuation or duplicate WORK before create, compacts request provenance, emits request events and verifies readback. Existing entity-backed role queues consume the result; canonical entities must not be hidden by stale active indexes.

**Tech Stack:** Python 3.12 stdlib, unittest, file-backed NEXO agent runtime, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-09-15-request-ingress-design.md`

## Global Constraints
- TOWER_V06 remains state authority; this repo is code truth.
- Only actionable material task intent becomes WORK.
- No raw chat/transcript persistence.
- MERGE before CREATE.
- Terminal duplicate requests never resurrect WORK.
- Chat/thread references are provenance only.
- Maximum retained request refs/source thread ids: 20.
- Every material write requires readback.

---

### Task 1: Request ingress behavior

**Files:**
- Create: `runtime/nexo_agent_api/test_request_ingress.py`
- Create: `runtime/nexo_agent_api/ingress.py`
- Modify: `runtime/nexo_agent_api/__init__.py`
- Modify: `.github/workflows/nexo-execution-tests.yml`

**Interfaces:**
- Produces: `AgentService.ingest_request(*, thread_id: str, action: str, subject: str, domain: str, owner_role: str, scope: str = "", constraints: list[str] | None = None, acceptance: list[str] | None = None, priority: str = "NORMAL", correlation_id: str | None = None, target_work_id: str | None = None, actionable: bool = True) -> dict`
- Produces result keys: `admitted`, `outcome`, `work_id`, `request_fingerprint`, `readback`, `event_id` when material.

- [ ] **Step 1: Write failing tests**

Create tests for: duplicate request across two chats merges into one WORK; different task creates another WORK; non-actionable request persists nothing; explicit target resolves existing WORK; terminal duplicate is not resurrected; no raw chat field exists; refs compact after 20 while `request_count` remains exact.

- [ ] **Step 2: Run tests to verify RED**

GitHub Actions command must include:

```bash
python -m unittest runtime.nexo_agent_api.test_request_ingress -v
```

Expected: FAIL because `AgentService.ingest_request` / ingress protocol does not exist.

- [ ] **Step 3: Implement minimal ingress protocol**

`ingress.py` must:
- normalize only compact structured intent;
- reject `actionable=False` without write/event;
- compute SHA-256 fingerprint from canonical normalized intent;
- resolve target WORK first, then active duplicate, then terminal duplicate;
- create `WORK::REQ::<16-hex>` for new task;
- store compact `request_summary`, fingerprint, request count/timestamps, max 20 refs and source threads;
- preserve existing status on merge;
- emit `REQUEST_INGESTED`, `REQUEST_MERGED`, `REQUEST_TERMINAL_MATCH`;
- verify entity readback after create/merge;
- never accept/store a `raw_text` field.

- [ ] **Step 4: Run request ingress tests to verify GREEN**

Expected: all request-ingress tests PASS.

- [ ] **Step 5: Run complete NEXO runtime test workflow**

Expected: all existing NEXO runtime unit tests PASS.

---

### Task 2: Canonical entity visibility over stale indexes

**Files:**
- Modify: `runtime/nexo_agent_api/service.py`
- Modify: `runtime/nexo_agent_api/test_request_ingress.py`

**Interfaces:**
- `_work_items()` continues returning canonical WORK dicts; entity files override or extend stale `indexes/active-work.json` projection.

- [ ] **Step 1: Add failing regression test**

Create a stale active index, ingest a new canonical WORK, then assert `queue_for(owner_role)` can see it.

- [ ] **Step 2: Run test to verify RED**

Expected: new canonical WORK is absent because current `_work_items()` only overlays entity files already named by the index.

- [ ] **Step 3: Implement minimal fix**

When an active index exists, load index cards, then scan all `entities/work/*.json` and merge every valid canonical entity by id, not only ids already present in the index.

- [ ] **Step 4: Run regression and full workflow**

Expected: regression PASS; all existing tests PASS.

---

### Task 3: Canonical runtime contract

**Files:**
- Create after code verification in state repo: `TOWER_V06/contracts/REQUEST_INGRESS_V1.json`

**Interfaces:**
- Declares admission, idempotency, compaction, lifecycle and readback invariants implemented by code truth.

- [ ] **Step 1: Add the contract only after code tests are green**
- [ ] **Step 2: Read back exact contract content from canonical `main` after merge/persistence**
- [ ] **Step 3: Verify no new scheduler/database/service/agent was introduced**

---

### Task 4: Final verification and integration

**Files:** no new production files unless verification exposes a defect.

- [ ] **Step 1: Run/inspect GitHub Actions on the feature branch**
- [ ] **Step 2: Confirm test suite green and inspect branch diff**
- [ ] **Step 3: Merge the feature branch to `main` using the existing repository integration path**
- [ ] **Step 4: Read back `main` code and canonical contract**
- [ ] **Step 5: Report invariants and exact commit(s)**
