"""Tests for car_catalog.services."""

import pytest

from car_catalog.models import Car
from car_catalog.services import (
    calculate_average_price,
    filter_by_year,
    find_lowest_mileage,
    find_most_expensive,
    search_by_brand,
    sort_by_price,
)


@pytest.fixture
def sample_cars() -> list[Car]:
    return [
        Car(brand="Toyota", model="Camry", year=2019, price=21500.0, mileage=45000),
        Car(brand="BMW", model="X5", year=2021, price=48200.0, mileage=18000),
        Car(brand="Toyota", model="Corolla", year=2022, price=19800.0, mileage=9000),
    ]


def test_search_by_brand(sample_cars: list[Car]) -> None:
    result = search_by_brand(sample_cars, "Toyota")
    assert len(result) == 2
    assert all(car.brand == "Toyota" for car in result)


def test_filter_by_year(sample_cars: list[Car]) -> None:
    result = filter_by_year(sample_cars, 2021)
    assert len(result) == 1
    assert result[0].model == "X5"


def test_find_most_expensive(sample_cars: list[Car]) -> None:
    best = find_most_expensive(sample_cars)
    assert best is not None
    assert best.model == "X5"


def test_calculate_average_price(sample_cars: list[Car]) -> None:
    average = calculate_average_price(sample_cars)
    assert average == pytest.approx((21500.0 + 48200.0 + 19800.0) / 3)


def test_find_lowest_mileage(sample_cars: list[Car]) -> None:
    lowest = find_lowest_mileage(sample_cars)
    assert lowest is not None
    assert lowest.model == "Corolla"


def test_sort_by_price(sample_cars: list[Car]) -> None:
    sorted_cars = sort_by_price(sample_cars)
    prices = [car.price for car in sorted_cars]
    assert prices == sorted(prices, reverse=True)


def test_invalid_year_raises() -> None:
    with pytest.raises(ValueError):
        Car(brand="Test", model="Model", year=1800, price=1000.0, mileage=100)


def test_negative_price_raises() -> None:
    with pytest.raises(ValueError):
        Car(brand="Test", model="Model", year=2020, price=-100.0, mileage=100)
