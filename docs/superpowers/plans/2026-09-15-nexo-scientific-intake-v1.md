# NEXO Scientific Intake v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert explicit chat test commands into canonical Tower-first TEST creation, dedupe, capability resolution, one-request-per-test GitHub dispatch, and a reusable MCP/API tool contract.

**Architecture:** Keep scientific interpretation outside the transport layer. A pure intake module parses/normalizes commands and computes stable fingerprints; a small orchestration service performs Tower-first persistence before producing dispatch envelopes; an MCP facade exposes exactly the same service contract. Existing `nexo-dispatch.yml` remains the execution backend.

**Tech Stack:** Python 3.13 standard library, `unittest`, existing NEXO control-plane modules, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-09-15-nexo-scientific-intake-v1-design.md`

## Global Constraints

- `byDenoso/NEXO-Obsidian-Vault@main:TOWER_V06` remains canonical operational truth.
- One request JSON per dispatch commit.
- Unknown capability fails to `CAPABILITY_GAP`; no arbitrary shell execution.
- Tower persistence/readback must happen before dispatch.
- Credentials never appear in tool inputs, commits, logs, or canonical entities.
- Raw GitHub Actions artifacts are non-canonical until verified and read back.

---

### Task 1: Pure command intake and fingerprinting

**Files:**
- Create: `tests/test_scientific_intake.py`
- Create: `nexo_control_plane/scientific_intake.py`

**Interfaces:**
- Produces: `is_execution_utterance(text: str) -> bool`
- Produces: `parse_execution_clauses(text: str) -> list[str]`
- Produces: `ScientificTestSpec`
- Produces: `scientific_fingerprint(spec: ScientificTestSpec) -> str`

- [ ] **Step 1: Write failing tests** covering imperative recognition, advisory rejection, two-clause splitting, formatting-stable fingerprint, and material-change fingerprint.
- [ ] **Step 2: Push tests only and confirm `NEXO control-plane CI` fails because `nexo_control_plane.scientific_intake` does not exist.**
- [ ] **Step 3: Implement the minimal pure module** with accent-insensitive imperative detection, clause parsing, immutable dataclass, canonical JSON fingerprinting and safe identifier helper.
- [ ] **Step 4: Push implementation and confirm the focused tests and full control-plane CI pass.**

### Task 2: Dedupe and capability planning

**Files:**
- Modify: `tests/test_scientific_intake.py`
- Modify: `nexo_control_plane/scientific_intake.py`

**Interfaces:**
- Produces: `ExistingTestRef`
- Produces: `CapabilityRef`
- Produces: `IntakeDisposition`
- Produces: `ScientificIntakePlan`
- Produces: `plan_scientific_test(spec, existing_tests, capabilities) -> ScientificIntakePlan`

- [ ] **Step 1: Add failing tests** for terminal duplicate, active duplicate, exact capability, compatible capability, and missing capability.
- [ ] **Step 2: Confirm RED in CI.**
- [ ] **Step 3: Implement minimal planning logic** with `DUPLICATE_TERMINAL`, `ATTACH_EXISTING`, `READY`, and `CAPABILITY_GAP` dispositions.
- [ ] **Step 4: Confirm GREEN for focused and full CI.**

### Task 3: Tower-first orchestration and dispatch envelope

**Files:**
- Create: `tests/test_scientific_submit.py`
- Create: `nexo_control_plane/scientific_submit.py`

**Interfaces:**
- Consumes: `ScientificIntakePlan`
- Produces protocol: `TowerGateway.persist_test(entity) -> dict`
- Produces protocol: `TowerGateway.readback_test(test_id) -> dict`
- Produces protocol: `DispatchGateway.submit(request) -> str`
- Produces: `ScientificSubmitService.submit(plan) -> SubmitReceipt`
- Produces: `build_dispatch_request(plan, persisted_entity) -> dict`

- [ ] **Step 1: Write failing tests** proving Tower persist occurs before dispatch, failed readback prevents dispatch, dispatch failure leaves the receipt retryable/READY, active/terminal duplicates do not dispatch, and executable tests emit exactly one request payload.
- [ ] **Step 2: Confirm RED.**
- [ ] **Step 3: Implement the smallest orchestration service** using injected gateways so transport remains testable and host-specific.
- [ ] **Step 4: Confirm GREEN.**

### Task 4: MCP/API facade

**Files:**
- Create: `tests/test_mcp_scientific_tools.py`
- Create: `nexo_control_plane/mcp_scientific_tools.py`

**Interfaces:**
- Produces: `tool_descriptor() -> dict`
- Produces: `submit_scientific_tests_tool(payload: dict, service_factory) -> dict`
- Tool name: `nexo_submit_scientific_tests_v1`

- [ ] **Step 1: Write failing tests** for tool name/schema, rejection of missing utterance, no credential fields in schema, batch receipt shape, and delegation to the same submit service.
- [ ] **Step 2: Confirm RED.**
- [ ] **Step 3: Implement the MCP facade** without introducing a second scientific execution path.
- [ ] **Step 4: Confirm GREEN.**

### Task 5: Correlation and closure telemetry primitives

**Files:**
- Create: `tests/test_execution_telemetry.py`
- Create: `nexo_control_plane/execution_telemetry.py`

**Interfaces:**
- Produces: `ExecutionTrace`
- Produces: `derive_latency_metrics(trace) -> dict`
- Produces: `classify_failure_stage(trace) -> str | None`

- [ ] **Step 1: Write failing tests** for full trace latency metrics, missing-stage handling, and failure-stage attribution.
- [ ] **Step 2: Confirm RED.**
- [ ] **Step 3: Implement pure telemetry derivation.**
- [ ] **Step 4: Confirm GREEN and full CI.**

### Task 6: Documentation and runtime integration contract

**Files:**
- Modify: `nexo_control_plane/README.md`
- Modify: `nexo_dispatch/README.md`

**Interfaces:**
- Documents: explicit chat command semantics, MCP boundary, Tower-first ordering, one-request-per-commit rule, result closure fallback.

- [ ] **Step 1: Add documentation assertions to an existing/new test** that checks the MCP tool name and Tower-first invariant appear in the docs.
- [ ] **Step 2: Confirm RED.**
- [ ] **Step 3: Update docs with exact runtime contract.**
- [ ] **Step 4: Confirm GREEN.**

### Task 7: Tower capability registration

**Files in `byDenoso/NEXO-Obsidian-Vault`:**
- Create: `TOWER_V06/contracts/NEXO_SCIENTIFIC_INTAKE_V1.json`
- Update: `TOWER_V06/CONTROL.json`

**Interfaces:**
- Registers MCP/API capability `nexo_submit_scientific_tests_v1`.
- Declares canonical truth owner and `TOWER_FIRST_DISPATCH` ordering.
- Keeps `mcp_state` distinct from hosting status until a hosted endpoint passes canary.

- [ ] **Step 1: Write the frozen contract JSON on the feature branch and validate it against existing Tower conventions.**
- [ ] **Step 2: Update CONTROL only with declarative capability state; do not claim hosting before proof.**
- [ ] **Step 3: Read both files back exactly.**

### Task 8: End-to-end canary and merge

**Files:**
- Create one non-secret canary request under `nexo_dispatch/requests/` only after the feature branch code is green.

**Interfaces:**
- Canary must use an existing proven allow-listed execution capability and a synthetic/non-scientific canary identity; it must not create a fake scientific claim.

- [ ] **Step 1: Run full control-plane CI on the feature branch.**
- [ ] **Step 2: Create one canary request and verify the dispatch workflow run/artifact.**
- [ ] **Step 3: Verify correlation ID and result schema.**
- [ ] **Step 4: Open PR(s), review diff, merge only after CI/readback are green.**
