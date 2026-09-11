from __future__ import annotations

import hashlib
import json
import math
from copy import deepcopy
from typing import Any

MODELS = {"M1", "M3"}


def canonical_json(data: dict[str, Any]) -> bytes:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha256_json(data: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_json(data)).hexdigest()


def build_science_manifest(model: str, config: dict[str, Any]) -> dict[str, Any]:
    if model not in MODELS:
        raise ValueError(f"model must be one of {sorted(MODELS)}")
    manifest = {
        "schema": "peer-nested-science-v1",
        "model": model,
        "likelihood": deepcopy(config.get("likelihood", {})),
        "params": deepcopy(config.get("params", {})),
        "prior": deepcopy(config.get("prior", {})),
        "theory": deepcopy(config.get("theory", {})),
        "sampler": deepcopy(config.get("sampler", {})),
    }
    manifest["sha256"] = sha256_json(manifest)
    return manifest


def classify_lane(*, complete: bool, resumable: bool, fatal: bool) -> str:
    if fatal:
        return "FAILED"
    if complete:
        return "COMPLETE"
    if resumable:
        return "RESUMABLE"
    return "FAILED"


def quadrature(*sigmas: float) -> float:
    return math.sqrt(sum(float(s) ** 2 for s in sigmas))
