"""Unit tests of validation against the configured ranges."""

import pytest

from car_catalog.config import AppConfig
from car_catalog.exceptions import InvalidCarDataError
from car_catalog.validators import is_valid_car, validate_car


def test_validate_car_returns_the_same_car(car_factory) -> None:
    car = car_factory()
    assert validate_car(car) is car


@pytest.mark.parametrize(
    ("year", "price", "ok"),
    [
        (2000, 10_000.0, True),      # lower year bound, lower price bound
        (2025, 50_000.0, True),      # upper bounds
        (1999, 10_000.0, False),     # year just below
        (2026, 10_000.0, False),     # year just above
        (2010, 9_999.99, False),     # price just below
        (2010, 50_000.01, False),    # price just above
    ],
)
def test_custom_range_boundaries(car_factory, year, price, ok) -> None:
    config = AppConfig(
        min_year=2000, max_year=2025, min_price=10_000.0, max_price=50_000.0
    )
    car = car_factory(year=year, price=price)
    assert is_valid_car(car, config) is ok


def test_out_of_range_year_raises_with_range_in_message(car_factory) -> None:
    config = AppConfig(min_year=2010, max_year=2020)
    with pytest.raises(InvalidCarDataError, match="2010..2020"):
        validate_car(car_factory(year=2005), config)


def test_out_of_range_price_raises(car_factory) -> None:
    config = AppConfig(max_price=1000.0)
    with pytest.raises(InvalidCarDataError, match="Price"):
        validate_car(car_factory(price=1000.5), config)
