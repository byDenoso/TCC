# DENER SSOT Apps Script Adapter

The concrete SSOT spreadsheet identifier and physical sheet mapping are private configuration and MUST NOT be committed to this public repository.

V1 runs read-only in SHADOW mode. Supported operations are `health`, `export_public` and `export_internal`.

The public export exposes the canonical logical model and an allowlist summary for the private client domain. The internal export is operational-only and is never a public site feed.

Configuration:
- Apps Script property `DENER_SSOT_ID`: private spreadsheet identifier.
- Private adapter mapping: logical SSOT sections to physical sheet IDs/names.
- GitHub secret `SSOT_EXPORT_URL`: deployed read endpoint used by the Pages materializer.

Smoke gates:
- `health` returns `ok=true`.
- `export_public` returns schema `1.0`, `ssot_revision` and `state_hash`.
- Same state produces the same `state_hash`.
- Missing private mapping returns `SCHEMA_NOT_READY`.
- Public projection includes only allowlisted fields.
