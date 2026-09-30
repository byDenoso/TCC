#!/usr/bin/env python3
"""Leitura da Tower pelo bundle existente, sem gravar estado canonico."""
from __future__ import annotations
import argparse
import ast
import base64
import contextlib
import hashlib
import io
import json
import sys
import tempfile
import types
import zipfile
from pathlib import Path

KNOWN_BUNDLE = "0f7667ecf8fc6afb91748a6273400d01a6699bcda8c502ad60a164781ed05138"


def review_stamp(value: object) -> str:
    # Preserva o primeiro _stamp da versao auditada, sobrescrito no modulo.
    return str((value.get("at") if isinstance(value, dict) else value) or "")


def bind_review_clock(module: object) -> None:
    original = module._review_queue
    isolated_globals = dict(original.__globals__, _stamp=review_stamp)
    module._review_queue = types.FunctionType(
        original.__code__, isolated_globals, original.__name__,
        original.__defaults__, original.__closure__,
    )


def read_status(tower_path: Path, bundle_path: Path) -> dict:
    raw = tower_path.read_bytes()
    input_hash = hashlib.sha256(raw).hexdigest()
    tree = ast.parse(bundle_path.read_bytes())
    encoded = next(ast.literal_eval(node.value) for node in tree.body
                   if isinstance(node, ast.Assign) and any(
                       isinstance(target, ast.Name) and target.id == "_BUNDLE"
                       for target in node.targets))
    archive = base64.b64decode(encoded, validate=True)
    digest = hashlib.sha256(archive).hexdigest()
    with tempfile.TemporaryDirectory(prefix="nexo-workspace-read-") as temporary:
        root = Path(temporary).resolve()
        with zipfile.ZipFile(io.BytesIO(archive)) as package:
            for entry in package.infolist():
                if not (root / entry.filename).resolve().is_relative_to(root):
                    raise ValueError("Caminho inseguro no bundle")
            package.extractall(root)
        sys.path.insert(0, str(root))
        try:
            from runtime.nexo_agent_api import evolution
            from runtime.nexo_agent_api.live_tower import (
                materialize_live_tower, read_live_tower_bytes, verify_live_tower,
            )
            revision = verify_live_tower(read_live_tower_bytes(raw))
            tower, _ = materialize_live_tower(raw, root / "TOWER_V06")
            errors = io.StringIO()
            with contextlib.redirect_stderr(errors):
                status = evolution.evolution_status(tower)
            native_warning = errors.getvalue()
            repaired = False
            if (digest == KNOWN_BUNDLE and
                "review_queue skipped (TypeError:" in native_warning and
                "NoneType" in native_warning and "datetime.datetime" in native_warning):
                bind_review_clock(evolution)
                queue_errors = io.StringIO()
                with contextlib.redirect_stderr(queue_errors):
                    status = evolution.evolution_status(tower)
                remaining = queue_errors.getvalue()
                repaired = "review_queue skipped" not in remaining
            else:
                remaining = native_warning
            if input_hash != hashlib.sha256(tower_path.read_bytes()).hexdigest():
                raise RuntimeError("A copia de entrada mudou durante a leitura")
            return {
                "read_status": "DEGRADED" if remaining else (
                    "OK_LOCAL_REVIEW_CLOCK_REPAIR" if repaired else "OK_NATIVE"),
                "read_only": True,
                "input_unchanged": True,
                "source_revision": revision,
                "bundle_sha256": digest,
                "review_queue_repaired_locally": repaired,
                "native_warning": native_warning.strip(),
                "remaining_warning": remaining.strip(),
                "published_projection_verified": False,
                "data": status,
            }
        finally:
            sys.path.remove(str(root))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tower", type=Path)
    parser.add_argument("bundle", type=Path)
    args = parser.parse_args()
    try:
        result = read_status(args.tower, args.bundle)
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
        return 2 if result["read_status"] == "DEGRADED" else 0
    except Exception as error:
        print(json.dumps({"read_status": "FAILED", "error": str(error)}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
