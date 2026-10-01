"""Tests for data_processor.processors and data_processor.analytics."""

import pytest

from data_processor.analytics import (
    calculate_average_values,
    create_car_record,
    create_year_filter,
    find_linear,
    find_lowest_mileage,
    find_most_expensive,
    sort_by_price,
)
from data_processor.processors import (
    count_cars_by_brand,
    create_car_index,
    filter_by_year,
    get_unique_brand_model_pairs,
    get_unique_brands,
    group_by_brand,
)


@pytest.fixture
def sample_cars() -> list[dict]:
    return [
        {"id": 1, "brand": "Toyota", "model": "Camry", "year": 2019, "price": 21500.0, "mileage": 45000},
        {"id": 2, "brand": "BMW", "model": "X5", "year": 2021, "price": 48200.0, "mileage": 18000},
        {"id": 3, "brand": "Toyota", "model": "Corolla", "year": 2022, "price": 19800.0, "mileage": 9000},
    ]


def test_get_unique_brands(sample_cars: list[dict]) -> None:
    assert get_unique_brands(sample_cars) == {"Toyota", "BMW"}


def test_get_unique_brand_model_pairs(sample_cars: list[dict]) -> None:
    pairs = get_unique_brand_model_pairs(sample_cars)
    assert ("Toyota", "Camry") in pairs
    assert len(pairs) == 3


def test_create_car_index(sample_cars: list[dict]) -> None:
    index = create_car_index(sample_cars)
    assert index[2]["brand"] == "BMW"


def test_filter_by_year(sample_cars: list[dict]) -> None:
    result = filter_by_year(sample_cars, 2021)
    assert len(result) == 1
    assert result[0]["model"] == "X5"


def test_group_by_brand(sample_cars: list[dict]) -> None:
    grouped = group_by_brand(sample_cars)
    assert len(grouped["Toyota"]) == 2


def test_count_cars_by_brand(sample_cars: list[dict]) -> None:
    counter = count_cars_by_brand(sample_cars)
    assert counter["Toyota"] == 2


def test_find_most_expensive(sample_cars: list[dict]) -> None:
    best = find_most_expensive(sample_cars)
    assert best is not None
    assert best["model"] == "X5"


def test_find_lowest_mileage(sample_cars: list[dict]) -> None:
    lowest = find_lowest_mileage(sample_cars)
    assert lowest is not None
    assert lowest["model"] == "Corolla"


def test_sort_by_price(sample_cars: list[dict]) -> None:
    sorted_cars = sort_by_price(sample_cars)
    prices = [car["price"] for car in sorted_cars]
    assert prices == sorted(prices, reverse=True)


def test_calculate_average_values() -> None:
    assert calculate_average_values(10, 20, 30) == pytest.approx(20.0)


def test_create_car_record() -> None:
    record = create_car_record(id=9, brand="Skoda", model="Octavia", year=2023, price=26500.0, mileage=1200)
    assert record["brand"] == "Skoda"


def test_create_year_filter(sample_cars: list[dict]) -> None:
    is_recent = create_year_filter(2021)
    recent = [car for car in sample_cars if is_recent(car)]
    assert len(recent) == 2


def test_find_linear(sample_cars: list[dict]) -> None:
    found = find_linear(sample_cars, 3)
    assert found is not None
    assert found["model"] == "Corolla"
    assert find_linear(sample_cars, 999) is None
