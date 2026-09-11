import json
from pathlib import Path

import pytest

from peer_decisive_followups.checkpoint_manager import (
    CheckpointError,
    inspect_raw_checkpoint,
    promote_checkpoint,
    restore_bundle,
    verify_bundle,
)
from peer_decisive_followups.production_contract import sha256_json


def _manifests():
    science = {"schema": "science", "model": "M1", "tau": [0.0, 0.1]}
    runtime = {"schema": "runtime", "camb": "1.6.6", "cobaya": "3.6.2"}
    return science, runtime


def _raw(tmp_path: Path, *, resume: bytes = b"resume-state") -> Path:
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "chain.resume").write_bytes(resume)
    (raw / "chain_phys_live.txt").write_text("live", encoding="utf-8")
    (raw / "chain_dead.txt").write_text("dead", encoding="utf-8")
    return raw


def test_live_only_checkpoint_is_not_resumable(tmp_path: Path):
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "chain_phys_live.txt").write_text("partial", encoding="utf-8")
    state = inspect_raw_checkpoint(raw)
    assert state["phase"] == "initializing_live_points"
    assert state["resumable"] is False


def test_zero_size_resume_is_rejected(tmp_path: Path):
    raw = _raw(tmp_path, resume=b"")
    science, runtime = _manifests()
    with pytest.raises(CheckpointError, match="resume"):
        promote_checkpoint(raw, tmp_path / "bundle", model="M1", segment=1,
                           parent_digest=None, science_manifest=science,
                           runtime_manifest=runtime)


def test_promote_verify_and_restore_round_trip(tmp_path: Path):
    raw = _raw(tmp_path)
    science, runtime = _manifests()
    bundle = tmp_path / "bundle"
    manifest = promote_checkpoint(raw, bundle, model="M1", segment=2,
                                  parent_digest="parent123", science_manifest=science,
                                  runtime_manifest=runtime)
    expected = {"model": "M1", "science_sha": sha256_json(science),
                "runtime_sha": sha256_json(runtime), "parent_digest": "parent123"}
    verified = verify_bundle(bundle, expected)
    assert verified["checkpoint_digest"] == manifest["checkpoint_digest"]
    destination = tmp_path / "restored"
    restored = restore_bundle(bundle, destination, expected)
    assert (destination / "chain.resume").read_bytes() == b"resume-state"
    assert restored["checkpoint_digest"] == manifest["checkpoint_digest"]


def test_corrupt_file_is_rejected(tmp_path: Path):
    raw = _raw(tmp_path)
    science, runtime = _manifests()
    bundle = tmp_path / "bundle"
    promote_checkpoint(raw, bundle, model="M1", segment=1, parent_digest=None,
                       science_manifest=science, runtime_manifest=runtime)
    (bundle / "raw" / "chain.resume").write_text("tampered", encoding="utf-8")
    with pytest.raises(CheckpointError, match="hash"):
        verify_bundle(bundle, {"model": "M1", "science_sha": sha256_json(science),
                               "runtime_sha": sha256_json(runtime)})


def test_manifest_identity_mismatch_is_rejected(tmp_path: Path):
    raw = _raw(tmp_path)
    science, runtime = _manifests()
    bundle = tmp_path / "bundle"
    promote_checkpoint(raw, bundle, model="M1", segment=1, parent_digest=None,
                       science_manifest=science, runtime_manifest=runtime)
    with pytest.raises(CheckpointError, match="model"):
        verify_bundle(bundle, {"model": "M3", "science_sha": sha256_json(science),
                               "runtime_sha": sha256_json(runtime)})


def test_restore_leaves_existing_destination_untouched_on_failure(tmp_path: Path):
    raw = _raw(tmp_path)
    science, runtime = _manifests()
    bundle = tmp_path / "bundle"
    promote_checkpoint(raw, bundle, model="M1", segment=1, parent_digest=None,
                       science_manifest=science, runtime_manifest=runtime)
    destination = tmp_path / "dest"
    destination.mkdir()
    (destination / "sentinel").write_text("keep", encoding="utf-8")
    (bundle / "raw" / "chain.resume").write_text("tampered", encoding="utf-8")
    with pytest.raises(CheckpointError):
        restore_bundle(bundle, destination, {"model": "M1",
                                             "science_sha": sha256_json(science),
                                             "runtime_sha": sha256_json(runtime)})
    assert (destination / "sentinel").read_text(encoding="utf-8") == "keep"


def test_bundle_rejects_symlinks_and_unexpected_top_level_files(tmp_path: Path):
    raw = _raw(tmp_path)
    science, runtime = _manifests()
    bundle = tmp_path / "bundle"
    promote_checkpoint(raw, bundle, model="M1", segment=1, parent_digest=None,
                       science_manifest=science, runtime_manifest=runtime)
    (bundle / "surprise.txt").write_text("nope", encoding="utf-8")
    with pytest.raises(CheckpointError, match="unexpected"):
        verify_bundle(bundle, {"model": "M1", "science_sha": sha256_json(science),
                               "runtime_sha": sha256_json(runtime)})
