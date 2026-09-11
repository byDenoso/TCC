from __future__ import annotations

import argparse
import hashlib
import json
import os
import signal
import subprocess
import time
from pathlib import Path

from peer_decisive_followups.checkpoint_manager import inspect_raw_checkpoint, promote_checkpoint
from peer_decisive_followups.production_config import build_production_configs
from peer_decisive_followups.runtime_contract import verify_runtime_manifest


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def bootstrap_checkpoint_ready(raw: Path, previous_signature):
    state = inspect_raw_checkpoint(Path(raw))
    valid = state.get("valid_resume_files", [])
    if not valid:
        return False, None
    signature = tuple(
        (name, (Path(raw) / name).stat().st_size, _sha256(Path(raw) / name))
        for name in sorted(valid)
    )
    return previous_signature == signature, signature


def _stop_group(proc: subprocess.Popen, grace_seconds: float) -> None:
    if proc.poll() is not None:
        return
    try:
        os.killpg(proc.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        proc.wait(timeout=grace_seconds)
        return
    except subprocess.TimeoutExpired:
        pass
    if proc.poll() is None:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        proc.wait(timeout=max(1.0, grace_seconds))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the unbounded first PEER PolyChord stage until a stable resume exists."
    )
    parser.add_argument("--model", choices=["M1", "M3"], required=True)
    parser.add_argument("--science", type=Path, required=True)
    parser.add_argument("--packages", required=True)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--runtime-manifest", type=Path, required=True)
    parser.add_argument("--output-bundle", type=Path, required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--poll-seconds", type=float, default=30.0)
    parser.add_argument("--grace-seconds", type=float, default=60.0)
    parser.add_argument("--skip-cobaya-preflight", action="store_true")
    args = parser.parse_args()

    runtime_manifest = json.loads(args.runtime_manifest.read_text(encoding="utf-8"))
    runtime_manifest = verify_runtime_manifest(runtime_manifest)
    work = args.work.resolve()
    root = work / f"nested_{args.model}"
    built = build_production_configs(
        args.science.resolve(), args.model, args.packages, root, args.seed,
        continuation=False,
    )
    science_manifest = built["science_manifest"]

    if not args.skip_cobaya_preflight:
        subprocess.run(
            ["cobaya-run", str((root / "data.yaml").resolve()), "--test"],
            cwd=work, check=True,
        )

    data_dir = root / "data"
    raw = data_dir / "chain_polychord_raw"
    data_dir.mkdir(parents=True, exist_ok=True)
    raw.mkdir(parents=True, exist_ok=True)
    stdout_path = data_dir / "stdout.bootstrap.log"
    stderr_path = data_dir / "stderr.bootstrap.log"
    previous_signature = None
    stopped_for_checkpoint = False

    with stdout_path.open("w", encoding="utf-8") as out, stderr_path.open("w", encoding="utf-8") as err:
        proc = subprocess.Popen(
            [
                "mpirun", "--oversubscribe", "-np", "4", "cobaya-run",
                str((root / "data.yaml").resolve()),
            ],
            cwd=work,
            stdout=out,
            stderr=err,
            text=True,
            start_new_session=True,
        )
        while proc.poll() is None:
            ready, signature = bootstrap_checkpoint_ready(raw, previous_signature)
            previous_signature = signature
            if ready:
                stopped_for_checkpoint = True
                _stop_group(proc, args.grace_seconds)
                break
            time.sleep(max(0.1, args.poll_seconds))
        exit_code = proc.wait()

    ready, _ = bootstrap_checkpoint_ready(raw, previous_signature)
    state = inspect_raw_checkpoint(raw)
    if not state["resumable"]:
        report = {
            "classification": "FAILED",
            "exit_code": exit_code,
            "stopped_for_checkpoint": stopped_for_checkpoint,
            "checkpoint_state": state,
        }
        (root / "bootstrap_status.json").write_text(
            json.dumps(report, indent=2, sort_keys=True), encoding="utf-8"
        )
        print(json.dumps(report, indent=2, sort_keys=True))
        return 2

    manifest = promote_checkpoint(
        raw,
        args.output_bundle.resolve(),
        model=args.model,
        segment=0,
        parent_digest=None,
        science_manifest=science_manifest,
        runtime_manifest=runtime_manifest,
    )
    report = {
        "classification": "RESUMABLE" if stopped_for_checkpoint else "COMPLETE",
        "exit_code": exit_code,
        "stopped_for_checkpoint": stopped_for_checkpoint,
        "checkpoint_digest": manifest["checkpoint_digest"],
        "checkpoint_state": state,
    }
    (root / "bootstrap_status.json").write_text(
        json.dumps(report, indent=2, sort_keys=True), encoding="utf-8"
    )
    (args.output_bundle.resolve() / "segment_status.json").write_text(
        json.dumps(report, indent=2, sort_keys=True), encoding="utf-8"
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
