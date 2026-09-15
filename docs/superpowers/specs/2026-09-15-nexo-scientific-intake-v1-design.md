# NEXO Scientific Intake v1 — Design

## Goal

Turn explicit user execution commands such as `Teste X`, `Rode Y` and `Execute Z` into canonical scientific TEST entities in `TOWER_V06`, deduplicate them, dispatch executable work through the existing push-based GitHub Actions path, ingest/verify the result, and close the loop without bypassing Tower authority.

## Architecture

The system is split into three boundaries:

1. `ScientificIntakeService` is deterministic domain logic. It parses explicit execution intent, normalizes one or more test requests, computes a semantic fingerprint, resolves duplicate/existing work from a supplied Tower view, and produces a canonical `ScientificIntakePlan`.
2. `ScientificIntakeGateway` performs side effects in strict order: Tower persist + exact readback first, dispatch second. A failed dispatch leaves the TEST canonically `READY` for retry. The gateway never makes scientific decisions.
3. MCP/API exposes one structured operation, `nexo_submit_scientific_tests_v1`, that calls the same service/gateway. MCP is an interface, not a truth owner. ChatGPT, automations, and future clients must all use this contract rather than inventing independent writers.

`TOWER_V06` remains the sole operational truth owner. The existing `nexo/dispatch-runtime` push inbox remains the execution transport. GitHub Actions artifacts remain non-canonical until verified and written back to Tower.

## Command semantics

Execution commands are recognized only when the user is explicitly instructing execution. Supported leading forms include `teste`, `testar`, `rode`, `rodar`, `execute`, `executar`, and `faça o teste` (case-insensitive, accent-insensitive). Questions such as `vale a pena testar X?`, `o que acha do teste X?`, or `explique o teste X` are not execution commands.

A single message may contain multiple execution clauses separated by semicolon/newline or repeated execution verbs. Each clause becomes an independent candidate TEST. One dispatch commit is emitted per TEST because the current `NEXO dispatch` workflow intentionally rejects commits containing more than one request JSON.

## Canonical identity and dedupe

Each normalized test receives a fingerprint computed from a canonical JSON object containing:

- normalized scientific question;
- dataset/stack identifiers when supplied;
- null/rival when supplied;
- method/task/capability when supplied;
- decision rule when supplied;
- model/parameter constraints when supplied.

Volatile fields such as timestamps, correlation IDs, prose formatting and attempt number are excluded.

Dedupe behavior:

- matching terminal TEST -> `DUPLICATE_TERMINAL`; return the existing result/reference and do not dispatch;
- matching READY/DISPATCHED/RUNNING/CHECKPOINTED TEST -> `ATTACH_EXISTING`; do not create or dispatch a duplicate;
- no match -> create a new TEST;
- scientifically material change to any fingerprint field -> new TEST identity.

## TEST and TEST_GROUP persistence

New tests use the existing Tower entity model.

Minimum TEST fields:

- `id`
- `kind=TEST`
- `label`
- `question`
- `status=READY`
- `test_group_id`
- `writer_role=EXECUTOR`
- `entity_version=1`
- `scientific_fingerprint`
- `claim_boundary`
- `decision_rule`
- `provenance_refs`
- `execution_capability`
- `correlation_id`

If the requested `test_group_id` does not exist, create the smallest honest `TEST_GROUP` with `group_kind=AD_HOC` and `navigation_semantics=TERMINAL_NEURAL_NODE`. Creating a TEST and updating its group count must be idempotent.

## Capability resolution

Intake never fabricates an executor. It receives a capability registry view. Resolution is:

- exact declared capability -> dispatch immediately;
- compatible proven capability -> dispatch using the frozen adapter/task contract;
- no capability -> persist TEST as `READY` with `execution_state=CAPABILITY_GAP` and emit an engineering capability request; do not silently change scientific meaning.

The existing allow-listed `execution` adapter remains the only generic dispatch path. Arbitrary shell commands stay forbidden.

## Dispatch contract

For an executable TEST, the gateway writes exactly one JSON request to `byDenoso/TCC@nexo/dispatch-runtime:nexo_dispatch/requests/<TEST_ID>-A<attempt>.json` containing the current dispatch schema:

- `work_id`
- `correlation_id`
- `domain=SCIENCE`
- `adapter=execution`
- `source_revision`
- `attempt`
- `args.runtime_requirement`
- `args.task_id`
- `args.repository`
- `args.required_outputs`
- `args.parameters`
- `args.test_id`
- `args.execute=true`

Tower persistence/readback must succeed before this commit is created.

## Result closure

The eventual closure path is event-first with hourly reconciliation as redundancy:

`Actions completion -> artifact lookup -> schema/hash verification -> Tower RESULT/EVIDENCE mutation -> exact readback -> TEST terminal transition -> TEST_GROUP aggregate reconciliation`.

Until hosted event ingestion is available, the existing Autoconsistente reconciliation loop remains the fallback. Raw Action output never closes a scientific TEST.

## MCP boundary

MCP tool: `nexo_submit_scientific_tests_v1`.

Input:

```json
{
  "utterance": "Teste X; Teste Y",
  "source": "chat",
  "defaults": {
    "test_group_id": "optional",
    "claim_boundary": "optional",
    "decision_rule": "optional"
  }
}
```

Output:

```json
{
  "accepted": true,
  "tests": [
    {
      "test_id": "...",
      "fingerprint": "sha256:...",
      "state": "READY|DISPATCHED|ATTACH_EXISTING|DUPLICATE_TERMINAL|CAPABILITY_GAP",
      "correlation_id": "...",
      "dispatch_ref": "optional",
      "canonical_readback": true
    }
  ]
}
```

The MCP implementation must authenticate to GitHub/Tower using host-managed credentials. Credentials are never accepted as tool arguments and never committed to the repository.

## Observability

Every submitted TEST carries one `correlation_id` across chat intake, Tower entity/event, dispatch request, GitHub run/artifact and result closure.

Minimum derived metrics:

- `time_to_canonical_ready`
- `time_to_dispatch`
- `time_to_result`
- `time_to_canonical_close`
- `failure_stage`

These metrics are operational evidence only and cannot change scientific conclusions.

## Failure semantics

- Tower write/readback failure -> fail closed; no dispatch.
- Dispatch commit failure after canonical READY -> leave TEST READY and return retryable dispatch failure.
- Unknown capability -> CAPABILITY_GAP, not BLOCKED science.
- Duplicate active TEST -> attach to existing identity.
- Duplicate terminal TEST -> reuse existing terminal evidence.
- Artifact verification failure -> do not canonicalize result; emit typed verification failure for Meta-Improvement/reconciliation.

## Acceptance

The feature is accepted when:

1. explicit execution language is recognized while advisory/questions are rejected;
2. multiple commands produce multiple independent plans;
3. fingerprints are stable under formatting/case changes and change under material scientific differences;
4. terminal and active duplicates are not redispatched;
5. Tower-first ordering is enforced;
6. one dispatch request is produced per executable TEST;
7. missing capability yields CAPABILITY_GAP rather than arbitrary execution;
8. the MCP descriptor exposes the same intake service contract;
9. all unit tests and existing control-plane tests pass;
10. a canary proves one structured test can travel intake -> dispatch request -> GitHub Actions artifact without violating Tower authority.
