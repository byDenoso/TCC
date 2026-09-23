#!/usr/bin/env python3
"""The one entry point that reads and writes the live NEXO Tower.

    nexo_tower.py status                 Drive head vs published ATLAS manifest
    nexo_tower.py pull   [--dest DIR]    download + verify + materialize (read-only use)
    nexo_tower.py download --out FILE    raw live Tower bytes (CI reader)
    nexo_tower.py apply  REQUEST.json... mutate -> CAS write same file id -> readback -> notify ATLAS
    nexo_tower.py project --out DIR      build the public projection straight from Drive
    nexo_tower.py inbox list|done IDS    proposals ChatGPT created in Drive NEXO_INBOX

Every automation and every human-driven change goes through ``apply``; nothing
else writes operational truth.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from runtime.nexo_agent_api.drive_transport import (  # noqa: E402
    DriveInbox,
    DriveTower,
    TowerConflict,
    nexo_home,
    writer_lock,
)
from runtime.nexo_agent_api.live_tower import (  # noqa: E402
    LIVE_TOWER_NAME,
    materialize_live_tower,
    read_live_tower_bytes,
    verify_live_tower,
)

ATLAS_MANIFEST_URL = "https://bydenoso.github.io/Pantheon/tower-projection/manifest.json"
PAGES_REPOSITORY = "byDenoso/Pantheon"
PAGES_EVENT = "nexo-public-projection-updated"


def _print(payload: dict) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


def _published_manifest() -> dict | None:
    try:
        with urllib.request.urlopen(ATLAS_MANIFEST_URL + f"?t={int(time.time())}", timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception:
        return None


def cmd_status(_: argparse.Namespace) -> int:
    tower, head = DriveTower().read()
    fingerprint = verify_live_tower(tower)
    published = _published_manifest() or {}
    atlas_revision = published.get("tower_revision") or published.get("source_state_fingerprint")
    _print({
        "tower_state_fingerprint": fingerprint,
        "tower_head_revision_id": head.head_revision_id,
        "tower_modified_time": head.modified_time,
        "tower_file_count": tower.get("file_count"),
        "atlas_tower_revision": atlas_revision,
        "atlas_generated_at": published.get("generated_at"),
        "atlas": "CURRENT" if atlas_revision == fingerprint else ("UNREACHABLE" if not published else "OUTDATED"),
    })
    return 0


def cmd_download(args: argparse.Namespace) -> int:
    raw, head = DriveTower().download()
    fingerprint = verify_live_tower(read_live_tower_bytes(raw))
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(raw)
    _print({"path": str(out), "state_fingerprint": fingerprint, "head_revision_id": head.head_revision_id})
    return 0


def cmd_pull(args: argparse.Namespace) -> int:
    raw, head = DriveTower().download()
    fingerprint = verify_live_tower(read_live_tower_bytes(raw))
    dest = Path(args.dest) if args.dest else nexo_home() / "tower" / fingerprint.replace(":", "-")[:23] / "TOWER_V06"
    root, metadata = materialize_live_tower(raw, dest)
    _print({"root": str(root), "head_revision_id": head.head_revision_id, **metadata})
    return 0


def _notify_atlas() -> str:
    token = os.environ.get("NEXO_PAGES_DISPATCH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not token:
        return "SKIPPED_NO_TOKEN_CRON_RECONCILES"
    request = urllib.request.Request(
        f"https://api.github.com/repos/{PAGES_REPOSITORY}/dispatches",
        data=json.dumps({"event_type": PAGES_EVENT}).encode(),
        headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return f"DISPATCHED_{response.status}"
    except Exception as exc:  # the 15-min Pages reconciler still converges
        return f"DISPATCH_FAILED_{type(exc).__name__}"


def cmd_apply(args: argparse.Namespace) -> int:
    from runtime.nexo_agent_api.mutations import apply_mutation_request

    requests = []
    for name in args.requests:
        payload = json.loads(Path(name).read_text(encoding="utf-8"))
        requests.extend(payload if isinstance(payload, list) else [payload])

    attempts = max(1, args.retries + 1)
    for attempt in range(1, attempts + 1):
        try:
            with writer_lock():
                drive = DriveTower(write=True)
                raw, base = drive.download()
                before = verify_live_tower(read_live_tower_bytes(raw))
                with tempfile.TemporaryDirectory(prefix="nexo-tower-write-") as work:
                    root, _ = materialize_live_tower(raw, Path(work) / "TOWER_V06")
                    receipts = [apply_mutation_request(root, request) for request in requests]
                    rejected = [r for r in receipts if not r.get("accepted", True) or r.get("issue")]
                    if rejected:
                        _print({"status": "REJECTED", "tower_state_fingerprint": before, "receipts": receipts})
                        return 2
                    packed = (root / LIVE_TOWER_NAME).read_bytes()
                    after = verify_live_tower(read_live_tower_bytes(packed))
                    if after == before:
                        _print({"status": "NO_OP", "tower_state_fingerprint": before, "receipts": receipts})
                        return 0
                    if args.dry_run:
                        _print({"status": "DRY_RUN", "before": before, "after": after, "receipts": receipts})
                        return 0
                    write = drive.compare_and_swap(base, packed)
            _print({
                "status": "PASS",
                "before": before,
                "after": write["state_fingerprint"],
                "write": write,
                "atlas_notify": _notify_atlas(),
                "receipts": receipts,
            })
            return 0
        except TowerConflict as exc:
            if attempt == attempts:
                _print({"status": "CONFLICT", "detail": str(exc), "attempts": attempt})
                return 3
            time.sleep(min(30, 2 ** attempt))
    return 3


def cmd_project(args: argparse.Namespace) -> int:
    from runtime.nexo_agent_api.public_projection import build_public_projection, verify_projection

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from build_public_projection import write_projection_if_changed  # noqa: E402

    raw, _ = DriveTower().download()
    with tempfile.TemporaryDirectory(prefix="nexo-tower-project-") as work:
        root, metadata = materialize_live_tower(raw, Path(work) / "TOWER_V06")
        projection = build_public_projection(
            root,
            tower_revision=metadata["tower_revision"],
            tower_file_id=metadata["tower_file_id"],
            generated_at=None if args.no_timestamp else time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        )
        projection["manifest"].update(metadata)
        ok, detail = verify_projection(projection)
        if not ok:
            print(f"::error::projection failed verification: {detail}", file=sys.stderr)
            return 1
        changed = write_projection_if_changed(args.out, projection)
    _print({"out": args.out, "changed": changed, **projection["manifest"]})
    return 0


def cmd_inbox(args: argparse.Namespace) -> int:
    inbox = DriveInbox(write=args.action == "done")
    if args.action == "list":
        _print({"items": [{k: item.get(k) for k in ("id", "name", "createdTime", "payload")} for item in inbox.pending()]})
    else:
        for file_id in args.ids:
            inbox.mark_processed(file_id)
        _print({"processed": args.ids})
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status").set_defaults(func=cmd_status)
    p = sub.add_parser("download"); p.add_argument("--out", required=True); p.set_defaults(func=cmd_download)
    p = sub.add_parser("pull"); p.add_argument("--dest"); p.set_defaults(func=cmd_pull)
    p = sub.add_parser("apply")
    p.add_argument("requests", nargs="+", help="mutation request JSON files (object or list)")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--retries", type=int, default=2)
    p.set_defaults(func=cmd_apply)
    p = sub.add_parser("project"); p.add_argument("--out", required=True); p.add_argument("--no-timestamp", action="store_true"); p.set_defaults(func=cmd_project)
    p = sub.add_parser("inbox", help="ChatGPT proposal inbox on Drive (create-only)")
    p.add_argument("action", choices=["list", "done"])
    p.add_argument("ids", nargs="*")
    p.set_defaults(func=cmd_inbox)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
