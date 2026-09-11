from pathlib import Path

from peer_decisive_followups.checkpoint_manager import inspect_checkpoint, snapshot_checkpoint


def test_initializing_live_points_is_not_resumable(tmp_path: Path) -> None:
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "chain_phys_live.txt").write_text("partial live points", encoding="utf-8")

    status = inspect_checkpoint(raw)

    assert status["resumable"] is False
    assert status["phase"] == "initializing_live_points"


def test_resume_file_marks_checkpoint_resumable(tmp_path: Path) -> None:
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "chain.resume").write_text("resume-state", encoding="utf-8")
    (raw / "chain_phys_live.txt").write_text("live", encoding="utf-8")

    status = inspect_checkpoint(raw)

    assert status["resumable"] is True
    assert status["phase"] == "sampling"


def test_snapshot_copies_only_when_resume_exists(tmp_path: Path) -> None:
    raw = tmp_path / "raw"
    raw.mkdir()
    out = tmp_path / "snapshot"
    (raw / "chain.resume").write_text("resume-state", encoding="utf-8")
    (raw / "chain_phys_live.txt").write_text("live", encoding="utf-8")

    manifest = snapshot_checkpoint(raw, out)

    assert (out / "chain.resume").read_text(encoding="utf-8") == "resume-state"
    assert manifest["resumable"] is True
    assert manifest["resume_meta"][0]["sha256"]
