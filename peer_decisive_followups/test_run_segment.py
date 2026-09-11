import sys
from pathlib import Path

from peer_decisive_followups.run_segment import run_segment


def _paths(tmp_path: Path):
    raw = tmp_path / "raw"
    raw.mkdir()
    return raw, tmp_path / "stdout.log", tmp_path / "stderr.log"


def test_timeout_with_resume_is_resumable(tmp_path: Path):
    raw, stdout, stderr = _paths(tmp_path)
    script = (
        "from pathlib import Path; import time; "
        f"Path({str(raw / 'chain.resume')!r}).write_text('state'); "
        "time.sleep(30)"
    )
    result = run_segment([sys.executable, "-c", script], cwd=tmp_path, raw=raw,
                         stdout_path=stdout, stderr_path=stderr,
                         seconds=0.2, grace_seconds=0.5)
    assert result["timed_out"] is True
    assert result["classification"] == "RESUMABLE"
    assert result["resumable"] is True


def test_timeout_without_resume_fails_closed(tmp_path: Path):
    raw, stdout, stderr = _paths(tmp_path)
    result = run_segment([sys.executable, "-c", "import time; time.sleep(30)"],
                         cwd=tmp_path, raw=raw, stdout_path=stdout, stderr_path=stderr,
                         seconds=0.2, grace_seconds=0.5)
    assert result["timed_out"] is True
    assert result["classification"] == "FAILED"
    assert result["resumable"] is False


def test_natural_completion_with_stats_is_complete(tmp_path: Path):
    raw, stdout, stderr = _paths(tmp_path)
    script = (
        "from pathlib import Path; "
        f"Path({str(raw / 'chain.stats')!r}).write_text('logZ = 1.0'); "
        f"Path({str(raw / 'chain.resume')!r}).write_text('state')"
    )
    result = run_segment([sys.executable, "-c", script], cwd=tmp_path, raw=raw,
                         stdout_path=stdout, stderr_path=stderr,
                         seconds=2, grace_seconds=0.5)
    assert result["timed_out"] is False
    assert result["classification"] == "COMPLETE"


def test_unexpected_nonzero_exit_is_failed_even_with_resume(tmp_path: Path):
    raw, stdout, stderr = _paths(tmp_path)
    script = (
        "from pathlib import Path; "
        f"Path({str(raw / 'chain.resume')!r}).write_text('state'); "
        "raise SystemExit(7)"
    )
    result = run_segment([sys.executable, "-c", script], cwd=tmp_path, raw=raw,
                         stdout_path=stdout, stderr_path=stderr,
                         seconds=2, grace_seconds=0.5)
    assert result["exit_code"] == 7
    assert result["classification"] == "FAILED"
