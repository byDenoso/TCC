from __future__ import annotations

import math
from collections.abc import Iterable

import numpy as np


def reflect_unit_box(values: np.ndarray | Iterable[float]) -> np.ndarray:
    """Reflect arbitrary real coordinates into [0, 1] with period two."""
    array = np.asarray(values, dtype=float)
    folded = np.mod(array, 2.0)
    return np.where(folded <= 1.0, folded, 2.0 - folded)


def validate_temperatures(values: Iterable[float]) -> tuple[float, ...]:
    temperatures = tuple(float(value) for value in values)
    if len(temperatures) < 2:
        raise ValueError("At least two temperatures are required")
    if not math.isclose(temperatures[0], 1.0, rel_tol=0.0, abs_tol=1e-12):
        raise ValueError("The cold temperature must be exactly 1")
    if any(not math.isfinite(value) or value <= 0 for value in temperatures):
        raise ValueError("Temperatures must be positive and finite")
    if any(right <= left for left, right in zip(temperatures, temperatures[1:])):
        raise ValueError("Temperatures must be strictly increasing")
    return temperatures


def swap_log_alpha(beta_a: float, beta_b: float, loglike_a: float, loglike_b: float) -> float:
    """Log acceptance ratio for swapping states between inverse temperatures."""
    return float((beta_a - beta_b) * (loglike_b - loglike_a))


def pair_schedule(step: int, size: int) -> list[tuple[int, int]]:
    """Return alternating, disjoint adjacent swap pairs."""
    if size < 2:
        return []
    start = int(step) % 2
    return [(left, left + 1) for left in range(start, size - 1, 2)]


def metropolis_accept(log_alpha: float, uniform: float) -> bool:
    """Apply a Metropolis decision using a caller-supplied U(0,1) draw."""
    if not 0.0 < uniform < 1.0:
        raise ValueError("uniform must lie strictly inside (0, 1)")
    if math.isnan(log_alpha):
        return False
    return math.log(uniform) < min(0.0, float(log_alpha))
