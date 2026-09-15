from __future__ import annotations

"""Thin recovery shim around the frozen parallel-tempering implementation.

The production driver remains byte-identical in ``pt_driver_impl.py``. This shim
only classifies two proposal-local CAMB/Cobaya failures observed in the archived
ladder artifact as recoverable rejections. Unexpected programming and runtime
errors still propagate and fail the job.
"""

import pt_driver_impl as _impl


_ORIGINAL_IS_RECOVERABLE = _impl._is_recoverable_numerical_error


def _is_recoverable_numerical_error(exc: BaseException) -> bool:
    if _ORIGINAL_IS_RECOVERABLE(exc):
        return True
    exception_name = _impl._exception_name(exc)
    if exception_name != "cobaya.log.LoggedError":
        return False
    message = str(exc).lower()
    return any(
        marker in message
        for marker in (
            "no solution for h0 inside of theta_h0_range",
            "mismatch in integrated times",
        )
    )


_impl._is_recoverable_numerical_error = _is_recoverable_numerical_error

for _name in dir(_impl):
    if not _name.startswith("__"):
        globals().setdefault(_name, getattr(_impl, _name))


def __getattr__(name: str):
    return getattr(_impl, name)


if __name__ == "__main__":
    raise SystemExit(_impl.main())
