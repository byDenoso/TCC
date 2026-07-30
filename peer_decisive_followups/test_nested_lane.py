from __future__ import annotations

from pathlib import Path

from peer_decisive_followups.run_nested_lane import _replace_directory_link, normalized_evidence


def test_normalized_evidence_uses_external_prior_correction() -> None:
    data = {"status": "COMPLETE", "evidence": {"logZ": -1020.0, "logZstd": 0.30}}
    prior = {"status": "COMPLETE", "evidence": {"logZ": -5.0, "logZstd": 0.20}}

    result = normalized_evidence(data, prior)

    assert result == {"logZ": -1015.0, "logZstd": 0.50}


def test_incomplete_component_never_yields_evidence() -> None:
    data = {"status": "INCOMPLETE", "evidence": None}
    prior = {"status": "COMPLETE", "evidence": {"logZ": 0.0, "logZstd": 0.1}}

    assert normalized_evidence(data, prior) is None


def test_runtime_link_replaces_stale_directory(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    destination = tmp_path / "runtime"
    destination.mkdir()
    (destination / "stale.txt").write_text("stale", encoding="utf-8")

    _replace_directory_link(destination, source)

    assert destination.is_symlink()
    assert destination.resolve() == source.resolve()
