"""Local GC commands routed through the existing self-contained Writer."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from . import tower_gc


def _write_json(path, value):
    _write_private(path, json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2).encode() + b"\n")


def _write_private(path, raw):
    import os
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    # Generated maintenance artifacts are private even in a permissive umask.
    fd = os.open(destination, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(raw)
    except BaseException:
        destination.unlink(missing_ok=True)
        raise


def main(argv):
    parser = argparse.ArgumentParser(description="Tower GC: dry-run and isolated recovery rehearsal; no canonical writes")
    commands = parser.add_subparsers(dest="command", required=True)
    dry = commands.add_parser("dry-run")
    dry.add_argument("tower")
    dry.add_argument("report")
    backup = commands.add_parser("backup")
    backup.add_argument("tower")
    backup.add_argument("archive")
    backup.add_argument("manifest")
    archive = commands.add_parser("archive")
    archive.add_argument("tower")
    archive.add_argument("paths")
    archive.add_argument("archive")
    archive.add_argument("manifest")
    restore = commands.add_parser("restore")
    restore.add_argument("tower")
    restore.add_argument("archive")
    restore.add_argument("manifest")
    restore.add_argument("expected_revision")
    restore.add_argument("output")
    args = parser.parse_args(argv)
    try:
        raw = Path(args.tower).read_bytes()
        if args.command == "dry-run":
            result = tower_gc.plan_gc(raw)
            _write_json(args.report, result)
            print(json.dumps({"status": "DRY_RUN", **result["summary"]}, sort_keys=True))
        elif args.command in {"backup", "archive"}:
            if Path(args.archive).resolve() == Path(args.manifest).resolve():
                raise tower_gc.TowerGCError('GC_OUTPUT_PATHS_ALIAS')
            if args.command == "backup":
                packed, receipt = tower_gc.prepare_backup(raw)
            else:
                paths = json.loads(Path(args.paths).read_bytes())
                if not isinstance(paths, list) or not all(isinstance(path, str) for path in paths):
                    raise tower_gc.TowerGCError("GC_PATHS_INVALID")
                packed, receipt = tower_gc.prepare_archive(raw, paths)
            # Both outputs must be fresh; never overwrite a Tower or backup.
            if Path(args.manifest).exists() or Path(args.archive).exists():
                raise tower_gc.TowerGCError("GC_OUTPUT_ALREADY_EXISTS")
            _write_private(args.archive, packed)
            try:
                # Read back actual disk bytes, then emit the manifest.
                actual = Path(args.archive).read_bytes()
                if args.command == "backup":
                    tower_gc.restore_backup(actual, receipt)
                else:
                    tower_gc.verify_archive(actual, receipt)
                _write_json(args.manifest, receipt)
            except BaseException:
                Path(args.archive).unlink(missing_ok=True)
                raise
            print(json.dumps({"status": "REHEARSAL_ONLY", "archive_bytes": len(packed), "readback": "PASS"}))
        else:
            receipt = json.loads(Path(args.manifest).read_bytes())
            restored, result = tower_gc.restore_entries(raw, Path(args.archive).read_bytes(), receipt,
                                                        expected_revision=args.expected_revision)
            _write_private(args.output, restored)
            print(json.dumps(result))
        return 0
    except (ValueError, OSError) as exc:
        # Avoid disclosing object paths or private payloads in shared logs.
        print(json.dumps({"status": "GC_FAILED", "error_type": type(exc).__name__}))
        return 2
