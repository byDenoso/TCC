#!/usr/bin/env python3
"""Validate the public NEXO Tower template."""

from __future__ import annotations

import json
import sys
from pathlib import Path


REQUIRED = [
    "graphs/catalog.json",
    "snapshots/latest.json",
    "state/current/ops_config.json",
    "state/current/work.json",
    "state/current/blockers.json",
    "state/current/decisions.json",
    "state/current/agents.json",
    "state/current/artifacts.json",
    "manifests/drive_datasets.json",
    "manifests/drive_artifacts.json",
]


def load(root: Path, rel: str) -> dict:
    path = root / rel
    if not path.exists():
        raise ValueError(f"missing: {rel}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"not object: {rel}")
    return payload


def validate(root: Path) -> None:
    for rel in REQUIRED:
        load(root, rel)
    catalog = load(root, "graphs/catalog.json")
    graph_ids = []
    for graph in catalog.get("graphs", []):
        graph_id = graph.get("graph_id")
        if not graph_id:
            raise ValueError("graph without graph_id")
        if graph_id in graph_ids:
            raise ValueError(f"duplicate graph_id: {graph_id}")
        graph_ids.append(graph_id)
        data_ref = graph.get("data_ref", {})
        if data_ref.get("kind") == "github_tower":
            graph_payload = load(root, data_ref.get("path"))
            if graph_payload.get("graph_id") != graph_id:
                raise ValueError(f"graph payload mismatch: {graph_id}")
    snapshot = load(root, "snapshots/latest.json")
    for graph_id in snapshot.get("graphs", []):
        if graph_id not in graph_ids:
            raise ValueError(f"snapshot unknown graph: {graph_id}")


def main() -> int:
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("tower_template")
    try:
        validate(root)
    except Exception as exc:
        print(f"INVALID: {exc}", file=sys.stderr)
        return 1
    print(f"VALID: {root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
