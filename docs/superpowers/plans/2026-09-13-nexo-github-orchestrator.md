# NEXO GitHub-native Orchestrator v0.1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a GitHub-native NEXO control plane that validates campaign manifests, computes deterministic execution plans, dispatches only registered workflows, separates technical completion from scientific promotion, and emits machine-readable result/state artifacts without requiring n8n or a VM.

**Architecture:** GitHub Actions is the control plane. Repository-owned Python modules validate declarative campaign/result contracts and state transitions; workflows call those modules and use GitHub-native dispatch/artifacts for execution receipts. v0.1 proves the contract with a cheap no-op executor and keeps all existing scientific workflows untouched.

**Tech Stack:** Python 3.11, PyYAML, jsonschema, pytest, GitHub Actions, GitHub CLI, JSON/YAML.

**Spec:** `docs/superpowers/specs/2026-09-13-nexo-github-orchestrator-design.md`

## Global Constraints

- No VM, n8n, or always-on service.
- Campaign manifests are data only; arbitrary shell/command fields are forbidden.
- Only repository-registered executors and validators may run.
- A green GitHub workflow alone can never yield scientific `PASSED`.
- Non-finite metrics must serialize as JSON-safe `null` and fail closed.
- Dry-run validates everything but dispatches nothing.
- Retry budget is explicit and bounded; scientific gate failure is never auto-retried.
- Existing PEER physics, priors, likelihoods, scientific SSOT authority, and production science workflows are not modified in v0.1.
- First end-to-end executor is cheap/no-op, not CAMB/MCMC.

---

### Task 1: Campaign contract and validation

**Files:**
- Create: `.nexo/schemas/campaign.schema.json`
- Create: `.nexo/campaigns/example-noop.yaml`
- Create: `scripts/nexo/__init__.py`
- Create: `scripts/nexo/contracts.py`
- Create: `tests/nexo/test_campaign_contract.py`

**Interfaces:**
- Produces: `load_campaign(path: Path) -> dict`, `validate_campaign(campaign: dict) -> dict`, `EXECUTOR_REGISTRY`, `VALIDATOR_REGISTRY`.
- Consumers: execution planner and workflows in later tasks.

- [ ] **Step 1: Write failing tests** covering valid campaign, unknown executor, unknown validator, duplicate test IDs, missing dependencies, cycles, budget overflow, and command-injection fields.

Representative test:

```python
from scripts.nexo.contracts import validate_campaign


def test_unknown_executor_is_rejected(valid_campaign):
    valid_campaign["tests"][0]["executor"] = "shell"
    with pytest.raises(ValueError, match="unknown executor"):
        validate_campaign(valid_campaign)
```

- [ ] **Step 2: Run** `python -m pytest -q tests/nexo/test_campaign_contract.py` and verify RED.
- [ ] **Step 3: Implement schema + validation** with `jsonschema.Draft202012Validator`, strict `additionalProperties: false`, executor registry containing only `github_workflow`, and validator registry initially containing `artifact_presence_only` and `contract_test_pass`.
- [ ] **Step 4: Add semantic graph checks** for duplicate IDs, missing dependencies, cycles, `len(tests) <= budget.max_tests`, `max_parallel <= max_tests`, and forbidden keys such as `run`, `command`, `shell`, `script` anywhere in the manifest.
- [ ] **Step 5: Run tests** and verify PASS.
- [ ] **Step 6: Commit** with `feat: add NEXO campaign contract`.

### Task 2: Execution planner and state machine

**Files:**
- Create: `scripts/nexo/planner.py`
- Create: `scripts/nexo/state.py`
- Create: `tests/nexo/test_planner_state.py`
- Create: `.nexo/state/README.md`

**Interfaces:**
- Consumes: validated campaign dict from Task 1.
- Produces: `build_execution_plan(campaign: dict, completed: dict[str, str] | None = None) -> dict`; `transition_test_state(current: str, target: str) -> str`; `transition_campaign_state(current: str, target: str) -> str`.

- [ ] **Step 1: Write failing tests** for deterministic runnable-order, dependency blocking, `max_parallel`, retry budget, legal/illegal state transitions, and dry-run plan metadata.

Representative test:

```python
def test_planner_enforces_max_parallel(valid_campaign):
    valid_campaign["budget"]["max_parallel"] = 1
    plan = build_execution_plan(validate_campaign(valid_campaign))
    assert len(plan["runnable_now"]) == 1
```

