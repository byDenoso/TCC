from pathlib import Path

import pytest

from peer_decisive_followups.bootstrap_production import bootstrap_checkpoint_ready
from peer_decisive_followups.runtime_contract import (
    RuntimeContractError,
    build_runtime_manifest,
    verify_runtime_manifest,
)


def test_runtime_manifest_is_deterministic():
    a = build_runtime_manifest(payload_hashes={"b": "2", "a": "1"})
    b = build_runtime_manifest(payload_hashes={"a": "1", "b": "2"})
    assert a["identity_sha256"] == b["identity_sha256"]
    assert a["camb"] == "1.6.6"
    assert a["cobaya"] == "3.6.2"
    assert a["polychord"] == "1.20.1"


def test_runtime_manifest_rejects_act_commit_mismatch():
    manifest = build_runtime_manifest()
    manifest["act_commit"] = "bad"
    with pytest.raises(RuntimeContractError, match="ACT"):
        verify_runtime_manifest(manifest)


def test_runtime_manifest_rejects_camb_mismatch():
    manifest = build_runtime_manifest()
    manifest["camb"] = "1.6.5"
    with pytest.raises(RuntimeContractError, match="CAMB"):
        verify_runtime_manifest(manifest)


def test_bootstrap_checkpoint_not_ready_without_nonempty_resume(tmp_path: Path):
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "chain_phys_live.txt").write_text("partial", encoding="utf-8")
    assert bootstrap_checkpoint_ready(raw, previous_signature=None) == (False, None)


def test_bootstrap_checkpoint_requires_stable_resume_signature(tmp_path: Path):
    raw = tmp_path / "raw"
    raw.mkdir()
    resume = raw / "chain.resume"
    resume.write_bytes(b"state")
    ready, signature = bootstrap_checkpoint_ready(raw, previous_signature=None)
    assert ready is False and signature is not None
    ready2, signature2 = bootstrap_checkpoint_ready(raw, previous_signature=signature)
    assert ready2 is True and signature2 == signature
