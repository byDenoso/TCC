# DENER SSOT Apps Script Adapter

Spreadsheet: `1e6s2dKOYVLNsPUguHI85RLVLwJKtlCsQZBJ1BE-UhaY`.

V1 is read-only and runs in SHADOW mode. Supported operations are `health`, `export_public` and `export_internal`.

Canonical logical tabs: `SYSTEM`, `PROJECTS`, `WORK`, `TESTS`, `EVENTS`, `KNOWLEDGE`, `RELATIONS`, `DECISIONS`, `OLYMPUS`.

The public export uses an allowlist summary for the client domain. The internal export is not a site feed.

Smoke checks:
- `health` returns `ok=true`.
- `export_public` returns schema `1.0`, `ssot_revision` and `state_hash`.
- Same state produces the same `state_hash`.
- Missing canonical tabs produces `SCHEMA_NOT_READY`.
