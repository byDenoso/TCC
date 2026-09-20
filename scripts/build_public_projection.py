#!/usr/bin/env python3
"""Compile the deterministic public projection from canonical Tower state.

Read-only with respect to canonical state: it writes only the projection artifacts.

    python scripts/build_public_projection.py \
        --root TOWER_V06 \
        --out TOWER_V06/snapshot/pages \
        --tower-commit "$GITHUB_SHA"

The writer is content-addressed:
* identical canonical content is a true NO_OP, so metadata-only refreshes cannot
  claim a newer Tower revision over stale projection bytes;
* changed content is written with atomic file replacement, with projection first
  and manifest last, so a consumer that sees an intermediate state fails closed
  on fingerprint mismatch instead of accepting mixed generations.

Exits non-zero when the produced projection fails its own verification, so a
broken projection can never be published.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from runtime.nexo_agent_api.public_projection import (  # noqa: E402
    build_public_projection,
    projection_bytes,
    verify_projection,
)


def verify_root_provenance(root: str | Path, tower_commit: str) -> str:
    """Prove that root is a clean checkout of the declared canonical commit."""
    root = Path(root).resolve()
    declared = str(tower_commit or "").strip().lower()
    if len(declared) != 40 or any(ch not in "0123456789abcdef" for ch in declared):
        raise ValueError("tower_commit must be a full 40-hex commit SHA")
    try:
        head = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip().lower()
    except (OSError, subprocess.CalledProcessError) as exc:
        raise ValueError("Tower root is not inside a readable Git checkout") from exc
    if head != declared:
        raise ValueError(f"Tower root HEAD {head} differs from declared tower_commit {declared}")
    try:
        dirty = subprocess.run(
            ["git", "-C", str(root), "status", "--porcelain=v1", "--untracked-files=all", "--", "."],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError) as exc:
        raise ValueError("Unable to verify Tower root worktree cleanliness") from exc
    if dirty:
        raise ValueError("Tower root worktree is not clean; refusing mixed-revision projection")
    return head


def _manifest_bytes(projection: dict) -> bytes:
    return (
        json.dumps(
            projection["manifest"],
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")


def _existing_fingerprint(path: Path) -> str | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return None
    manifest = payload.get("manifest") if isinstance(payload, dict) else None
    if not isinstance(manifest, dict):
        return None
    value = manifest.get("projection_fingerprint")
    return str(value) if value else None


def _atomic_replace(path: Path, data: bytes) -> None:
    """Replace one artifact atomically within its destination directory."""
    tmp = path.with_name(f".{path.name}.tmp")
    try:
        with tmp.open("wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    finally:
        try:
            tmp.unlink()
        except FileNotFoundError:
            pass


def write_projection_if_changed(out: str | Path, projection: dict) -> bool:
    """Persist a verified projection only when canonical content changed.

    Returns True when new bytes were written, False for a content-identical NO_OP.
    The manifest is replaced last. Consumers therefore either observe the old
    matching pair, the new matching pair, or a transient mismatch that their
    verifier must reject.
    """
    ok, detail = verify_projection(projection)
    if not ok:
        raise ValueError(f"public projection failed verification: {detail}")

    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    projection_path = out / "projection.json"
    manifest_path = out / "manifest.json"

    new_fingerprint = str(projection["manifest"]["projection_fingerprint"])
    if _existing_fingerprint(projection_path) == new_fingerprint:
        return False

    _atomic_replace(projection_path, projection_bytes(projection))
    _atomic_replace(manifest_path, _manifest_bytes(projection))
    return True


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default="TOWER_V06", help="canonical Tower root")
    parser.add_argument("--out", default="TOWER_V06/snapshot/pages", help="output directory")
    parser.add_argument("--tower-repository", default="byDenoso/NEXO-Obsidian-Vault")
    parser.add_argument("--tower-commit", default=None)
    parser.add_argument(
        "--no-timestamp",
        action="store_true",
        help="omit generated_at so two builds are byte-identical",
    )
    args = parser.parse_args()

    if not args.tower_commit:
        print("::error::--tower-commit is required for a publishable projection", file=sys.stderr)
        return 1
    try:
        verify_root_provenance(args.root, args.tower_commit)
    except ValueError as exc:
        print(f"::error::public projection provenance check failed: {exc}", file=sys.stderr)
        return 1

    generated_at = (
        None
        if args.no_timestamp
        else datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    )

    projection = build_public_projection(
        args.root,
        tower_repository=args.tower_repository,
        tower_commit=args.tower_commit,
        generated_at=generated_at,
    )

    ok, detail = verify_projection(projection)
    if not ok:
        print(f"::error::public projection failed verification: {detail}", file=sys.stderr)
        return 1

    changed = write_projection_if_changed(args.out, projection)

    manifest = projection["manifest"]
    print(f"projection_fingerprint = {manifest['projection_fingerprint']}")
    print(f"event_cursor           = {manifest['event_cursor']}")
    print(f"tower_commit           = {manifest['tower_commit']}")
    print(f"active_work            = {projection['counts']['active_work']}")
    print(f"index_only_dropped     = {projection['counts']['index_only_dropped']}")
    print(f"write_status           = {'UPDATED' if changed else 'NO_OP'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
