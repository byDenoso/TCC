from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from peer_decisive_followups.evidence import parse_polychord_stats
from peer_decisive_followups.production_config import build_production_configs
from peer_decisive_followups.production_contract import sha256_json
from peer_decisive_followups.runtime_contract import verify_runtime_manifest


def _find_stats(root: Path) -> Path:
    matches = sorted(root.rglob("*.stats"))
    if len(matches) != 1:
        raise RuntimeError(f"expected exactly one PolyChord stats file under {root}, found {matches}")
    return matches[0]


def run_prior_normalization(*, model: str, science: Path, packages: str, work: Path,
                            runtime_manifest_path: Path, seed: int,
                            output_path: Path) -> dict:
    runtime_manifest = json.loads(runtime_manifest_path.read_text(encoding="utf-8"))
    runtime_manifest = verify_runtime_manifest(runtime_manifest)
    work = work.resolve()
    root = work / f"nested_{model}"
    built = build_production_configs(
        science.resolve(), model, packages, root, seed, continuation=False
    )
    science_manifest = built["science_manifest"]
    config = root / "prior_volume.yaml"
    prior_dir = root / "prior_volume"
    prior_dir.mkdir(parents=True, exist_ok=True)
    stdout_path = prior_dir / "stdout.log"
    stderr_path = prior_dir / "stderr.log"
    with stdout_path.open("w", encoding="utf-8") as out, stderr_path.open("w", encoding="utf-8") as err:
        proc = subprocess.run(
            ["mpirun", "--oversubscribe", "-np", "4", "cobaya-run", str(config.resolve())],
            cwd=work,
            stdout=out,
            stderr=err,
            text=True,
        )
    if proc.returncode != 0:
        raise RuntimeError(f"prior-volume PolyChord failed with exit code {proc.returncode}")
    stats_path = _find_stats(prior_dir)
    evidence = parse_polychord_stats(stats_path)
    result = {
        "schema": "peer-prior-normalization-v1",
        "status": "COMPLETE",
        "model": model,
        "seed": int(seed) + 90000,
        "science_sha": sha256_json(science_manifest),
        "runtime_sha": sha256_json(runtime_manifest),
        "logZ": evidence["logZ"],
        "logZstd": evidence["logZstd"],
        "stats": evidence,
        "normalization_convention": "Cobaya external-prior unit-likelihood correction",
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Run PEER prior-volume normalization independently of data sampling.")
    parser.add_argument("--model", choices=["M1", "M3"], required=True)
    parser.add_argument("--science", type=Path, required=True)
    parser.add_argument("--packages", required=True)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--runtime-manifest", type=Path, required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run_prior_normalization(
        model=args.model,
        science=args.science,
        packages=args.packages,
        work=args.work,
        runtime_manifest_path=args.runtime_manifest,
        seed=args.seed,
        output_path=args.output,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
