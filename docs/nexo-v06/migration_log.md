# NEXO v0.6 Migration Log

## 2026-09-12

Started Tower/API migration scaffold in `byDenoso/TCC`.

This public repo contains the implementation template only. Real Tower state should live in a protected Tower repository.

Initial scope:

- Tower template under `tower_template/`.
- Graph catalog and sample renderable graphs.
- Snapshot fixture.
- Read-only Tower reader under `runtime/nexo_view_api/`.
- Local validator under `scripts/validate_tower_template.py`.
- GitHub Actions validation workflow.

Sheets remains deprecated as an agent write path in the v0.6 direction.
