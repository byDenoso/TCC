# Portable CAMB Execution Capability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `peer.camb.exact_v2` an executable fail-closed capability for NEXO execution, including GitHub Actions.

**Architecture:** Add optional capability requirements to execution contracts, resolve them before task launch, and isolate portable CAMB materialization/verification in `runtime/portable_camb/runtime.py`. Existing tasks remain unchanged unless they explicitly require the capability.

**Tech Stack:** Python 3.12, unittest, GitHub Actions, bash launcher, SHA-256 verification.

**Spec:** `docs/superpowers/specs/2026-09-17-portable-camb-execution-capability-design.md`

## Global Constraints

- Preserve frozen scientific task parameters and decision rules.
- No implicit system/pip CAMB fallback for `peer.camb.exact_v2`.
- Verify archive and `camblib.so` SHA256 before scientific execution.
- Existing contracts without `required_capabilities` remain compatible.
- Capability failure is fail-closed and happens before task execution.

---

### Task 1: Contract capability requirements

**Files:**
- Modify: `runtime/nexo_execution/core.py`
- Test: `runtime/nexo_execution/test_execution.py`

**Interfaces:**
- Consumes: existing `ExecutionContract.from_dict()`.
- Produces: `ExecutionContract.required_capabilities: list[str]`, default `[]`.

- [ ] Write a failing unit test proving a v2 contract accepts `required_capabilities=["peer.camb.exact_v2"]` and legacy contracts omit it safely.
- [ ] Run `python -m unittest runtime.nexo_execution.test_execution -v` and verify the new assertion fails for the missing field/API.
- [ ] Add the optional field with backward-compatible defaulting.
- [ ] Re-run the test suite and verify PASS.

### Task 2: Portable CAMB runtime resolver

**Files:**
- Create: `runtime/portable_camb/runtime.py`
- Create: `runtime/portable_camb/test_runtime.py`

**Interfaces:**
- Produces: `prepare_portable_camb(env: dict[str,str] | None = None) -> dict[str,str]`.
- Returns environment additions including `NEXO_CAPABILITY_PEER_CAMB_EXACT_V2_LAUNCHER`, CAMB/CosmoRec versions, archive SHA256, and camblib SHA256.

- [ ] Write failing tests for missing payload fail-closed, bad archive SHA rejection, and verified expanded payload environment export.
- [ ] Run `python -m unittest runtime.portable_camb.test_runtime -v` and verify RED.
- [ ] Implement deterministic source resolution, extraction to temporary directory, manifest/hash verification, launcher validation, and provenance env output.
- [ ] Re-run tests and verify PASS.

### Task 3: Pre-execution capability preparation

**Files:**
- Modify: `runtime/nexo_execution/core.py`
- Test: `runtime/nexo_execution/test_execution.py`

**Interfaces:**
- Add `prepare_required_capabilities(contract, env) -> dict[str,str]`.
- `LocalProvider.submit()` calls it before `subprocess.run`.

- [ ] Write failing tests proving CAMB preparation happens before task launch and failure prevents subprocess execution.
- [ ] Run targeted unit tests and verify RED.
- [ ] Implement a minimal execution capability registry mapping `peer.camb.exact_v2` to `prepare_portable_camb`.
- [ ] Inject returned environment additions into the scientific task environment.
- [ ] Re-run execution and portable-CAMB tests and verify PASS.

### Task 4: CI coverage and canonical capability metadata

**Files:**
- Modify: `.github/workflows/nexo-execution-tests.yml`
- Modify: `runtime/portable_camb/README.md`

**Interfaces:**
- CI runs `runtime.portable_camb.test_runtime`.
- Documentation specifies contract opt-in and Actions environment source.

- [ ] Add the portable runtime unit test command to CI.
- [ ] Document `required_capabilities` and `NEXO_PEER_CAMB_ARCHIVE(_URL)`.
- [ ] Push and verify the `NEXO Runtime Tests` workflow passes.

### Task 5: Readback verification

**Files:** none unless a defect is found.

- [ ] Fetch the final files from `main` and verify capability ID, hashes, and fail-closed behavior are present.
- [ ] Inspect the corresponding GitHub Actions run and confirm all runtime tests pass.
- [ ] Confirm no frozen PEER/GZ scientific contract was modified as part of the capability implementation.