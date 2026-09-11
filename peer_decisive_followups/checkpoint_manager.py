from __future__ import annotations

import hashlib
import json
import os
import shutil
from pathlib import Path


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def inspect_checkpoint(raw: Path) -> dict:
    raw = Path(raw)
    resumes = sorted(raw.glob("*.resume")) if raw.exists() else []
    live = sorted(raw.glob("*_phys_live.txt")) if raw.exists() else []
    dead = sorted(raw.glob("*_dead.txt")) if raw.exists() else []
    if resumes:
        phase = "sampling"
    elif live:
        phase = "initializing_live_points"
    else:
        phase = "not_started"
    return {
        "resumable": bool(resumes),
        "phase": phase,
        "resume_files": [p.name for p in resumes],
        "live_files": [p.name for p in live],
        "dead_files": [p.name for p in dead],
    }


def snapshot_checkpoint(raw: Path, out: Path) -> dict:
    raw, out = Path(raw), Path(out)
    status = inspect_checkpoint(raw)
    tmp = out.with_name(out.name + ".tmp")
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir(parents=True, exist_ok=True)
    if raw.exists():
        for src in raw.iterdir():
            if src.is_file():
                shutil.copy2(src, tmp / src.name)
    resume_meta = []
    for name in status["resume_files"]:
        p = tmp / name
        resume_meta.append({"name": name, "size": p.stat().st_size, "sha256": _sha256(p)})
    manifest = {**status, "resume_meta": resume_meta}
    (tmp / "checkpoint_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    if out.exists():
        shutil.rmtree(out)
    os.replace(tmp, out)
    return manifest
