#!/usr/bin/env python3
"""Compile the deterministic public projection from canonical Tower state.

Read-only with respect to canonical state: it writes only the projection artifacts.

    python scripts/build_public_projection.py \
        --root TOWER_V06 \
        --out TOWER_V06/snapshot/pages \
        --tower-commit "$GITHUB_SHA"

Exits non-zero when the produced projection fails its own verification, so a
broken projection can never be published.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from runtime.nexo_agent_api.public_projection import (  # noqa: E402
    build_public_projection,
    projection_bytes,
    verify_projection,
)


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

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "projection.json").write_bytes(projection_bytes(projection))
    (out / "manifest.json").write_bytes(
        (json.dumps(projection["manifest"], ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    )

    manifest = projection["manifest"]
    print(f"projection_fingerprint = {manifest['projection_fingerprint']}")
    print(f"event_cursor           = {manifest['event_cursor']}")
    print(f"tower_commit           = {manifest['tower_commit']}")
    print(f"active_work            = {projection['counts']['active_work']}")
    print(f"index_only_dropped     = {projection['counts']['index_only_dropped']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
