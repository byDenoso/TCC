from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


def _load():
    spec = importlib.util.find_spec("peer_decisive_followups.bootstrap_state")
    assert spec is not None, "bootstrap_state module is required"
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _manifests():
    return ({"schema": "science", "model": "M1"}, {"schema": "runtime", "id": "r1"})


def _state(tmp_path: Path) -> tuple[Path, Path]:
    raw = tmp_path / "work" / "data" / "chain_polychord_raw"
    raw.mkdir(parents=True)
    state = raw / "chain.bootstrap"
    state.write_text("POLYCHORD_BOOTSTRAP_V1\n3 0 5 20\n", encoding="utf-8")
    prefix = tmp_path / "work" / "data" / "chain"
    Path(str(prefix) + ".input.yaml").write_text("output: old\n", encoding="utf-8")
    Path(str(prefix) + ".updated.yaml").write_text("output: old\n", encoding="utf-8")
    return state, prefix


def test_promote_verify_restore_roundtrip(tmp_path: Path):
    module = _load()
    science, runtime = _manifests()
    state, prefix = _state(tmp_path)
    bundle = tmp_path / "bundle"
    manifest = module.promote_bootstrap_bundle(
        state, bundle, model="M1", segment=2, parent_digest="parent",
        science_manifest=science, runtime_manifest=runtime, output_prefix=prefix,
        status={"classification": "BOOTSTRAP_REQUIRED"},
    )
    assert manifest["schema"] == "peer-bootstrap-checkpoint-v1"
    assert manifest["phase"] == "generating_live_points"
    assert manifest["resumable_native"] is False
    verified = module.verify_bootstrap_bundle(bundle, {
        "model": "M1", "parent_digest": "parent",
        "checkpoint_digest": manifest["checkpoint_digest"],
    })
    assert verified["checkpoint_digest"] == manifest["checkpoint_digest"]

    destination = tmp_path / "restore" / "chain_polychord_raw" / "chain.bootstrap"
    output_dir = tmp_path / "restore" / "data"
    module.restore_bootstrap_bundle(bundle, destination, {
        "model": "M1", "checkpoint_digest": manifest["checkpoint_digest"]
    }, output_dir=output_dir)
    assert destination.read_bytes() == state.read_bytes()
    assert (output_dir / "chain.input.yaml").is_file()
    assert (output_dir / "chain.updated.yaml").is_file()


def test_corruption_and_identity_mismatch_fail_closed(tmp_path: Path):
    module = _load()
    science, runtime = _manifests()
    state, prefix = _state(tmp_path)
    bundle = tmp_path / "bundle"
    manifest = module.promote_bootstrap_bundle(
        state, bundle, model="M1", segment=0, parent_digest=None,
        science_manifest=science, runtime_manifest=runtime, output_prefix=prefix,
    )
    with pytest.raises(module.BootstrapStateError, match="model mismatch"):
        module.verify_bootstrap_bundle(bundle, {"model": "M3"})
    payload = bundle / "raw" / "chain.bootstrap"
    payload.write_text("corrupt", encoding="utf-8")
    with pytest.raises(module.BootstrapStateError, match="hash"):
        module.verify_bootstrap_bundle(bundle, {"checkpoint_digest": manifest["checkpoint_digest"]})


def test_restore_is_atomic_on_invalid_bundle(tmp_path: Path):
    module = _load()
    science, runtime = _manifests()
    state, prefix = _state(tmp_path)
    bundle = tmp_path / "bundle"
    manifest = module.promote_bootstrap_bundle(
        state, bundle, model="M1", segment=1, parent_digest="p0",
        science_manifest=science, runtime_manifest=runtime, output_prefix=prefix,
    )
    destination = tmp_path / "dest" / "chain.bootstrap"
    destination.parent.mkdir(parents=True)
    destination.write_text("previous-good-state", encoding="utf-8")
    (bundle / "raw" / "chain.bootstrap").write_text("bad", encoding="utf-8")
    with pytest.raises(module.BootstrapStateError):
        module.restore_bootstrap_bundle(
            bundle, destination,
            {"model": "M1", "checkpoint_digest": manifest["checkpoint_digest"]},
        )
    assert destination.read_text(encoding="utf-8") == "previous-good-state"


def test_manifest_records_parent_science_runtime_and_status(tmp_path: Path):
    module = _load()
    science, runtime = _manifests()
    state, prefix = _state(tmp_path)
    bundle = tmp_path / "bundle"
    manifest = module.promote_bootstrap_bundle(
        state, bundle, model="M1", segment=4, parent_digest="abc",
        science_manifest=science, runtime_manifest=runtime, output_prefix=prefix,
        status={"classification": "BOOTSTRAP_REQUIRED", "accepted": 1000},
    )
    assert manifest["parent_checkpoint_digest"] == "abc"
    assert manifest["science_sha"]
    assert manifest["runtime_sha"]
    status = json.loads((bundle / "segment_status.json").read_text(encoding="utf-8"))
    assert status["accepted"] == 1000
