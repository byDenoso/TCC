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
import gzip
import json
import os
import subprocess
import sys
import tempfile
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


def materialize_drive_bundle_root(
    bundle_path: str | Path,
    current_path: str | Path,
    destination: str | Path,
) -> tuple[Path, dict[str, object]]:
    """Verify a Drive CURRENT+bundle pair and materialize a read-only Tower root."""
    bundle_path = Path(bundle_path)
    current_path = Path(current_path)
    with gzip.open(bundle_path, "rt", encoding="utf-8") as handle:
        bundle = json.load(handle)
    current = json.loads(current_path.read_text(encoding="utf-8"))

    if bundle.get("contract") not in {"NEXO_DRIVE_BUNDLE_V3", "NEXO_TOWER_BUNDLE_V1"}:
        raise ValueError(f"unsupported Drive bundle contract: {bundle.get('contract')!r}")
    if bundle.get("authority") != "TOWER_V06" or bundle.get("storage") != "GOOGLE_DRIVE_PRIVATE":
        raise ValueError("Drive bundle is not canonical TOWER_V06 storage")
    files = bundle.get("files")
    if not isinstance(files, dict) or bundle.get("file_count") != len(files):
        raise ValueError("Drive bundle file_count does not match files payload")
    if current.get("contract") != "NEXO_DRIVE_CURRENT_V3":
        raise ValueError("Drive CURRENT contract is not NEXO_DRIVE_CURRENT_V3")
    if current.get("snapshot_id") != bundle.get("canonical_revision"):
        raise ValueError("Drive CURRENT snapshot_id differs from bundle canonical_revision")
    if current.get("state_fingerprint") != bundle.get("state_fingerprint"):
        raise ValueError("Drive CURRENT state_fingerprint differs from bundle")
    if current.get("truth_owner") != "TOWER_V06@GOOGLE_DRIVE_PRIVATE" or current.get("cutover_active") is not True:
        raise ValueError("Drive CURRENT is not an active canonical cutover pointer")

    root = Path(destination).resolve()
    root.mkdir(parents=True, exist_ok=True)
    for relative, entry in files.items():
        if not isinstance(relative, str) or not isinstance(entry, dict):
            continue
        target = (root / relative).resolve()
        if target != root and root not in target.parents:
            raise ValueError(f"unsafe bundle path: {relative!r}")
        encoding = entry.get("encoding")
        if encoding == "json":
            data = json.dumps(entry.get("value"), ensure_ascii=False, sort_keys=True, indent=2) + "\n"
        elif encoding == "text":
            data = str(entry.get("data") or "")
        else:
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(data, encoding="utf-8")

    control = json.loads((root / "CONTROL.json").read_text(encoding="utf-8"))
    if control.get("truth_owner") != current.get("truth_owner"):
        raise ValueError("materialized CONTROL truth_owner differs from Drive CURRENT")

    metadata = {
        "export_role": "PUBLIC_READ_ONLY_DERIVED_COPY",
        "source_snapshot_id": current.get("snapshot_id"),
        "source_state_fingerprint": current.get("state_fingerprint"),
        "source_storage": current.get("storage"),
        "source_promoted_at": current.get("promoted_at"),
        "truth_owner": current.get("truth_owner"),
    }
    return root, {key: value for key, value in metadata.items() if value is not None}


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
    parser.add_argument("--drive-bundle", default=None, help="canonical TOWER.bundle.json.gz from Drive CURRENT")
    parser.add_argument("--drive-current", default=None, help="CURRENT.json paired with --drive-bundle")
    parser.add_argument(
        "--no-timestamp",
        action="store_true",
        help="omit generated_at so two builds are byte-identical",
    )
    args = parser.parse_args()

    if not args.tower_commit:
        print("::error::--tower-commit is required as code/provenance identity", file=sys.stderr)
        return 1

    temporary_root = None
    source_metadata: dict[str, object] = {}
    projection_root: str | Path = args.root
    try:
        if args.drive_bundle:
            if not args.drive_current:
                raise ValueError("--drive-current is required with --drive-bundle")
            temporary_root = tempfile.TemporaryDirectory(prefix="nexo-drive-projection-")
            projection_root, source_metadata = materialize_drive_bundle_root(
                args.drive_bundle,
                args.drive_current,
                Path(temporary_root.name) / "TOWER_V06",
            )
        else:
            verify_root_provenance(args.root, args.tower_commit)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        if temporary_root is not None:
            temporary_root.cleanup()
        print(f"::error::public projection provenance check failed: {exc}", file=sys.stderr)
        return 1

    generated_at = (
        None
        if args.no_timestamp
        else datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    )

    projection = build_public_projection(
        projection_root,
        tower_repository=args.tower_repository,
        tower_commit=args.tower_commit,
        generated_at=generated_at,
    )
    projection["manifest"].update(source_metadata)

    ok, detail = verify_projection(projection)
    if not ok:
        print(f"::error::public projection failed verification: {detail}", file=sys.stderr)
        return 1

    changed = write_projection_if_changed(args.out, projection)
    if temporary_root is not None:
        temporary_root.cleanup()

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
