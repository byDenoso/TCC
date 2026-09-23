"""Single mapping between logical Tower paths and filesystem paths.

Tower identities contain ``::`` (``TEST::A``, ``WORK::GZ-01-B01``). The live
Tower bundle keys files by logical POSIX path, so identities stay exact there.
NTFS forbids ``:`` in file names, so on Windows the on-disk name escapes it.
Every place that turns an identity into a file path must go through here.
"""

from __future__ import annotations

import os
from pathlib import Path

_ESCAPE = os.name == "nt"


def fs_name(logical: str) -> str:
    """Filesystem-safe form of one logical path component."""
    if not _ESCAPE:
        return logical
    return logical.replace("%", "%25").replace(":", "%3A")


def logical_name(name: str) -> str:
    """Inverse of :func:`fs_name`."""
    if not _ESCAPE:
        return name
    return name.replace("%3A", ":").replace("%25", "%")


def fs_path(root: str | Path, logical: str) -> Path:
    """Resolve a logical ``a/b/c.json`` path under ``root`` for this OS."""
    return Path(root).joinpath(*(fs_name(part) for part in logical.split("/")))


def logical_path(root: str | Path, path: str | Path) -> str:
    """Logical POSIX path of ``path`` relative to ``root``."""
    relative = Path(path).relative_to(Path(root))
    return "/".join(logical_name(part) for part in relative.parts)


def entity_path(root: str | Path, kind: str, entity_id: str) -> Path:
    return Path(root) / "entities" / kind / fs_name(f"{entity_id}.json")


def json_file(directory: str | Path, identity: str) -> Path:
    """``<directory>/<identity>.json`` with the identity escaped for this OS."""
    return Path(directory) / fs_name(f"{identity}.json")
