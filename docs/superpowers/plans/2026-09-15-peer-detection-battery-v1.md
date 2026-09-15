# PEER Detection Battery V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make D00-D25 executable, auditable, work-bound NEXO scientific gates and expose them as a ready-to-prepare PEER battery.

**Architecture:** TCC owns frozen gate policy/evaluation code and execution contracts. NEXO Tower owns capability registration, campaign/work bindings, dispatch, evidence, and readback. One generic evaluator handles gate-specific metrics from a canonical registry; 26 static task IDs provide capability-level routing while work-bound evidence bindings remain provenance-hashed and fail closed when absent.

**Tech Stack:** Python 3.12, unittest, GitHub Actions, NEXO execution contracts, Tower V06 capability manifest.

**Spec:** `docs/superpowers/specs/2026-09-15-peer-detection-battery-v1.md`

## Global Constraints

- Tower remains the sole authority.
- Runtime PASS must never imply PEER support.
- D00-D25 gate identities and final classes are frozen by spec.
- Missing/invalid scientific evidence returns `INCONCLUSIVE`, never synthetic support.
- D09 may stop expensive anchor-independent detection work, but skipped gates are explicitly recorded.
- Numerical thresholds are campaign policy, not universal statistical laws.
- All scientific input bindings are digestable and included in provenance.

---

### Task 1: Gate registry and evaluators

**Files:**
- Create: `runtime/nexo_execution/peer_detection.py`
- Create: `runtime/nexo_execution/peer_detection_gates.json`
- Create: `runtime/nexo_execution/test_peer_detection.py`

**Interfaces:**
- Produces: `load_gate_registry()`, `evaluate_gate(gate_id, evidence, prior_results=None)`, `synthesise_detection(results)`.

- [ ] Write failing tests for exact D00-D25 coverage, ordering, policy digest, empirical global p-value, anchor ablation, fail-closed missing evidence, and deterministic synthesis.
- [ ] Run `python -m unittest runtime.nexo_execution.test_peer_detection -v` and confirm RED.
- [ ] Implement the registry loader and gate evaluators.
- [ ] Re-run the test module and confirm GREEN.
- [ ] Commit.

### Task 2: Executable gate entrypoint and allowlist

**Files:**
- Create: `benchmarks/peer_detection_gate.py`
- Modify: `runtime/nexo_execution/core.py`
- Extend: `runtime/nexo_execution/test_peer_detection.py`

**Interfaces:**
- Consumes: `evaluate_gate`.
- Produces: 26 task IDs `peer_detection_d00` ... `peer_detection_d25`, all writing `peer_detection_gate_result.json`.

- [ ] Add failing tests asserting all 26 task IDs are allowlisted and map to the generic module with the correct `--gate` argument.
- [ ] Run the focused tests and confirm RED.
- [ ] Add all task mappings and CLI entrypoint.
- [ ] Run focused tests and confirm GREEN.
- [ ] Commit.

### Task 3: Work-bound scientific evidence bindings

**Files:**
- Modify in NEXO Vault: `scripts/run_single_runtime.py`
- Test in NEXO Vault: `services/nexo-api/tests/test_single_runtime.py`

**Interfaces:**
- Work fields accepted under `execution_bindings`: `input_path`, `input_url`, `input_sha256`, `results_bundle_path`.
- Bindings are passed as `NEXO_BINDING_*` environment variables and their canonical SHA-256 is stored in provenance.

- [ ] Add failing tests proving only the whitelisted binding object is forwarded and its hash is stable.
- [ ] Confirm RED in NEXO API CI.
- [ ] Implement forwarding and provenance hashing without mutating the frozen execution contract.
- [ ] Confirm GREEN.
- [ ] Commit.

### Task 4: Frozen gate contracts

**Files:**
- Create: `runtime/nexo_execution/contracts/peer-detection-d00-v1.json` ... `peer-detection-d25-v1.json`

**Interfaces:**
- Each contract binds one task ID to the frozen TCC implementation commit and requires `peer_detection_gate_result.json`.

- [ ] Freeze the implementation commit SHA.
- [ ] Generate 26 contracts with unique execution/test IDs and gate-specific task IDs.
- [ ] Validate every contract with `ExecutionContract.load` and assert contract hashes are stable.
- [ ] Commit.

### Task 5: Canonical NEXO capability map

**Files:**
- Modify in NEXO Vault: `TOWER_V06/manifests/capabilities.json`
- Create in NEXO Vault: `TOWER_V06/contracts/PEER_DETECTION_BATTERY_V1.json`
- Test in NEXO Vault: `services/nexo-api/tests/test_capability_router.py` or a dedicated battery mapping test.

**Interfaces:**
- Capability IDs: `peer.detection.d00.freeze_v1` ... gate-specific IDs through D25.
- All use backend `github_dispatch`, repository `byDenoso/TCC`, workflow `nexo-execution.yml`, and frozen contract names.

- [ ] Add failing tests that every frozen gate has one active capability and one contract binding.
- [ ] Confirm RED.
- [ ] Register all 26 capabilities and the battery contract including execution order and D09 stop policy.
- [ ] Confirm GREEN.
- [ ] Commit.

### Task 6: Battery preparation helper

**Files:**
- Create in NEXO Vault: `scripts/prepare_peer_detection_battery.py`
- Create tests in NEXO Vault: `services/nexo-api/tests/test_peer_detection_battery.py`

**Interfaces:**
- Input: optional per-gate `execution_bindings` map.
- Output: `prepare_batteries`-compatible PRIMARY lane payload with D00-D25 works, exact capability IDs, groups, dependencies, criteria summary, and provenance.

- [ ] Add RED tests for 26 works, exact order, stable IDs, binding propagation, and D09 stop metadata.
- [ ] Implement helper.
- [ ] Confirm GREEN.
- [ ] Commit.

### Task 7: End-to-end verification and merge

- [ ] Run TCC runtime test suite including `test_peer_detection`.
- [ ] Run NEXO API/plugin test suites.
- [ ] Verify all 26 capability definitions resolve and each frozen contract exists.
- [ ] Execute D00 canary end-to-end through NEXO Single Runtime and confirm canonical readback.
- [ ] Review PR diff against the spec.
- [ ] Merge only after all checks pass.