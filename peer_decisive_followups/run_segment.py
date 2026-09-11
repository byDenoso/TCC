from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import time
from pathlib import Path

from peer_decisive_followups.checkpoint_manager import inspect_raw_checkpoint, snapshot_checkpoint


def _stop_process_group(proc: subprocess.Popen, grace_seconds: float) -> None:
    if proc.poll() is not None:
        return
    try:
        os.killpg(proc.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    except (AttributeError, PermissionError):
        proc.terminate()
    try:
        proc.wait(timeout=max(0.0, grace_seconds))
        return
    except subprocess.TimeoutExpired:
        pass
    if proc.poll() is None:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            return
        except (AttributeError, PermissionError):
            proc.kill()
        proc.wait(timeout=max(1.0, grace_seconds))


def run_segment(command: list[str], *, cwd: Path, raw: Path,
                stdout_path: Path, stderr_path: Path, seconds: float,
                grace_seconds: float = 30.0) -> dict:
    cwd, raw = Path(cwd), Path(raw)
    stdout_path, stderr_path = Path(stdout_path), Path(stderr_path)
    stdout_path.parent.mkdir(parents=True, exist_ok=True)
    stderr_path.parent.mkdir(parents=True, exist_ok=True)
    raw.mkdir(parents=True, exist_ok=True)

    timed_out = False
    with stdout_path.open("w", encoding="utf-8") as out, stderr_path.open("w", encoding="utf-8") as err:
        proc = subprocess.Popen(
            command,
            cwd=cwd,
            stdout=out,
            stderr=err,
            text=True,
            start_new_session=True,
        )
        deadline = time.monotonic() + float(seconds)
        while proc.poll() is None:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                timed_out = True
                _stop_process_group(proc, grace_seconds)
                break
            time.sleep(min(0.05, remaining))
        if proc.poll() is None:
            _stop_process_group(proc, grace_seconds)
        exit_code = proc.wait()

    checkpoint_state = inspect_raw_checkpoint(raw)
    resumable = bool(checkpoint_state["resumable"])
    complete = exit_code == 0 and any(
        p.is_file() and p.stat().st_size > 0 for p in raw.glob("*.stats")
    )

    if timed_out:
        classification = "RESUMABLE" if resumable else "FAILED"
    elif exit_code != 0:
        classification = "FAILED"
    elif complete:
        classification = "COMPLETE"
    elif resumable:
        classification = "RESUMABLE"
    else:
        classification = "FAILED"

    return {
        "exit_code": exit_code,
        "timed_out": timed_out,
        "seconds": float(seconds),
        "complete": complete,
        "resumable": resumable,
        "classification": classification,
        "checkpoint_state": checkpoint_state,
    }


def run_with_checkpoints(command: list[str], *, cwd: Path, raw: Path, snapshot: Path,
                         stdout_path: Path, stderr_path: Path, seconds: int,
                         interval: int = 300) -> dict:
    """Compatibility wrapper. Canonical snapshots are created only after process exit."""
    del interval
    result = run_segment(
        command,
        cwd=cwd,
        raw=raw,
        stdout_path=stdout_path,
        stderr_path=stderr_path,
        seconds=seconds,
    )
    result["checkpoint"] = snapshot_checkpoint(raw, snapshot) if result["resumable"] else result["checkpoint_state"]
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--cwd", type=Path, required=True)
    parser.add_argument("--raw", type=Path, required=True)
    parser.add_argument("--snapshot", type=Path)
    parser.add_argument("--stdout", type=Path, required=True)
    parser.add_argument("--stderr", type=Path, required=True)
    parser.add_argument("--seconds", type=float, default=19200)
    parser.add_argument("--grace-seconds", type=float, default=30.0)
    parser.add_argument("--status", type=Path, required=True)
    args = parser.parse_args()

    result = run_segment(
        ["mpirun", "--oversubscribe", "-np", "4", "cobaya-run", str(args.config.resolve())],
        cwd=args.cwd.resolve(),
        raw=args.raw.resolve(),
        stdout_path=args.stdout.resolve(),
        stderr_path=args.stderr.resolve(),
        seconds=args.seconds,
        grace_seconds=args.grace_seconds,
    )
    if args.snapshot and result["resumable"]:
        result["checkpoint"] = snapshot_checkpoint(args.raw.resolve(), args.snapshot.resolve())
    args.status.parent.mkdir(parents=True, exist_ok=True)
    args.status.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0 if result["classification"] in {"COMPLETE", "RESUMABLE"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
