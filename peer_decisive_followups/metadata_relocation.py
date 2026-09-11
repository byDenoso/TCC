from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


LOCATION_KEYS = {"python_path", "packages_path", "output"}


def _relocate_components(old: dict[str, Any], current: dict[str, Any], block: str) -> None:
    old_block = old.get(block)
    new_block = current.get(block)
    if not isinstance(old_block, dict) or not isinstance(new_block, dict):
        return
    for name, current_spec in new_block.items():
        old_spec = old_block.get(name)
        if not isinstance(old_spec, dict) or not isinstance(current_spec, dict):
            continue
        if "python_path" in current_spec:
            old_spec["python_path"] = current_spec["python_path"]
        # Component `path` may locate an external implementation (e.g. `global`).
        # Relocate it only when the new canonical config explicitly supplies it.
        if "path" in current_spec and "path" in old_spec:
            old_spec["path"] = current_spec["path"]


def relocate_cobaya_metadata(output_prefix: Path, current_config: dict[str, Any]) -> dict[str, Any]:
    """Relocate only machine-specific paths in restored Cobaya info files.

    Scientific values are deliberately not overlaid. The checkpoint's semantic identity
    has already been verified before this function is called; this merely makes that
    verified run portable to a new filesystem location.
    """
    prefix = Path(output_prefix)
    changed_files: list[str] = []
    changes: dict[str, dict[str, Any]] = {}
    for suffix in (".input.yaml", ".updated.yaml"):
        path = Path(str(prefix) + suffix)
        if not path.is_file():
            continue
        old = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(old, dict):
            raise ValueError(f"Cobaya metadata must be a mapping: {path}")
        before = {
            "packages_path": old.get("packages_path"),
            "output": old.get("output"),
        }
        if "packages_path" in current_config:
            old["packages_path"] = current_config["packages_path"]
        if "output" in current_config:
            old["output"] = current_config["output"]
        for block in ("theory", "likelihood"):
            _relocate_components(old, current_config, block)
        path.write_text(yaml.safe_dump(old, sort_keys=False), encoding="utf-8")
        changed_files.append(path.name)
        changes[path.name] = {
            "packages_path": [before["packages_path"], old.get("packages_path")],
            "output": [before["output"], old.get("output")],
        }
    return {"files": changed_files, "changes": changes}
