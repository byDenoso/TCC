from __future__ import annotations

import importlib.util
import site
import sys
from pathlib import Path
from typing import Any

_real = None
for base in [*site.getsitepackages(), site.getusersitepackages()]:
    init = Path(base) / "yaml" / "__init__.py"
    if init.exists():
        spec = importlib.util.spec_from_file_location(
            "_peer_pyyaml_real",
            init,
            submodule_search_locations=[str(init.parent)],
        )
        if spec and spec.loader:
            module = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = module
            spec.loader.exec_module(module)
            _real = module
            break
if _real is None:
    raise ImportError("Could not locate the installed PyYAML package")


def _clean(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _clean(v) for k, v in value.items() if k != "checkpoint_every"}
    if isinstance(value, list):
        return [_clean(v) for v in value]
    if isinstance(value, tuple):
        return tuple(_clean(v) for v in value)
    return value


def safe_dump(data: Any, *args: Any, **kwargs: Any) -> str:
    return _real.safe_dump(_clean(data), *args, **kwargs)


def safe_load(stream: Any) -> Any:
    return _real.safe_load(stream)


def __getattr__(name: str) -> Any:
    return getattr(_real, name)
