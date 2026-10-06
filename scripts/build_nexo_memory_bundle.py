#!/usr/bin/env python3
"""Build the memory 1.0.1 / retrieval 1.1.0 loader from reviewable sources.

Generated wrappers are outputs, never a source for the Writer build. No network
or live Tower access is used. Run --check in CI to reject stale/corrupt wrappers.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import io
import json
from pathlib import Path
import zipfile

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "gpt" / "nexo_memory.py"
MEMORY_SOURCES = ("memory.py", "memory_cli.py", "live_tower.py", "tower_paths.py")
RETRIEVAL_SOURCES = ("retrieval.py", "retrieval_cli.py", "retrieval_mcp.py", "retrieval_models.py")


TEMPLATE = '''#!/usr/bin/env python3
"""NEXO private memory 1.0.1. No network, no Tower writes, no scheduler changes."""
import base64, hashlib, io, json, sys, tempfile, zipfile
from pathlib import Path
_BUNDLE = "{memory_payload}"
_SHA256 = "{memory_digest}"
_RETRIEVAL_BUNDLE = "{retrieval_payload}"
_RETRIEVAL_SHA256 = "{retrieval_digest}"

def _extract(raw, root, label):
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        for member in archive.infolist():
            target = (root / member.filename).resolve()
            if root.resolve() not in target.parents:
                raise RuntimeError(f"Invalid {{label}} bundle path")
        archive.extractall(root)

def main():
    memory_raw = base64.b64decode(_BUNDLE, validate=True)
    retrieval_raw = base64.b64decode(_RETRIEVAL_BUNDLE, validate=True)
    if hashlib.sha256(memory_raw).hexdigest() != _SHA256:
        raise RuntimeError("Memory package integrity failure")
    if hashlib.sha256(retrieval_raw).hexdigest() != _RETRIEVAL_SHA256:
        raise RuntimeError("Retrieval package integrity failure")
    if sys.argv[1:] == ["--version"]:
        print(json.dumps({{
            "version": "1.1.0",
            "memory_version": "1.0.1",
            "retrieval_version": "1.1.0",
            "memory_package_sha256": _SHA256,
            "retrieval_package_sha256": _RETRIEVAL_SHA256,
            "tower_mutation": False,
        }}))
        return 0
    with tempfile.TemporaryDirectory(prefix="nexo-memory-") as folder:
        root = Path(folder)
        _extract(memory_raw, root, "memory")
        _extract(retrieval_raw, root, "retrieval")
        sys.path.insert(0, str(root))
        args = list(sys.argv[1:])
        if args and args[0] in {{"context", "search"}}:
            from runtime.nexo_agent_api.retrieval_cli import main as run, memory_cache_path
            if len(args) >= 3:
                args[2] = memory_cache_path(args[2])
        else:
            from runtime.nexo_agent_api.memory_cli import main as run
        return run(args)

if __name__ == "__main__":
    raise SystemExit(main())
'''


def _archive(sources: dict[str, bytes], *, compresslevel: int) -> bytes:
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        for name, raw in sorted(sources.items()):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            archive.writestr(info, raw, compresslevel=compresslevel)
    return stream.getvalue()


def render() -> bytes:
    memory = {"runtime/__init__.py": b"", "runtime/nexo_agent_api/__init__.py": b""}
    for name in MEMORY_SOURCES:
        path = f"runtime/nexo_agent_api/{name}"
        memory[path] = (REPO / path).read_bytes()
    manifest = {
        "classification": "CODE_ONLY",
        "version": "1.0.1",
        "sources": {name: hashlib.sha256(raw).hexdigest() for name, raw in memory.items()},
    }
    memory["manifest.json"] = json.dumps(manifest, sort_keys=True).encode("utf-8")
    retrieval = {
        f"runtime/nexo_agent_api/{name}": (REPO / "runtime/nexo_agent_api" / name).read_bytes()
        for name in RETRIEVAL_SOURCES
    }
    # Preserve the installed release line's deterministic compression settings.
    memory_raw = _archive(memory, compresslevel=6)
    retrieval_raw = _archive(retrieval, compresslevel=9)
    return TEMPLATE.format(
        memory_payload=base64.b64encode(memory_raw).decode("ascii"),
        memory_digest=hashlib.sha256(memory_raw).hexdigest(),
        retrieval_payload=base64.b64encode(retrieval_raw).decode("ascii"),
        retrieval_digest=hashlib.sha256(retrieval_raw).hexdigest(),
    ).encode("utf-8")


def build() -> Path:
    output = render()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_bytes(output)
    return OUT


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Fail if the committed loader differs from source")
    args = parser.parse_args()
    if args.check:
        if not OUT.is_file() or OUT.read_bytes() != render():
            parser.exit(1, "nexo_memory.py is stale or corrupt; run scripts/build_nexo_memory_bundle.py\n")
    else:
        print(build())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
