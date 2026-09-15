# NEXO Control Plane v0.3

This package is deterministic infrastructure for NEXO. It is intentionally **not** another conversational agent.

## Canonical state

Operational truth is `byDenoso/NEXO-Obsidian-Vault@main:TOWER_V06`.

The write invariant is `READ_SHA_WRITE_READBACK`. GitHub code owns implementation; GitHub Actions executes frozen contracts; projections such as Atlas or Drive do not write back to canonical truth unless a current Tower contract explicitly authorizes it.

## Responsibility split

- **Autoconsistente / Executor:** scientific intake, test planning, dispatch, validation and scientific loop closure.
- **Meta-Improvement:** runtime/system health and repair, never scientific reinterpretation.
- **Core:** deterministic queue/dependency/lock/backpressure/reconciliation policy.
- **Learner:** consumes verified evidence only.
- **Atlas:** read-only projection of Tower state.

## Scientific intake v1

The canonical structured interface is `nexo_submit_scientific_tests_v1`.

Explicit user commands such as `Teste X`, `Rode Y`, `Execute Z` and `Faça o teste W` are eligible for scientific execution intake. Advisory language such as `vale a pena testar X?` or `explique o teste X` is not an execution command.

The ordering invariant is **TOWER_FIRST_DISPATCH**:

```text
explicit user execution intent
  -> normalize + scientific fingerprint
  -> dedupe against canonical TEST state
  -> persist TEST / TEST_GROUP in Tower
  -> exact canonical readback
  -> resolve proven execution capability
  -> one dispatch request per TEST
  -> GitHub Actions
  -> artifact verification
  -> RESULT / EVIDENCE canonicalization
  -> exact readback
  -> next scientific decision
```

Unknown execution capability becomes `CAPABILITY_GAP`; it never authorizes arbitrary shell execution or a silent change to the scientific contract.

The MCP/API boundary is an interface only. It does not become a truth owner and it never receives credentials as tool arguments. Host-managed credentials are required by the eventual hosted runtime.

## Fail-closed rules

- Unknown domain/status/backend: reject.
- Invalid state transition: reject without mutation.
- Missing/failed dependency: do not dispatch.
- Shared resource lock: block only the conflicting work, not the whole system.
- Duplicate external identity: block and reconcile before proceeding.
- Raw GitHub result: never teach and never close canonical work.
- Tower persist/readback failure: never dispatch.
- Artifact verification failure: never canonicalize a scientific result.

## Default capacity

| Control | Default |
|---|---:|
| Global external jobs | 8 |
| Science target | 4 |
| Engineering target | 2 |
| Verification reserve | 1 |
| Burst/blocker reserve | 1 |
| Per lane | 3 |
| Speculative jobs | 2 |
| Verification backlog soft limit | 8 |
| Ready queue soft limit | 20 |

Capacity is a control-plane budget, not a promise to saturate GitHub. Backpressure suppresses speculation before it suppresses decision-relevant/blocking work.

## Shadow planner

The shadow planner accepts a JSON snapshot and returns what it *would* dispatch/wait/block without mutating state:

```bash
python -m nexo_control_plane.cli shadow tests/fixtures/shadow_snapshot.json
```

## External result acceptance

```text
GitHub runner
  -> result/artifact/checkpoint
  -> identity + hash verification
  -> Tower RESULT/EVIDENCE mutation
  -> canonical readback
  -> VERIFIED
  -> scientific loop / DONE
```

GitHub executes contracts. It does not own scientific interpretation or canonical truth.

## Locks

Locks are resource-scoped, e.g. `repo:TCC:portable_camb` or `science:T-DE042`. A structural global lock is reserved for schema/governance migrations only.
