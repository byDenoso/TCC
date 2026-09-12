from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from runtime.nexo_core.projection import validate_snapshot


class SnapshotValidationError(ValueError):
    pass


def publish_snapshot(snapshot: dict[str, Any], target: str | Path) -> Path:
    errors = validate_snapshot(snapshot)
    if errors:
        raise SnapshotValidationError(";".join(errors))

    destination = Path(target)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(destination.name + ".tmp")
    temporary.write_text(
        json.dumps(snapshot, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, destination)
    return destination
