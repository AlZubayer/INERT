"""Mathematical checks for the offline viability memo calculations."""

import pytest

from inert.viability_audit import median_bounds


def test_median_bounds_are_sharp_for_four_unknown_positive_calls() -> None:
    observed = [10.0, 20.0, 30.0, 40.0, 50.0, 60.0]
    lower, upper = median_bounds(observed, 10)
    assert lower == 15.0
    assert upper == 55.0


def test_median_bounds_require_majority_and_even_target() -> None:
    with pytest.raises(ValueError):
        median_bounds([1.0, 2.0, 3.0, 4.0, 5.0], 10)
    with pytest.raises(ValueError):
        median_bounds([1.0, 2.0, 3.0], 5)
