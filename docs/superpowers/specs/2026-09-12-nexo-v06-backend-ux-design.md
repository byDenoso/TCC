# NEXO v0.6 Backend UX Design

## Goal
Reduce agent ceremony and legacy dependencies without adding a new service or database.

## Design
- GitHub `TOWER_V06` remains the canonical state owner.
- A compact `indexes/active-work.json` is the hot discovery surface; per-entity JSON is created automatically on first mutation and then overrides the index.
- `bootstrap/<role>.json` and `queues/<role>.json` are derived views, never truth owners.
- Backend mutation owns version checking, atomic write, material event receipt, and exact readback.
- Executor eligibility is mechanical; raw `READY` is insufficient.
- Artifact/capability refs are resolved through manifests so roles do not depend on storage/provider details.
- Legacy Sheets/Tower are migration archive/fallback only and are not part of normal boot.

## Non-goals
No new DB, no Neon, no microservices, no frontend redesign, no automatic scientific-claim changes.
