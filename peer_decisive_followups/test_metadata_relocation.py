from pathlib import Path

import yaml

from peer_decisive_followups.checkpoint_manager import relocate_cobaya_metadata


def test_relocation_updates_only_runtime_locations(tmp_path: Path):
    data = tmp_path / "data"
    data.mkdir()
    prefix = data / "chain"
    old = {
        "packages_path": "/old/packages",
        "output": "/old/work/data/chain",
        "params": {"tau": {"prior": {"min": 0.0, "max": 0.1}}},
        "theory": {"peer": {"python_path": "/old/science", "path": "global", "extra_args": {"mnu": 0.06}}},
        "likelihood": {"shoes": {"python_path": "/old/science", "mean": 73.04, "sigma": 1.04}},
        "sampler": {"polychord": {"blocking": [[1, ["tau"]]], "nlive": 400}},
    }
    for suffix in (".input.yaml", ".updated.yaml"):
        Path(str(prefix) + suffix).write_text(yaml.safe_dump(old, sort_keys=False), encoding="utf-8")
    current = {
        "packages_path": "/new/packages",
        "output": str(prefix),
        "params": {"tau": {"prior": {"min": 0.0, "max": 0.1}}},
        "theory": {"peer": {"python_path": "/new/science", "path": "global", "extra_args": {"mnu": 0.06}}},
        "likelihood": {"shoes": {"python_path": "/new/science", "mean": 73.04, "sigma": 1.04}},
        "sampler": {"polychord": {"nlive": 400}},
    }
    report = relocate_cobaya_metadata(prefix, current)
    assert report["files"] == ["chain.input.yaml", "chain.updated.yaml"]
    restored = yaml.safe_load(Path(str(prefix) + ".updated.yaml").read_text(encoding="utf-8"))
    assert restored["packages_path"] == "/new/packages"
    assert restored["output"] == str(prefix)
    assert restored["theory"]["peer"]["python_path"] == "/new/science"
    assert restored["likelihood"]["shoes"]["python_path"] == "/new/science"
    assert restored["params"]["tau"]["prior"] == {"min": 0.0, "max": 0.1}
    assert restored["sampler"]["polychord"]["blocking"] == [[1, ["tau"]]]


def test_relocation_does_not_copy_scientific_values_from_current(tmp_path: Path):
    prefix = tmp_path / "chain"
    old = {
        "packages_path": "/old/packages",
        "output": "/old/chain",
        "params": {"tau": {"prior": {"min": 0.0, "max": 0.1}}},
        "likelihood": {"shoes": {"python_path": "/old/science", "mean": 73.04}},
    }
    current = {
        "packages_path": "/new/packages",
        "output": str(prefix),
        "params": {"tau": {"prior": {"min": 0.01, "max": 0.1}}},
        "likelihood": {"shoes": {"python_path": "/new/science", "mean": 999.0}},
    }
    for suffix in (".input.yaml", ".updated.yaml"):
        Path(str(prefix) + suffix).write_text(yaml.safe_dump(old, sort_keys=False), encoding="utf-8")
    relocate_cobaya_metadata(prefix, current)
    restored = yaml.safe_load(Path(str(prefix) + ".updated.yaml").read_text(encoding="utf-8"))
    assert restored["params"]["tau"]["prior"]["min"] == 0.0
    assert restored["likelihood"]["shoes"]["mean"] == 73.04


def test_continuation_orchestrator_relocates_metadata_after_restore_before_sampling():
    source = Path(__file__).with_name("orchestrate_segment.py").read_text(encoding="utf-8")
    assert "relocate_cobaya_metadata" in source
    restore_at = source.index("parent = restore_bundle(")
    relocate_at = source.index("relocate_cobaya_metadata(")
    run_at = source.index("result = run_segment(")
    assert restore_at < relocate_at < run_at
    assert 'built["data"]' in source[relocate_at:run_at]
