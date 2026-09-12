# NEXO v0.6 Graph Registry Contract

## Purpose

The graph registry lets NEXO ONE discover renderable graphs without scanning Drive, Sheets, Vercel, or raw folders.

The frontend asks the View API for graph metadata and graph data. It must use stable `graph_id` values instead of raw paths.

## Stable IDs

Use:

```text
GRAPH::<DOMAIN>::<NAME>
```

Examples in this scaffold:

- `GRAPH::OPS::AUTOMATION_PIPELINE`
- `GRAPH::OPS::BLOCKERS`
- `GRAPH::COSMOLOGY::SOURCE_BINDING_FUNNEL`

## Required catalog fields

- `graph_id`
- `title`
- `domain`
- `type`
- `status`
- `renderer`
- `data_ref`
- `data_url`
- `version`
- `updated_at`
- `visibility`

## MVP rule

Small JSON graph data can use `data_ref.kind = github_tower`.

Heavy graph data should remain in Drive and be represented by a manifest entry. The frontend still calls the View API. It never receives storage credentials or raw discovery duties.
