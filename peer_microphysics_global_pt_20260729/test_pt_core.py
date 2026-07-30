import numpy as np
import pytest

from pt_core import (
    metropolis_accept,
    pair_schedule,
    reflect_unit_box,
    swap_log_alpha,
    validate_temperatures,
)


def test_reflection_preserves_unit_box_and_symmetry():
    x = np.array([-0.2, 0.2, 1.3, 2.2])
    assert np.allclose(reflect_unit_box(x), [0.2, 0.2, 0.7, 0.2])


def test_temperature_ladder_starts_at_one_and_is_strictly_increasing():
    assert validate_temperatures([1, 1.5, 2.5]) == (1.0, 1.5, 2.5)
    with pytest.raises(ValueError):
        validate_temperatures([1, 1, 2])
    with pytest.raises(ValueError):
        validate_temperatures([1.2, 2])


def test_swap_ratio_uses_likelihood_only():
    assert swap_log_alpha(1.0, 0.5, -10.0, -8.0) == pytest.approx(1.0)


def test_pair_schedule_alternates_disjoint_edges():
    assert pair_schedule(0, 6) == [(0, 1), (2, 3), (4, 5)]
    assert pair_schedule(1, 6) == [(1, 2), (3, 4)]


def test_metropolis_accept_is_deterministic_for_supplied_uniform():
    assert metropolis_accept(-1.0, 0.2)
    assert not metropolis_accept(-1.0, 0.9)
