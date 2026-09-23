from __future__ import annotations

import gzip
import json
import subprocess

import pytest

from runtime.nexo_agent_api.public_projection import (
    build_public_projection,
    verify_projection,
)
from scripts.build_public_projection import (
    materialize_live_tower_root,
    verify_root_provenance,
    write_projection_if_changed,
)
from runtime.nexo_agent_api.live_tower import build_live_tower_payload
from runtime.nexo_agent_api.test_public_projection import _tower
from runtime.nexo_agent_api.tower_paths import entity_path


def _build(root, *, commit="a" * 40, generated_at="2026-09-20T00:00:00Z"):
    projection = build_public_projection(
        root,
        tower_commit=commit,
        generated_at=generated_at,
    )
    ok, detail = verify_projection(projection)
    assert ok, detail
    return projection


def test_identical_content_is_true_noop_and_preserves_old_provenance(tmp_path):
    root = _tower(tmp_path)
    out = tmp_path / "public"

    first = _build(root, commit="a" * 40, generated_at="2026-09-20T00:00:00Z")
    assert write_projection_if_changed(out, first) is True
    before_projection = (out / "projection.json").read_bytes()
    before_manifest = (out / "manifest.json").read_bytes()

    same_content_new_metadata = _build(
        root,
        commit="b" * 40,
        generated_at="2026-09-20T01:00:00Z",
    )
    assert (
        first["manifest"]["projection_fingerprint"]
        == same_content_new_metadata["manifest"]["projection_fingerprint"]
    )
    assert write_projection_if_changed(out, same_content_new_metadata) is False

    assert (out / "projection.json").read_bytes() == before_projection
    assert (out / "manifest.json").read_bytes() == before_manifest
    persisted = json.loads((out / "projection.json").read_text(encoding="utf-8"))
    assert persisted["manifest"]["tower_commit"] == "a" * 40


def test_changed_canonical_content_replaces_projection_and_manifest_together(tmp_path):
    root = _tower(tmp_path)
    out = tmp_path / "public"

    first = _build(root)
    assert write_projection_if_changed(out, first) is True

    work_path = entity_path(root, "work", "WORK-A")
    work = json.loads(work_path.read_text(encoding="utf-8"))
    work["status"] = "RUNNING"
    work_path.write_text(json.dumps(work), encoding="utf-8")

    second = _build(root, commit="c" * 40, generated_at="2026-09-20T02:00:00Z")
    assert second["manifest"]["projection_fingerprint"] != first["manifest"]["projection_fingerprint"]
    assert write_projection_if_changed(out, second) is True

    persisted = json.loads((out / "projection.json").read_text(encoding="utf-8"))
    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    assert persisted["manifest"] == manifest
    assert manifest["tower_commit"] == "c" * 40
    ok, detail = verify_projection(persisted)
    assert ok, detail


def test_root_provenance_requires_exact_clean_git_checkout(tmp_path):
    repo = tmp_path / "repo"
    root = repo / "TOWER_V06"
    root.mkdir(parents=True)
    (root / "CONTROL.json").write_text("{}\n", encoding="utf-8")

    subprocess.run(["git", "init", str(repo)], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "test@example.invalid"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "Projection Test"], check=True)
    subprocess.run(["git", "-C", str(repo), "add", "TOWER_V06/CONTROL.json"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-m", "fixture"], check=True, capture_output=True)
    head = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()

    assert verify_root_provenance(root, head) == head

    with pytest.raises(ValueError, match="differs from declared"):
        verify_root_provenance(root, "a" * 40)

    (root / "CONTROL.json").write_text('{"changed":true}\n', encoding="utf-8")
    with pytest.raises(ValueError, match="not clean"):
        verify_root_provenance(root, head)


def test_root_provenance_rejects_non_git_materialization(tmp_path):
    root = _tower(tmp_path)
    with pytest.raises(ValueError, match="not inside a readable Git checkout"):
        verify_root_provenance(root, "a" * 40)


def test_live_tower_materializes_without_current_or_generation(tmp_path):
    root = _tower(tmp_path / "source")
    control_path = root / "CONTROL.json"
    control = json.loads(control_path.read_text(encoding="utf-8"))
    control["truth_owner"] = "TOWER_V06@GOOGLE_DRIVE_PRIVATE"
    control["write_model"] = "IN_PLACE_FILE_REVISION_CAS_READBACK"
    control_path.write_text(json.dumps(control), encoding="utf-8")

    live = build_live_tower_payload(root, updated_at="2026-09-23T12:00:00Z")
    bundle = tmp_path / "NEXO_TOWER_LIVE.json.gz"
    with gzip.open(bundle, "wt", encoding="utf-8") as handle:
        json.dump(live, handle, ensure_ascii=False, sort_keys=True)

    materialized, metadata = materialize_live_tower_root(
        bundle,
        tmp_path / "materialized" / "TOWER_V06",
    )

    assert metadata["tower_revision"] == live["revision"]
    assert metadata["tower_file_id"] == live["stable_file_id"]
    assert not (materialized / "CURRENT.json").exists()

    projection = build_public_projection(
        materialized,
        tower_revision=str(metadata["tower_revision"]),
        tower_file_id=str(metadata["tower_file_id"]),
        generated_at="2026-09-23T12:01:00Z",
    )
    ok, detail = verify_projection(projection)
    assert ok, detail
    assert projection["manifest"]["tower_file_id"] == live["stable_file_id"]
    assert projection["manifest"]["tower_revision"] == live["revision"]
