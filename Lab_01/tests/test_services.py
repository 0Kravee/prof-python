"""Tests for car_catalog models and services."""

import pytest

from car_catalog import services
from car_catalog.exceptions import (
    CarCatalogError,
    CarNotFoundError,
    InvalidCarDataError,
)
from car_catalog.models import Car
from car_catalog.services import (
    CarCatalog,
    add_car,
    calculate_average_price,
    filter_by_year,
    find_lowest_mileage,
    find_most_expensive,
    get_statistics,
    remove_car,
    search_by_brand,
    search_cars,
    sort_by_mileage,
    sort_by_price,
    sort_by_year,
)


@pytest.fixture
def sample_cars() -> list[Car]:
    return [
        Car("Toyota", "Camry", 2019, 21500.0, 45000),
        Car("BMW", "X5", 2021, 48200.0, 18000),
        Car("Toyota", "Corolla", 2022, 19800.0, 9000),
    ]


def test_search_by_brand(sample_cars: list[Car]) -> None:
    result = search_by_brand(sample_cars, "toyota")
    assert len(result) == 2
    assert all(car.brand == "Toyota" for car in result)


def test_search_by_brand_not_found(sample_cars: list[Car]) -> None:
    assert search_by_brand(sample_cars, "Ford") == []


def test_filter_by_year(sample_cars: list[Car]) -> None:
    result = filter_by_year(sample_cars, 2021)
    assert [car.model for car in result] == ["X5"]


def test_find_most_expensive(sample_cars: list[Car]) -> None:
    best = find_most_expensive(sample_cars)
    assert best is not None and best.model == "X5"


def test_find_most_expensive_empty() -> None:
    assert find_most_expensive([]) is None


def test_calculate_average_price(sample_cars: list[Car]) -> None:
    expected = (21500.0 + 48200.0 + 19800.0) / 3
    assert calculate_average_price(sample_cars) == pytest.approx(expected)


def test_calculate_average_price_empty() -> None:
    assert calculate_average_price([]) == 0.0


def test_find_lowest_mileage(sample_cars: list[Car]) -> None:
    lowest = find_lowest_mileage(sample_cars)
    assert lowest is not None and lowest.model == "Corolla"
    assert find_lowest_mileage([]) is None


def test_sorting(sample_cars: list[Car]) -> None:
    prices = [car.price for car in sort_by_price(sample_cars)]
    assert prices == sorted(prices, reverse=True)
    years = [car.year for car in sort_by_year(sample_cars)]
    assert years == sorted(years, reverse=True)
    mileage = [car.mileage for car in sort_by_mileage(sample_cars)]
    assert mileage == sorted(mileage)


def test_multi_criteria_search(sample_cars: list[Car]) -> None:
    result = search_cars(sample_cars, "Toyota", min_year=2020)
    assert [car.model for car in result] == ["Corolla"]
    assert len(search_cars(sample_cars)) == 3
    assert search_cars(sample_cars, max_price=20000)[0].model == "Corolla"


def test_statistics(sample_cars: list[Car]) -> None:
    stats = get_statistics(sample_cars)
    assert stats["count"] == 3
    assert stats["max_price"] == 48200.0
    assert get_statistics([])["count"] == 0


def test_add_car_mutates_and_returns_list(sample_cars: list[Car]) -> None:
    new_car = Car("Skoda", "Octavia", 2023, 26500.0, 1200)
    result = add_car(sample_cars, new_car)
    assert result is sample_cars
    assert len(sample_cars) == 4 and sample_cars[-1] is new_car


def test_remove_car(sample_cars: list[Car]) -> None:
    removed = remove_car(sample_cars, "bmw", "x5")
    assert removed.brand == "BMW" and len(sample_cars) == 2
    with pytest.raises(CarNotFoundError):
        remove_car(sample_cars, "Ford", "Focus")


def test_invalid_data_raises_custom_and_value_error() -> None:
    with pytest.raises(InvalidCarDataError):
        Car("Test", "Model", 1800, 1000.0, 100)
    with pytest.raises(ValueError):
        Car("Test", "Model", 2020, -100.0, 100)
    with pytest.raises(CarCatalogError):
        Car("Test", "Model", 2020, 100.0, -1)
    with pytest.raises(InvalidCarDataError):
        Car("", "Model", 2020, 100.0, 1)


def test_car_properties() -> None:
    car = Car("Toyota", "Camry", 2019, 21500.0, 45000)
    assert car.full_name == car.name == "Toyota Camry"
    assert car.make == "Toyota"
    assert "Toyota Camry" in str(car)


def test_catalog_class(sample_cars: list[Car]) -> None:
    catalog = CarCatalog(sample_cars)
    catalog.add(Car("Audi", "A4", 2018, 23000.0, 62000))
    assert len(catalog) == 4
    assert catalog.most_expensive() is not None
    assert catalog.lowest_mileage() is not None
    assert len(catalog.search_by_brand("Audi")) == 1
    assert len(catalog.filter_by_year(2018)) == 1
    assert catalog.sorted_by_price()[0].model == "X5"
    assert catalog.average_price() > 0


def test_compatibility_aliases(sample_cars: list[Car]) -> None:
    assert services.find_by_brand(sample_cars, "BMW")
    assert services.get_cars_by_year(sample_cars, 2022)
    assert services.get_most_expensive_car(sample_cars).model == "X5"
    assert services.average_price(sample_cars) > 0
    assert services.find_min_mileage(sample_cars).model == "Corolla"
    assert services.Catalog is CarCatalog
