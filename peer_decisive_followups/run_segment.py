from __future__ import annotations

import argparse
import json
import subprocess
import threading
from pathlib import Path

from peer_decisive_followups.checkpoint_manager import snapshot_checkpoint


def run_with_checkpoints(command: list[str], *, cwd: Path, raw: Path, snapshot: Path,
                         stdout_path: Path, stderr_path: Path, seconds: int,
                         interval: int = 300) -> dict:
    stop = threading.Event()

    def watcher() -> None:
        while not stop.wait(interval):
            snapshot_checkpoint(raw, snapshot)

    thread = threading.Thread(target=watcher, daemon=True)
    thread.start()
    code = 0
    timed_out = False
    stdout_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with stdout_path.open("w", encoding="utf-8") as out, stderr_path.open("w", encoding="utf-8") as err:
            try:
                proc = subprocess.run(command, cwd=cwd, timeout=seconds, stdout=out, stderr=err, text=True)
                code = proc.returncode
            except subprocess.TimeoutExpired:
                code = 124
                timed_out = True
    finally:
        stop.set()
        thread.join(timeout=5)
        manifest = snapshot_checkpoint(raw, snapshot)

    result = {
        "exit_code": code,
        "timed_out": timed_out,
        "seconds": seconds,
        "checkpoint": manifest,
    }
    return result


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--config", type=Path, required=True)
    p.add_argument("--cwd", type=Path, required=True)
    p.add_argument("--raw", type=Path, required=True)
    p.add_argument("--snapshot", type=Path, required=True)
    p.add_argument("--stdout", type=Path, required=True)
    p.add_argument("--stderr", type=Path, required=True)
    p.add_argument("--seconds", type=int, default=19800)
    p.add_argument("--status", type=Path, required=True)
    args = p.parse_args()

    result = run_with_checkpoints(
        ["mpirun", "--oversubscribe", "-np", "4", "cobaya-run", str(args.config.resolve())],
        cwd=args.cwd.resolve(), raw=args.raw.resolve(), snapshot=args.snapshot.resolve(),
        stdout_path=args.stdout.resolve(), stderr_path=args.stderr.resolve(), seconds=args.seconds,
    )
    args.status.parent.mkdir(parents=True, exist_ok=True)
    args.status.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0 if result["exit_code"] in (0, 124) else result["exit_code"]


if __name__ == "__main__":
    raise SystemExit(main())
