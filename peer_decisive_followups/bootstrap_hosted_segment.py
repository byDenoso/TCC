from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import time
from pathlib import Path
from typing import Any

from peer_decisive_followups.bootstrap_state import (
    inspect_bootstrap_state,
    promote_bootstrap_bundle,
    restore_bootstrap_bundle,
)
from peer_decisive_followups.checkpoint_manager import inspect_raw_checkpoint, promote_checkpoint
from peer_decisive_followups.metadata_relocation import relocate_cobaya_metadata
from peer_decisive_followups.production_config import build_production_configs
from peer_decisive_followups.production_contract import sha256_json
from peer_decisive_followups.runtime_contract import verify_runtime_manifest


def classify_segment(*, exit_code: int, bootstrap_valid: bool, native_resumable: bool) -> str:
    if native_resumable:
        return "RESUMABLE"
    if exit_code == 86 and bootstrap_valid:
        return "BOOTSTRAP_REQUIRED"
    return "FAILED"


def segment_environment(segment_valid: int, *, base: dict[str, str] | None = None) -> dict[str, str]:
    if int(segment_valid) <= 0:
        raise ValueError("segment_valid must be positive")
    env = dict(os.environ if base is None else base)
    env["POLYCHORD_BOOTSTRAP_SEGMENT_VALID"] = str(int(segment_valid))
    return env


def _resume_signature(raw: Path) -> tuple[tuple[str, int, int], ...] | None:
    state = inspect_raw_checkpoint(raw)
    names = state.get("valid_resume_files", [])
    if not names:
        return None
    return tuple(
        (name, (raw / name).stat().st_size, (raw / name).stat().st_mtime_ns)
        for name in sorted(names)
    )


