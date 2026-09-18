# NEXO Control Plane v0.3 (shadow-first)

This package is deterministic infrastructure for NEXO. It is intentionally **not** another conversational agent.

## Responsibility split

- **Advisor:** scientific strategy and test prioritization only.
- **Emergent:** scientific/procedural hypotheses; procedural ideas do not become engineering work directly.
- **Core:** deterministic queue/dependency/lock/backpressure/reconciliation policy and typed ENGINEERING generation from failures or capability gaps.
- **Executor:** dispatch/router/run tracking. One logical authority, many workers.
- **Learner:** consumes verified evidence only. OBJECT = science; PROCEDURAL = engineering/runtime.
- **Daily:** aggregates material deltas for the user.

## Fail-closed rules

- Unknown domain/status/backend: reject.
- Invalid state transition: reject without mutation.
- Missing/failed dependency: do not dispatch.
- Shared resource lock: block only the conflicting work, not the whole system.
- Duplicate external identity: block and reconcile before proceeding.
- Raw GitHub result: never teach and never close canonical work.

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

This is the mandatory first deployment mode.

## Canonical state

Canonical state remains in `NEXO · SSOT CANONICAL` on Google Sheets/Drive. This public repository must contain only generic code, tests, and non-sensitive contracts. Do not commit SSOT dumps, personal data, model transcripts, secrets, API keys, or private prompts.

## External result acceptance

```text
GitHub runner
  -> result/artifact/checkpoint
  -> identity + hash verification
  -> Drive persistence/readback
  -> VERIFIED
  -> Learner / DONE
```

GitHub executes contracts. It does not own scientific interpretation or canonical truth.

## Locks

Locks are resource-scoped, e.g. `repo:TCC:portable_camb` or `science:T-DE042`. A structural global lock is reserved for schema/governance migrations only.

## Rollback

The first live cutover changes only role prompts and SSOT-compatible columns. Rollback is restoring the previous prompt contracts; existing WORK/EVENTS columns remain intact and the added columns are backward-compatible.
