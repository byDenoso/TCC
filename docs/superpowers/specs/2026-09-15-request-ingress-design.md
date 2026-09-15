# NEXO Idempotent Request Ingress Design

## Goal
Bind material task requests from any chat to canonical NEXO WORK without making chat history or model memory authoritative.

## Authority
- Canonical operational state remains `byDenoso/NEXO-Obsidian-Vault@main:TOWER_V06`.
- This repository remains code truth for runtime behavior.
- Chat/thread identifiers are provenance only and never required to continue a WORK.

## Admission
Only actionable material task intents are admitted. Conversational questions, explanations, brainstorming, status reads and raw chat text are not persisted as WORK.

The ingress API consumes an already compact, structured intent rather than a transcript. Required task intent fields are `action`, `subject`, `domain`, and `owner_role`; optional fields include `scope`, `constraints`, `acceptance`, `priority`, and `target_work_id`.

## Idempotency and dedupe
A request fingerprint is SHA-256 over canonical JSON containing the normalized material intent (`action`, `subject`, `scope`, `domain`, `target_work_id`). Whitespace/case normalization is deterministic.

Resolution order:
1. explicit `target_work_id` for continuation/change;
2. active WORK with identical request fingerprint;
3. terminal WORK with identical fingerprint, returned as a terminal match without resurrection;
4. otherwise create a new WORK.

Repeated requests from different chats merge provenance into the same WORK. No raw prompt is stored.

## Compaction / anti-junk
Persist only compact provenance: thread id, correlation id, timestamp and fingerprint. Keep at most the latest 20 request refs and source thread ids while retaining total request count and first/last request timestamps. Terminal WORK remains canonical but should not be reintroduced to active queues by ingress.

## Lifecycle
New admitted work starts `READY`. Existing active work keeps its current status when a duplicate request is merged. A terminal match is read-only by default. Chat deletion or source unavailability never invalidates WORK, TEST, RESULT or EVIDENCE.

## Events and readback
Each admitted request emits a material event: `REQUEST_INGESTED`, `REQUEST_MERGED`, or `REQUEST_TERMINAL_MATCH`. Creation/merge is successful only after canonical entity readback matches the expected fingerprint/version. Non-actionable input emits no canonical event and no WORK.

## Runtime integration
Implement as a focused `runtime/nexo_agent_api/ingress.py` protocol installed onto `AgentService`, mirroring the existing handoff extension pattern. Existing role queues consume the resulting WORK entities. Entity files remain canonical; active indexes are projections and must not hide newly-created canonical entities.

## Invariants
- `ONLY_ACTIONABLE_INTENT_BECOMES_WORK`
- `NO_RAW_CHAT_AS_CANONICAL_STATE`
- `MERGE_BEFORE_CREATE`
- `CHAT_LIFECYCLE != CANONICAL_STATE_LIFECYCLE`
- `SOURCE_DELETION_MUST_NOT_BREAK_WORK_CONTINUITY`
- `TERMINAL_WORK_NOT_RESURRECTED_BY_DUPLICATE_REQUEST`

## Acceptance tests
1. Same normalized task from two thread ids resolves to one WORK id and increments request count.
2. Different material task creates a different WORK.
3. Non-actionable request creates no WORK/event.
4. Explicit continuation resolves the target WORK without changing its state.
5. Duplicate request against terminal WORK does not make it active again.
6. Raw text is neither required nor persisted.
7. Provenance compacts after 20 refs while preserving total count.
8. A newly created canonical entity remains visible even when an active-work index already exists.
