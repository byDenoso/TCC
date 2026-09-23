from __future__ import annotations

import gzip
import json
from pathlib import Path

from .live_tower import (
    LIVE_TOWER_FILE_ID,
    LIVE_TOWER_NAME,
    build_live_tower_payload,
    publish_live_tower,
)


def _root(tmp_path: Path) -> Path:
    root = tmp_path / "TOWER_V06"
    (root / "entities" / "work").mkdir(parents=True)
    (root / "indexes").mkdir(parents=True)
    (root / "projections" / "public").mkdir(parents=True)
    (root / "CONTROL.json").write_text(json.dumps({"mode": "ACTIVE"}), encoding="utf-8")
    (root / "entities" / "work" / "W1.json").write_text(
        json.dumps({"id": "W1", "status": "READY", "entity_version": 1}),
        encoding="utf-8",
    )
    (root / "projections" / "public" / "latest.json").write_text(
        json.dumps({"derived": True}),
        encoding="utf-8",
    )
    return root


def test_live_tower_has_stable_identity_and_state_revision(tmp_path):
    root = _root(tmp_path)
    payload = build_live_tower_payload(root, updated_at="2026-09-23T12:00:00Z")

    assert payload["contract"] == "NEXO_TOWER_LIVE_V1"
    assert payload["stable_file_id"] == LIVE_TOWER_FILE_ID
    assert payload["revision"] == payload["state_fingerprint"]
    assert "CONTROL.json" in payload["files"]
    assert "entities/work/W1.json" in payload["files"]
    assert "projections/public/latest.json" not in payload["files"]


def test_timestamp_does_not_change_state_revision(tmp_path):
    root = _root(tmp_path)
    first = build_live_tower_payload(root, updated_at="2026-09-23T12:00:00Z")
    later = build_live_tower_payload(root, updated_at="2026-09-23T13:00:00Z")
    assert first["revision"] == later["revision"]


def test_material_change_changes_revision(tmp_path):
    root = _root(tmp_path)
    before = build_live_tower_payload(root)["revision"]
    path = root / "entities" / "work" / "W1.json"
    work = json.loads(path.read_text(encoding="utf-8"))
    work["status"] = "RUNNING"
    path.write_text(json.dumps(work), encoding="utf-8")
    after = build_live_tower_payload(root)["revision"]
    assert before != after


def test_publish_replaces_same_local_file_and_readbacks(tmp_path):
    root = _root(tmp_path)
    first = publish_live_tower(root, updated_at="2026-09-23T12:00:00Z")
    path = root / LIVE_TOWER_NAME
    assert path.exists()

    decoded = json.loads(gzip.decompress(path.read_bytes()).decode("utf-8"))
    assert decoded["stable_file_id"] == LIVE_TOWER_FILE_ID
    assert decoded["revision"] == first["revision"]

    work_path = root / "entities" / "work" / "W1.json"
    work = json.loads(work_path.read_text(encoding="utf-8"))
    work["status"] = "DONE"
    work_path.write_text(json.dumps(work), encoding="utf-8")

    second = publish_live_tower(root, updated_at="2026-09-23T12:05:00Z")
    assert second["revision"] != first["revision"]
    assert second["path"] == first["path"]
