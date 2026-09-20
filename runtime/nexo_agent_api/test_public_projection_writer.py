from __future__ import annotations

import json
from copy import deepcopy

from runtime.nexo_agent_api.public_projection import (
    build_public_projection,
    verify_projection,
)
from scripts.build_public_projection import write_projection_if_changed
from runtime.nexo_agent_api.test_public_projection import _tower


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

    work_path = root / "entities" / "work" / "WORK-A.json"
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
