# NEXO v0.6 Backend UX Contract

## Goal

Make backend state readable by agents and frontend consumers before improving the visual layer.

## Rules

1. Agents should not write directly to Sheets.
2. Sheets may remain as a projection or legacy view.
3. Tower stores canonical declarative state, graph catalog, blockers, decisions, manifests, and snapshots.
4. Drive stores datasets and heavy artifacts.
5. The frontend consumes a View API, not raw storage.
6. `READY` is not equal to `executor_eligible`.
7. Provider pulse and material execution are separate states.
8. Every blocker uses a typed `blocking_code`.
9. Every graph uses a stable `graph_id`.
10. Future write actions must go through typed backend actions, not browser-side storage edits.

## MVP endpoints

- `GET /api/health`
- `GET /api/snapshot`
- `GET /api/graphs`
- `GET /api/graphs/:graph_id/data`
- `GET /api/blockers`
- `GET /api/work`
- `GET /api/agents`

This commit implements the read model as Python helpers first. HTTP deployment can wrap the same reader without changing the frontend contract.
