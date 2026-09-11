from __future__ import annotations

import argparse
import json
from pathlib import Path

from peer_decisive_followups.checkpoint_manager import (
    CheckpointError,
    promote_checkpoint,
    restore_bundle,
)
from peer_decisive_followups.production_config import build_production_configs
from peer_decisive_followups.production_contract import sha256_json
from peer_decisive_followups.run_segment import run_segment


def _load_json(path: Path) -> dict:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON object required: {path}")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run one verified PEER PolyChord continuation segment."
    )
    parser.add_argument("--model", choices=["M1", "M3"], required=True)
    parser.add_argument("--science", type=Path, required=True)
    parser.add_argument("--packages", required=True)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--runtime-manifest", type=Path, required=True)
    parser.add_argument("--parent-bundle", type=Path, required=True)
    parser.add_argument("--expected-parent-digest")
    parser.add_argument("--output-bundle", type=Path, required=True)
    parser.add_argument("--segment", type=int, required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--seconds", type=float, default=19200)
    parser.add_argument("--grace-seconds", type=float, default=45.0)
    args = parser.parse_args()

    work = args.work.resolve()
    root = work / f"nested_{args.model}"
    built = build_production_configs(
        args.science.resolve(),
        args.model,
        args.packages,
        root,
        args.seed,
        continuation=True,
    )
    science_manifest = built["science_manifest"]
    runtime_manifest = _load_json(args.runtime_manifest.resolve())
    science_sha = sha256_json(science_manifest)
    runtime_sha = sha256_json(runtime_manifest)

    raw = root / "data" / "chain_polychord_raw"
    expected = {
        "model": args.model,
        "science_sha": science_sha,
        "runtime_sha": runtime_sha,
    }
    if args.expected_parent_digest:
        expected["checkpoint_digest"] = args.expected_parent_digest

    # verify_bundle/restore_bundle validates content before replacing the destination.
    parent = restore_bundle(args.parent_bundle.resolve(), raw, expected)
    if args.expected_parent_digest and parent.get("checkpoint_digest") != args.expected_parent_digest:
        raise CheckpointError("parent checkpoint digest mismatch")

    data_dir = root / "data"
    result = run_segment(
        [
            "mpirun", "--oversubscribe", "-np", "4", "cobaya-run",
            str((root / "data.yaml").resolve()),
        ],
        cwd=work,
        raw=raw,
        stdout_path=data_dir / "stdout.segment.log",
        stderr_path=data_dir / "stderr.segment.log",
        seconds=args.seconds,
        grace_seconds=args.grace_seconds,
    )

    status_path = root / "segment_status.json"
    status_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))

    if result["classification"] not in {"RESUMABLE", "COMPLETE"}:
        return 2

    child = promote_checkpoint(
        raw,
        args.output_bundle.resolve(),
        model=args.model,
        segment=args.segment,
        parent_digest=parent["checkpoint_digest"],
        science_manifest=science_manifest,
        runtime_manifest=runtime_manifest,
    )
    lineage = {
        "classification": result["classification"],
        "parent_checkpoint_digest": parent["checkpoint_digest"],
        "checkpoint_digest": child["checkpoint_digest"],
        "science_sha": science_sha,
        "runtime_sha": runtime_sha,
        "segment": args.segment,
        "model": args.model,
    }
    (args.output_bundle.resolve() / "segment_status.json").write_text(
        json.dumps({**result, **lineage}, indent=2, sort_keys=True), encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