- [ ] **Step 2: Run** `python -m pytest -q tests/nexo/test_planner_state.py` and verify RED.
- [ ] **Step 3: Implement deterministic topological planning** sorted by manifest order, returning `runnable_now`, `blocked`, `terminal`, `budget`, and `dry_run_safe: true`.
- [ ] **Step 4: Implement explicit transition maps** for campaign and test states from the spec, raising `ValueError` on illegal transitions.
- [ ] **Step 5: Run tests** and verify PASS.
- [ ] **Step 6: Commit** with `feat: add NEXO planner and state machine`.

### Task 3: Result envelope and validators

**Files:**
- Create: `.nexo/schemas/result.schema.json`
- Create: `scripts/nexo/results.py`
- Create: `scripts/nexo/validators.py`
- Create: `tests/nexo/test_results_validators.py`

**Interfaces:**
- Produces: `json_safe(value)`, `build_result_envelope(...) -> dict`, `validate_result_schema(result: dict) -> dict`, `run_validator(name: str, execution: dict, diagnostics: dict | None) -> dict`.
- Validator return shape: `{status: PASSED|NOT_PROMOTED|FAILED|BLOCKED, metrics: dict, reasons: list[str]}`.

- [ ] **Step 1: Write failing tests** for NaN/Inf conversion to `null`, workflow success without validator not becoming `PASSED`, `NOT_PROMOTED` distinct from `FAILED`, malformed diagnostics failing closed, and artifact-presence validation.

Representative test:

```python
def test_nonfinite_metric_is_json_safe_and_not_promoted():
    result = run_validator(
        "contract_test_pass",
        {"status": "COMPLETED", "conclusion": "success", "artifact_names": ["x"]},
        {"score": float("inf"), "passed": False},
    )
    assert result["status"] == "NOT_PROMOTED"
    assert result["metrics"]["score"] is None
    json.dumps(result, allow_nan=False)
```

- [ ] **Step 2: Run** `python -m pytest -q tests/nexo/test_results_validators.py` and verify RED.
- [ ] **Step 3: Implement recursive JSON sanitization** converting non-finite floats to `None`.
- [ ] **Step 4: Implement validators** with fail-closed semantics. `artifact_presence_only` passes only when execution succeeded and at least one artifact exists. `contract_test_pass` additionally requires `diagnostics.passed is True`.
- [ ] **Step 5: Implement result schema validation** and provenance fields for campaign commit, validator commit, executor run ID, executor head SHA, workflow, and artifact names.
- [ ] **Step 6: Run tests** and verify PASS.
- [ ] **Step 7: Commit** with `feat: add NEXO result envelope and validators`.

### Task 4: Cheap registered executor for end-to-end proof

**Files:**
- Create: `.github/workflows/nexo-noop-executor.yml`
- Create: `tests/nexo/test_workflow_contracts.py`

**Interfaces:**
- Inputs: `correlation_id`, `campaign_id`, `test_id`, `should_pass`.
- Output artifact: `nexo-executor-result-<correlation_id>` containing `executor-result.json`.
- `run-name` must include the exact correlation ID.

- [ ] **Step 1: Write failing structural test** loading the workflow YAML and asserting `workflow_dispatch`, required inputs, `run-name` correlation, no arbitrary command interpolation, result artifact upload, and least-privilege permissions.
- [ ] **Step 2: Run** `python -m pytest -q tests/nexo/test_workflow_contracts.py` and verify RED.
- [ ] **Step 3: Implement workflow** on Ubuntu 24.04 that writes a deterministic JSON result containing `correlation_id`, campaign/test IDs, `passed`, and GitHub run/head metadata; no external network calls beyond GitHub Actions runtime.
- [ ] **Step 4: Run structural test** and verify PASS.
- [ ] **Step 5: Commit** with `ci: add NEXO noop executor`.

### Task 5: Orchestrator workflow, dry-run, deterministic dispatch and receipts

**Files:**
- Create: `.github/workflows/nexo-orchestrator.yml`
- Create: `scripts/nexo/dispatch.py`
- Create: `tests/nexo/test_dispatch.py`
- Modify: `.nexo/campaigns/example-noop.yaml`

