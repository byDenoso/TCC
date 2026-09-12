"""Read-only helpers for the NEXO v0.6 Tower template."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class TowerReadIssue(RuntimeError):
    """Typed read issue for Tower access."""

    def __init__(self, code: str, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}

    def payload(self) -> dict[str, Any]:
        return {"issue": {"code": self.code, "message": self.message, "details": self.details}}


class TowerReader:
    """Filesystem-backed reader over a Tower root."""

    def __init__(self, root: str | Path = "tower_template") -> None:
        self.root = Path(root)

    def health(self) -> dict[str, Any]:
        return {"status": "ok", "service": "nexo-view-api", "version": "0.1.0"}

    def snapshot(self) -> dict[str, Any]:
        return self.read_json("snapshots/latest.json")

    def graph_catalog(self) -> dict[str, Any]:
        return self.read_json("graphs/catalog.json")

    def graph(self, graph_id: str) -> dict[str, Any]:
        for graph in self.graph_catalog().get("graphs", []):
            if graph.get("graph_id") == graph_id:
                return graph
        raise TowerReadIssue("GRAPH_NOT_FOUND", "Graph id not found.", {"graph_id": graph_id})

    def graph_data(self, graph_id: str) -> dict[str, Any]:
        graph = self.graph(graph_id)
        data_ref = graph.get("data_ref", {})
        if data_ref.get("kind") != "github_tower":
            raise TowerReadIssue("GRAPH_REF_NOT_LOCAL", "Only github_tower refs are available in this scaffold.", {"graph_id": graph_id})
        path = data_ref.get("path")
        payload = self.read_json(path)
        if payload.get("graph_id") != graph_id:
            raise TowerReadIssue("GRAPH_ID_MISMATCH", "Graph payload id differs from catalog id.", {"graph_id": graph_id, "path": path})
        return payload

    def read_json(self, relative_path: str) -> dict[str, Any]:
        path = self.root / relative_path
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise TowerReadIssue("TOWER_FILE_NOT_FOUND", "Tower file not found.", {"path": relative_path}) from exc
        if not isinstance(payload, dict):
            raise TowerReadIssue("TOWER_JSON_NOT_OBJECT", "Tower JSON root must be an object.", {"path": relative_path})
        return payload
