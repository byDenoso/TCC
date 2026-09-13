# NEXO Handoff Bus Design

## Goal
Create one canonical communication path between DIRECTOR/ChatGPT, ADVISOR, EXECUTOR and LEARNER without adding another database or queue service.

## Architecture
`TOWER_V06/events/` is the append-only communication bus. Work entities remain canonical state; events carry directed handoffs between roles. `bootstrap/<role>.json` projects a bounded `inbox` from the latest handoff state per `handoff_id`.

## Contract
A handoff event contains: `handoff_id`, `thread_id`, `correlation_id`, `from_role`, `to_role`, `handoff_type`, `entity_ref`, `state`, `next_action`, `event_id`, `event_type`, `material`.

States are `PENDING -> ACK -> DONE` with optional `FAILED`. Only the current recipient sees `PENDING` or `ACK` items in its inbox. `DONE` and `FAILED` are terminal and disappear from actionable inboxes while remaining auditable in events.

## Routing
DIRECTOR may emit to ADVISOR, EXECUTOR or LEARNER. Runtime roles may emit to other runtime roles. `to_role` must be a supported runtime role. The inbox is capped at 5 items, ordered oldest pending first for deterministic consumption.

## Separation of concerns
Work entities carry operational/scientific state. Handoff events carry conversation/coordination only. A handoff never substitutes required Executor eligibility fields on a work entity.

## Integration flow
ADVISOR creates/updates a READY work entity, then emits `WORK_READY` to EXECUTOR. EXECUTOR ACKs, runs, persists result, then emits `WORK_VERIFIED` or `WORK_FAILED` to LEARNER. LEARNER ACKs, writes learning, then emits `LESSON_READY` or `DISCRIMINANT_READY` to ADVISOR. DIRECTOR can inject a handoff using the same contract.

## Failure handling
Duplicate event replays are collapsed by `handoff_id` and latest event order. Unknown roles, illegal state transitions and missing handoff IDs raise `TowerAgentIssue`. Terminal handoffs are immutable except for replay-equivalent reads.

## Success criteria
1. Bootstrap exposes `inbox`, `inbox_count`, `inbox_limit`.
2. PENDING handoff appears only for its recipient.
3. ACK updates the same handoff and keeps it visible to the recipient.
4. DONE removes it from actionable inboxes while preserving event history.
5. Existing queue behavior and five-card queue cap remain unchanged.
6. Unit tests and runtime CI are green.
