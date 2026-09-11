from __future__ import annotations

import math
import re
from pathlib import Path
from typing import Any

from peer_decisive_followups.production_contract import quadrature


class EvidenceError(RuntimeError):
    pass


def _finite(*values: float) -> None:
    if not all(math.isfinite(float(value)) for value in values):
        raise EvidenceError("evidence values and uncertainties must be finite")


def normalize_evidence(data_logz: float, data_sigma: float,
                       prior_logz: float, prior_sigma: float) -> dict[str, float | str]:
    _finite(data_logz, data_sigma, prior_logz, prior_sigma)
    if data_sigma < 0 or prior_sigma < 0:
        raise EvidenceError("evidence uncertainties must be non-negative")
    return {
        "status": "COMPLETE",
        "logZ": float(data_logz) - float(prior_logz),
        "logZstd": quadrature(float(data_sigma), float(prior_sigma)),
    }


def compare_models(m3: dict[str, Any], m1: dict[str, Any]) -> dict[str, float | str]:
    for name, result in (("M3", m3), ("M1", m1)):
        if result.get("status") != "COMPLETE":
            raise EvidenceError(f"{name} evidence is incomplete")
        if result.get("converged") is not True:
            raise EvidenceError(f"{name} evidence has not converged")
        _finite(result.get("logZ"), result.get("logZstd"))
        if float(result["logZstd"]) < 0:
            raise EvidenceError(f"{name} evidence uncertainty must be non-negative")
    delta = float(m3["logZ"]) - float(m1["logZ"])
    sigma = quadrature(float(m3["logZstd"]), float(m1["logZstd"]))
    return {
        "status": "COMPLETE",
        "delta_logZ_M3_minus_M1": delta,
        "delta_logZ_std": sigma,
    }


def parse_polychord_stats(path: Path) -> dict[str, float]:
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    patterns = [
        r"log\(Z\)\s*=\s*([-+0-9.eE]+)\s*\+/-\s*([-+0-9.eE]+)",
        r"logZ\s*[:=]\s*([-+0-9.eE]+)\s*(?:\+/-|\+\-)\s*([-+0-9.eE]+)",
    ]
    matches: list[tuple[float, float]] = []
    for pattern in patterns:
        for match in re.finditer(pattern, text, flags=re.I):
            try:
                matches.append((float(match.group(1)), float(match.group(2))))
            except ValueError:
                continue
    if not matches:
        raise EvidenceError(f"no PolyChord logZ/logZstd found in {path}")
    logz, sigma = matches[-1]
    _finite(logz, sigma)
    if sigma < 0:
        raise EvidenceError("PolyChord logZ uncertainty must be non-negative")
    return {"logZ": logz, "logZstd": sigma}
