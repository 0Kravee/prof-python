"""Unit tests of the Car data model."""

import math

import pytest

from car_catalog.config import MAX_YEAR, MIN_YEAR
from car_catalog.exceptions import CarCatalogError, InvalidCarDataError


def test_car_stores_all_fields(car_factory) -> None:
    car = car_factory()
    assert (car.brand, car.model) == ("Toyota", "Camry")
    assert (car.year, car.price, car.mileage) == (2019, 21500.0, 45000)


def test_full_name_and_aliases(car_factory) -> None:
    car = car_factory()
    assert car.full_name == "Toyota Camry"
    assert car.name == car.full_name
    assert car.make == "Toyota"


def test_str_contains_price_with_two_decimals(car_factory) -> None:
    text = str(car_factory(price=19999.5))
    assert "19999.50 USD" in text
    assert "45000 km" in text


@pytest.mark.parametrize(
    ("year", "price", "mileage"),
    [
        (MIN_YEAR, 0.0, 0),
        (MAX_YEAR, 0.0, 0),
        (2020, 0.01, 1),
    ],
    ids=["min-year", "max-year", "smallest-positive"],
)
def test_boundary_values_are_accepted(
    car_factory, year, price, mileage
) -> None:
    car = car_factory(year=year, price=price, mileage=mileage)
    assert car.year == year


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("brand", "", "Brand and model"),
        ("brand", "   ", "Brand and model"),
        ("model", "", "Brand and model"),
        ("year", MIN_YEAR - 1, "Year must be between"),
        ("year", MAX_YEAR + 1, "Year must be between"),
        ("price", -0.01, "Price cannot be negative"),
        ("mileage", -1, "Mileage cannot be negative"),
    ],
)
def test_invalid_values_raise_custom_exception(
    car_factory, field, value, message
) -> None:
    with pytest.raises(InvalidCarDataError, match=message):
        car_factory(**{field: value})


def test_invalid_data_error_is_also_a_value_error(car_factory) -> None:
    with pytest.raises(ValueError):
        car_factory(year=1)
    assert issubclass(InvalidCarDataError, CarCatalogError)


def test_error_message_names_the_allowed_range(car_factory) -> None:
    with pytest.raises(InvalidCarDataError) as excinfo:
        car_factory(year=1800)
    assert str(MIN_YEAR) in str(excinfo.value)
    assert str(MAX_YEAR) in str(excinfo.value)


# --- tests written to look for real defects (see the report) ----------


@pytest.mark.parametrize("bad_price", [math.nan, math.inf, -math.inf])
def test_non_finite_price_is_rejected(car_factory, bad_price) -> None:
    with pytest.raises(InvalidCarDataError):
        car_factory(price=bad_price)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("year", "2020"),
        ("year", 2020.5),
        ("mileage", 1.5),
        ("mileage", "100"),
        ("price", "100"),
        ("brand", None),
        ("model", 42),
    ],
)
def test_wrong_type_raises_custom_error_not_type_error(
    car_factory, field, value
) -> None:
    with pytest.raises(InvalidCarDataError):
        car_factory(**{field: value})


def test_surrounding_spaces_are_removed_from_brand_and_model(
    car_factory,
) -> None:
    car = car_factory(brand="  BMW ", model=" X5  ")
    assert (car.brand, car.model) == ("BMW", "X5")