**Interfaces:**
- `make_correlation_id(campaign_id: str, test_id: str, attempt: int, sha: str) -> str`.
- `build_dispatch_command(test: dict, correlation_id: str) -> list[str]` returns an argv vector, never a shell string.
- Workflow artifact: `nexo-campaign-receipt-<campaign>-<run_id>` containing `execution-plan.json`, dispatch receipts, normalized results, and `campaign-summary.json`.

- [ ] **Step 1: Write failing unit tests** for correlation uniqueness/stability, workflow registry enforcement, argv construction without shell injection, and `dry_run=True` returning zero dispatches.
- [ ] **Step 2: Run** `python -m pytest -q tests/nexo/test_dispatch.py` and verify RED.
- [ ] **Step 3: Implement `dispatch.py`** with an explicit workflow registry mapping `nexo_noop` to `.github/workflows/nexo-noop-executor.yml`; reject any unregistered workflow name.
- [ ] **Step 4: Implement orchestrator `workflow_dispatch` inputs**: `campaign_path`, `dry_run` default `true`, and `attempt` default `1`. Permissions: `contents: read`, `actions: write`.
- [ ] **Step 5: Implement plan phase** that validates campaign, writes `execution-plan.json`, and exits without dispatch when dry-run is true.
- [ ] **Step 6: Implement execution phase** that dispatches each `runnable_now` test with the unique correlation ID, then resolves the child run by exact `displayTitle == correlation_id` plus workflow/ref/time constraints rather than “latest run”. Poll with a bounded timeout and fail closed if zero or multiple matches exist.
- [ ] **Step 7: Download exact child artifact by resolved run ID**, normalize execution/result data through repository Python modules, run validator, and write per-test result envelopes.
- [ ] **Step 8: Build campaign summary** distinguishing `PASSED`, `NOT_PROMOTED`, `FAILED`, and `BLOCKED`; emit `ready_for_learning: true` only when all required tests are terminal and none is technically unresolved.
- [ ] **Step 9: Upload receipt bundle even on failure** using `if: always()`.
- [ ] **Step 10: Run unit/structural tests** and verify PASS.
- [ ] **Step 11: Commit** with `feat: add GitHub-native NEXO orchestrator`.

### Task 6: CI contract, docs, and branch-level verification

**Files:**
- Create: `.github/workflows/nexo-contract.yml`
- Create: `docs/nexo/ORCHESTRATION.md`
- Modify: `docs/superpowers/specs/2026-09-13-nexo-github-orchestrator-design.md` status line only.

**Interfaces:**
- CI trigger: pushes/PRs touching `.nexo/**`, `scripts/nexo/**`, `tests/nexo/**`, or NEXO workflows.
- CI command: `python -m pytest -q tests/nexo` plus schema/workflow YAML parsing.

- [ ] **Step 1: Add contract workflow** installing `pytest pyyaml jsonschema`, running the NEXO test suite and parsing all NEXO YAML/JSON files.
- [ ] **Step 2: Add explicit structural assertions** that the orchestrator defaults to `dry_run=true`, has no cron schedule, has no `pull_request_target`, does not write to scientific SSOT, and only registered workflows appear in the example campaign.
- [ ] **Step 3: Document operations**: how to create a campaign, dry-run, execute, inspect receipts, interpret `NOT_PROMOTED`, and add a new registered executor/validator.
- [ ] **Step 4: Update design status** to `IMPLEMENTED ON FEATURE BRANCH, PENDING MERGE` only after CI is green.
- [ ] **Step 5: Push-trigger CI and inspect exact run result**; do not claim completion until the new NEXO contract workflow is green.
- [ ] **Step 6: Compare feature branch to `run-peer-segmented-20260911`** and verify no production scientific workflow, physics code, priors, likelihoods, or SSOT logic changed.
- [ ] **Step 7: Commit** with `test: verify NEXO orchestrator v0.1`.

## Self-review

- Spec coverage: campaign schema, state machine, result envelope, dry-run, registries, bounded retries, security boundary, deterministic correlation, validation separation, provenance, receipt artifacts, and no-VM requirement all map to tasks above.
- No placeholders: implementation steps specify files, interfaces, test commands, and expected semantics.
- Type consistency: campaign/result/status names match the design spec; all downstream tasks consume interfaces defined in earlier tasks.
- Deliberate v0.1 limitation: event routing stops at a machine-readable `ready_for_learning` receipt. It does not automatically write Drive/Sheets/Slack or invoke an LLM. That preserves the spec trust boundary and avoids introducing credentials before the control-plane contract is proven.