def _stop_group(proc: subprocess.Popen[Any], grace_seconds: float) -> None:
    if proc.poll() is not None:
        return
    try:
        os.killpg(proc.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        proc.wait(timeout=max(1.0, grace_seconds))
        return
    except subprocess.TimeoutExpired:
        pass
    if proc.poll() is None:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        proc.wait(timeout=max(1.0, grace_seconds))


def run_hosted_segment(*, model: str, science: Path, packages: str, work: Path,
                       runtime_manifest_path: Path, output_bundle: Path, seed: int,
                       segment: int, segment_valid: int, parent_bundle: Path | None = None,
                       parent_digest: str | None = None, poll_seconds: float = 20.0,
                       grace_seconds: float = 60.0, skip_cobaya_preflight: bool = False) -> dict[str, Any]:
    runtime_manifest = verify_runtime_manifest(
        json.loads(Path(runtime_manifest_path).read_text(encoding="utf-8"))
    )
    work = Path(work).resolve()
    root = work / f"nested_{model}"
    built = build_production_configs(
        Path(science).resolve(), model, packages, root, int(seed),
        continuation=parent_bundle is not None,
    )
    science_manifest = built["science_manifest"]
    data_dir = root / "data"
    raw = data_dir / "chain_polychord_raw"
    state_file = raw / "chain.bootstrap"
    output_prefix = data_dir / "chain"
    raw.mkdir(parents=True, exist_ok=True)

    resolved_parent_digest = parent_digest
    if parent_bundle is not None:
        expected = {
            "model": model,
            "science_sha": sha256_json(science_manifest),
            "runtime_sha": sha256_json(runtime_manifest),
        }
        if parent_digest is not None:
            expected["checkpoint_digest"] = parent_digest
        parent_manifest = restore_bootstrap_bundle(
            Path(parent_bundle), state_file, expected, output_dir=data_dir,
        )
        resolved_parent_digest = parent_manifest["checkpoint_digest"]
        relocate_cobaya_metadata(output_prefix, built["data"])

    if not skip_cobaya_preflight:
        subprocess.run(
            ["cobaya-run", str((root / "data.yaml").resolve()), "--test"],
            cwd=work, check=True,
        )

    stdout_path = data_dir / "stdout.hosted-bootstrap.log"
    stderr_path = data_dir / "stderr.hosted-bootstrap.log"
    previous_resume = None
    stopped_for_native = False
    env = segment_environment(segment_valid)
    with stdout_path.open("w", encoding="utf-8") as out, stderr_path.open("w", encoding="utf-8") as err:
        proc = subprocess.Popen(
            ["mpirun", "--oversubscribe", "-np", "4", "cobaya-run", str((root / "data.yaml").resolve())],
            cwd=work, stdout=out, stderr=err, text=True, env=env, start_new_session=True,
        )
        while proc.poll() is None:
            signature = _resume_signature(raw)
            if signature is not None and signature == previous_resume:
                stopped_for_native = True
                _stop_group(proc, grace_seconds)
                break
            previous_resume = signature
            time.sleep(max(0.1, poll_seconds))
        exit_code = proc.wait()

    native = inspect_raw_checkpoint(raw)
    bootstrap = inspect_bootstrap_state(state_file)
    classification = classify_segment(
        exit_code=exit_code,
        bootstrap_valid=bool(bootstrap.get("valid")),
        native_resumable=bool(native.get("resumable")),
    )
    report = {
        "classification": classification,
        "model": model,
        "segment": int(segment),
        "segment_valid": int(segment_valid),
        "exit_code": int(exit_code),
        "stopped_for_native_resume": stopped_for_native,
        "bootstrap_state": bootstrap,
        "native_checkpoint": native,
        "parent_checkpoint_digest": resolved_parent_digest,
    }
    (root / "hosted_segment_status.json").write_text(
        json.dumps(report, indent=2, sort_keys=True), encoding="utf-8"
    )

    output_bundle = Path(output_bundle).resolve()
    if classification == "BOOTSTRAP_REQUIRED":
        manifest = promote_bootstrap_bundle(
            state_file, output_bundle,
            model=model, segment=int(segment), parent_digest=resolved_parent_digest,
            science_manifest=science_manifest, runtime_manifest=runtime_manifest,
            output_prefix=output_prefix, status=report,
        )
    elif classification == "RESUMABLE":
        manifest = promote_checkpoint(
            raw, output_bundle,
            model=model, segment=int(segment), parent_digest=resolved_parent_digest,
            science_manifest=science_manifest, runtime_manifest=runtime_manifest,
            output_prefix=output_prefix, status=report,
        )
    else:
        raise RuntimeError(f"hosted bootstrap segment failed: {json.dumps(report, sort_keys=True)}")
    report["checkpoint_digest"] = manifest["checkpoint_digest"]
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Run one GitHub-hosted PEER pre-resume bootstrap segment.")
    parser.add_argument("--model", choices=["M1", "M3"], required=True)
    parser.add_argument("--science", type=Path, required=True)
    parser.add_argument("--packages", required=True)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--runtime-manifest", type=Path, required=True)
    parser.add_argument("--output-bundle", type=Path, required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--segment", type=int, required=True)
    parser.add_argument("--segment-valid", type=int, default=1000)
    parser.add_argument("--parent-bundle", type=Path)
    parser.add_argument("--parent-digest")
    parser.add_argument("--poll-seconds", type=float, default=20.0)
    parser.add_argument("--grace-seconds", type=float, default=60.0)
    parser.add_argument("--skip-cobaya-preflight", action="store_true")
    args = parser.parse_args()
    report = run_hosted_segment(
        model=args.model, science=args.science, packages=args.packages, work=args.work,
        runtime_manifest_path=args.runtime_manifest, output_bundle=args.output_bundle,
        seed=args.seed, segment=args.segment, segment_valid=args.segment_valid,
        parent_bundle=args.parent_bundle, parent_digest=args.parent_digest,
        poll_seconds=args.poll_seconds, grace_seconds=args.grace_seconds,
        skip_cobaya_preflight=args.skip_cobaya_preflight,
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
