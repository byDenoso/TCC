# NEXO v0.6 Tower API Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build the first backend UX layer for NEXO v0.6: Tower template, graph registry, snapshot fixture, read-only Tower reader, tests, validator, and CI.

**Architecture:** Public repo holds reusable code and neutral templates only. Real Tower state belongs in a protected Tower repo. The frontend must consume graph and snapshot data through a View API/reader contract, not raw storage scanning.

**Tech Stack:** Python 3 standard library, JSON, GitHub Actions.

**Spec:** `docs/nexo-v06/backend_ux_contract.md`, `docs/nexo-v06/graph_registry_contract.md`

## Tasks

- [x] Create Tower template layout.
- [x] Add graph catalog fixture.
- [x] Add sample graph payloads.
- [x] Add snapshot fixture.
- [x] Add read-only Tower reader.
- [x] Add unit tests for the reader.
- [x] Add Tower template validator.
- [x] Add CI workflow.
- [ ] Move real Tower state into a protected repo.
- [ ] Wrap reader with deployed API routes.
- [ ] Connect NEXO ONE frontend to `/api/snapshot` and `/api/graphs`.
