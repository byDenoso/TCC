"""Per-cosmology calibration contract, tested only with an analytic mock backend.

No trajectory, transfer function or spectrum is transported between cosmologies.
Numerical limits below are review settings, not validated scientific priors.
"""
from dataclasses import dataclass
from typing import Callable
import math

import numpy as np
from scipy.interpolate import CubicSpline
from scipy.optimize import least_squares, minimize_scalar


@dataclass(frozen=True)
class Target:
    fede: float
    theta_s_100: float
    log10_zc: float = 3.81
    theta_i: float = 2.89155
    eta: float = 0.1

    def __post_init__(self):
        if not all(math.isfinite(v) for v in self.__dict__.values()):
            raise ValueError('Non-finite target')
        if not 0 < self.fede <= 0.18:
            raise ValueError('Calibration requires 0 < fEDE <= 0.18; fEDE=0 is exact LCDM')
        if self.theta_s_100 <= 0:
            raise ValueError('theta_s_100 must be positive')


@dataclass(frozen=True)
class Summary:
    fede: float
    zc: float
    theta_s_100: float
    H0_effective: float | None = None
    scalar_fraction_today: float | None = None
    closure_fraction: float | None = None


@dataclass(frozen=True)
class Calibration:
    amplitude: float
    decay_constant: float
    H0: float
    summary: Summary
    residuals_in_tolerance_units: tuple[float, float, float]
    backend_calls: int


class CalibrationError(RuntimeError):
    """Stop and diagnose; do not silently turn solver failure into a physical prior."""


def scalar_peak(background: dict) -> tuple[float, float]:
    """Global peak on sampled history plus local continuous interpolation.

    The final physical gate must repeat this on a denser CLASS background grid.
    Boundary maxima and non-finite/negative histories are not valid solutions.
    """
    z = np.asarray(background['z'], dtype=float)
    rho = np.asarray(background['(.)rho_scf'], dtype=float)
    total = np.asarray(background['(.)rho_tot'], dtype=float)
    if not (z.shape == rho.shape == total.shape and z.ndim == 1 and len(z) >= 5):
        raise CalibrationError('Malformed CLASS background arrays')
    if not all(np.isfinite(a).all() for a in (z, rho, total)):
        raise CalibrationError('Non-finite background')
    if np.any(z < 0) or np.any(total <= 0) or np.any(rho < 0):
        raise CalibrationError('Unphysical background')
    x = -np.log1p(z)
    order = np.argsort(x)
    x, frac = x[order], (rho / total)[order]
    if np.any(np.diff(x) <= 0):
        raise CalibrationError('Non-unique background times')
    j = int(np.argmax(frac))
    if j < 2 or j > len(x) - 3:
        raise CalibrationError('Global peak touches background boundary')
    spline = CubicSpline(x[j-2:j+3], frac[j-2:j+3])
    result = minimize_scalar(lambda a: -float(spline(a)), bounds=(x[j-1], x[j+1]),
                             method='bounded', options={'xatol': 1e-11})
    if not result.success:
        raise CalibrationError('Peak interpolation failed')
    return float(-result.fun), float(np.expm1(-result.x))


def calibrate(target: Target, probe: Callable[[float, float, float], Summary],
              *, seed=None,
              max_nfev=80) -> Calibration:
    """Solve log(A), log(F), log(H0) against f_peak, z_peak and exact theta_s.

    probe MUST close over the full proposed cosmology and the same precision/
    neutrino/recombination settings used by the final CLASS spectrum calculation.
    A,F are deterministic coordinates, with no extra independent prior/Jacobian.
    """
    if seed is None:
        # A deterministic initial guess only, never a transported solution.
        # At fixed onset redshift A/F^2 is approximately fixed, fEDE~F^2.
        # The subsequent solve and final gate determine the accepted trajectory.
        scale = target.fede / .08991341424357711
        seed = (747.4451502175409*scale, .12672536270923074*math.sqrt(scale),
                68.20874306622639)
    calls = 0
    def residual(log_values):
        nonlocal calls
        values = np.exp(log_values)
        result = probe(*map(float, values))
        calls += 1
        if not all(math.isfinite(v) and v > 0 for v in (result.fede,result.zc,result.theta_s_100)):
            raise CalibrationError('Invalid calibration observables')
        return np.array([
            math.log(result.fede / target.fede) / 5e-4,
            (math.log10(result.zc) - target.log10_zc) / 5e-4,
            (result.theta_s_100 - target.theta_s_100) / 1e-5,
        ])
    # Broad numerical safeguard box; hitting it is a calibration error, not a
    # licence to report an excluded region. Expand/review before production.
    bounds = np.log([[1e-12, 1e-8, 20.0], [1e12, 10.0, 150.0]])
    result = least_squares(residual, np.log(seed), bounds=bounds,
                           diff_step=1e-3, max_nfev=max_nfev,
                           ftol=1e-9, xtol=1e-9, gtol=1e-9)
    final_residual = residual(result.x)
    if (not result.success or np.max(np.abs(final_residual)) > 1 or
            np.any(result.active_mask)):
        raise CalibrationError(f'Calibration failed: {result.message}; residual={final_residual}')
    A, F, H0 = map(float, np.exp(result.x))
    summary = probe(A, F, H0)
    calls += 1
    return Calibration(A, F, H0, summary, tuple(map(float, final_residual)), calls)
