from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

import yaml

from peer_decisive_followups.run_segment import run_with_checkpoints

SOURCE_RUN = "34561868964"


def sh(cmd: list[str], cwd: Path | None = None) -> None:
    print("+", " ".join(cmd), flush=True)
    subprocess.run(cmd, cwd=cwd, check=True)


def patch_historical_runner(nested_src: Path) -> None:
    runner = nested_src / "peer_decisive_followups" / "run_nested_lane.py"
    s = runner.read_text()
    s = s.replace('SOURCE_RUN = "30455821484"', f'SOURCE_RUN = "{SOURCE_RUN}"', 1)
    old = '    _replace_directory_link(work / "Rec_database", databases[0])\n    _replace_directory_link(work / "Development", developments[0])\n    (work / "temp").mkdir(exist_ok=True)\n'
    new = '    _replace_directory_link(work / "Rec_database", databases[0])\n    _replace_directory_link(work / "Development", developments[0])\n    _replace_directory_link(workspace / "Rec_database", databases[0])\n    _replace_directory_link(workspace / "Development", developments[0])\n    (work / "temp").mkdir(exist_ok=True)\n    (workspace / "temp").mkdir(exist_ok=True)\n'
    if old not in s:
        raise RuntimeError("CosmoRec binding contract changed")
    runner.write_text(s.replace(old, new, 1))

    cfg = nested_src / "peer_decisive_followups" / "build_nested_config.py"
    c = cfg.read_text()
    replacements = {
        '"nlive": "25d",': '"nlive": 400,',
        '"nprior": "20nlive",': '"nprior": "10nlive",',
        'info["resume"] = False': 'info["resume"] = True',
        'info["force"] = True': 'info["force"] = False',
    }
    for old_text, new_text in replacements.items():
        if old_text not in c:
            raise RuntimeError(f"config contract changed: {old_text}")
        c = c.replace(old_text, new_text, 1)
    cfg.write_text(c)


def patch_tau(root: Path) -> None:
    for name in ("data.yaml", "prior_volume.yaml"):
        p = root / name
        info = yaml.safe_load(p.read_text())
        tau = info.get("params", {}).get("tau", {})
        if isinstance(tau, dict) and isinstance(tau.get("prior"), dict) and tau["prior"].get("min") == 0.0:
            tau["prior"]["min"] = 0.01
        info["resume"] = True
        info["force"] = False
        p.write_text(yaml.safe_dump(info, sort_keys=False))


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--model", choices=["M1", "M3"], required=True)
    p.add_argument("--workspace", type=Path, required=True)
    p.add_argument("--seconds", type=int, default=19800)
    args = p.parse_args()

    ws = args.workspace.resolve()
    nested_src = ws / "nested-src"
    science = ws / "science-act"
    packages = ws / "packages"
    work = ws / f"evidence_{args.model}"
    root = work / f"nested_{args.model}"
    patch_historical_runner(nested_src)

    sys.path.insert(0, str(nested_src))
    from peer_decisive_followups.run_nested_lane import install_runtime
    install_runtime(work, packages)

    idx = 1 if args.model == "M1" else 3
    sh([
        sys.executable,
        str(nested_src / "peer_decisive_followups" / "build_nested_config.py"),
        "--science", str(science),
        "--model", args.model,
        "--packages", str(packages),
        "--root", str(root),
        "--seed", str(2026076100 + idx),
    ])
    patch_tau(root)

    data = root / "data"
    result = run_with_checkpoints(
        ["mpirun", "--oversubscribe", "-np", "4", "cobaya-run", str((root / "data.yaml").resolve())],
        cwd=work,
        raw=data / "chain_polychord_raw",
        snapshot=root / "checkpoint" / "raw",
        stdout_path=data / "stdout.segment.log",
        stderr_path=data / "stderr.segment.log",
        seconds=args.seconds,
    )
    status = root / "checkpoint" / "segment_status.json"
    status.parent.mkdir(parents=True, exist_ok=True)
    import json
    status.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))

    prior = root / "prior_volume"
    prior.mkdir(parents=True, exist_ok=True)
    with (prior / "stdout.segment.log").open("w") as out, (prior / "stderr.segment.log").open("w") as err:
        try:
            r = subprocess.run(
                ["mpirun", "--oversubscribe", "-np", "4", "cobaya-run", str((root / "prior_volume.yaml").resolve())],
                cwd=work, timeout=900, stdout=out, stderr=err, text=True,
            )
            code = r.returncode
        except subprocess.TimeoutExpired:
            code = 124
    (prior / "segment_exit_code.txt").write_text(str(code) + "\n", encoding="utf-8")
    return 0 if result["exit_code"] in (0, 124) else int(result["exit_code"])


if __name__ == "__main__":
    raise SystemExit(main())
