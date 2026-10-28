"""Unit tests of the functional business logic."""

import pytest

from car_catalog.exceptions import CarNotFoundError
from car_catalog.services import (
    CarCatalog,
    add_car,
    calculate_average_price,
    create_car,
    filter_by_year,
    find_lowest_mileage,
    find_most_expensive,
    get_statistics,
    remove_car,
    search_by_brand,
    search_by_model,
    search_cars,
    sort_by_mileage,
    sort_by_price,
    sort_by_year,
)


def test_add_car_changes_list_in_place_and_returns_it(car_factory) -> None:
    cars: list = []
    result = add_car(cars, car_factory())
    assert result is cars
    assert len(cars) == 1


def test_create_car_returns_validated_car() -> None:
    car = create_car("Kia", "Rio", 2020, 9000.0, 1000)
    assert car.full_name == "Kia Rio"


def test_remove_car_is_case_insensitive(sample_cars) -> None:
    removed = remove_car(sample_cars, "bmw", "x5")
    assert removed.full_name == "BMW X5"
    assert len(sample_cars) == 4


def test_removing_the_same_car_twice_fails_the_second_time(
    sample_cars,
) -> None:
    remove_car(sample_cars, "Audi", "A4")
    with pytest.raises(CarNotFoundError, match="Audi A4"):
        remove_car(sample_cars, "Audi", "A4")


@pytest.mark.parametrize(
    ("query", "expected"),
    [("toyota", 2), ("BMW", 2), (" audi ", 1), ("Tesla", 0), ("", 0)],
)
def test_search_by_brand(sample_cars, query, expected) -> None:
    assert len(search_by_brand(sample_cars, query)) == expected


@pytest.mark.parametrize(
    ("query", "expected"),
    [("camry", 1), ("X5", 1), ("3 series", 1), ("Golf", 0)],
)
def test_search_by_model(sample_cars, query, expected) -> None:
    assert len(search_by_model(sample_cars, query)) == expected


def test_search_by_brand_finds_cars_with_padded_names(car_factory) -> None:
    cars = [car_factory(brand=" BMW ", model="X5")]
    assert len(search_by_brand(cars, "bmw")) == 1


def test_filter_by_year_returns_only_that_year(sample_cars) -> None:
    result = filter_by_year(sample_cars, 2021)
    assert [car.model for car in result] == ["X5"]


def test_filter_by_year_without_matches_is_empty(sample_cars) -> None:
    assert filter_by_year(sample_cars, 1999) == []


def test_most_expensive_car(sample_cars) -> None:
    car = find_most_expensive(sample_cars)
    assert car is not None
    assert car.full_name == "BMW X5"


def test_most_expensive_of_empty_catalog_is_none() -> None:
    assert find_most_expensive([]) is None


def test_average_price_uses_approx_for_floats(car_factory) -> None:
    cars = [car_factory(price=0.1), car_factory(price=0.2)]
    assert calculate_average_price(cars) == pytest.approx(0.15)


def test_average_price_of_sample_catalog(sample_cars) -> None:
    assert calculate_average_price(sample_cars) == pytest.approx(28700.0)


def test_average_price_of_empty_catalog_is_zero() -> None:
    assert calculate_average_price([]) == 0.0


def test_lowest_mileage(sample_cars) -> None:
    car = find_lowest_mileage(sample_cars)
    assert car is not None
    assert car.mileage == 9000


def test_lowest_mileage_of_empty_catalog_is_none() -> None:
    assert find_lowest_mileage([]) is None


def test_equal_prices_return_the_first_car(car_factory) -> None:
    first = car_factory(brand="A", price=100.0)
    second = car_factory(brand="B", price=100.0)
    assert find_most_expensive([first, second]) is first


def test_sorting_functions(sample_cars) -> None:
    assert sort_by_price(sample_cars)[0].price == 48200.0
    assert sort_by_price(sample_cars, descending=False)[0].price == 19800.0
    assert sort_by_year(sample_cars)[0].year == 2022
    assert sort_by_mileage(sample_cars)[0].mileage == 9000
    assert sort_by_mileage(sample_cars, descending=True)[0].mileage == 62000


@pytest.mark.parametrize(
    ("criteria", "expected"),
    [
        ({}, 5),
        ({"brand": "bmw"}, 2),
        ({"min_year": 2020}, 3),
        ({"max_price": 21500}, 2),
        ({"max_mileage": 18000}, 2),
        ({"brand": "bmw", "min_year": 2021}, 1),
        ({"brand": "toyota", "max_price": 20000, "max_mileage": 10000}, 1),
        ({"brand": "audi", "min_year": 2022}, 0),
    ],
)
def test_search_cars_by_several_criteria(
    sample_cars, criteria, expected
) -> None:
    assert len(search_cars(sample_cars, **criteria)) == expected


def test_statistics_of_catalog(sample_cars) -> None:
    stats = get_statistics(sample_cars)
    assert stats["count"] == 5
    assert stats["min_price"] == 19800.0
    assert stats["max_price"] == 48200.0
    assert stats["average_mileage"] == pytest.approx(32200.0)


def test_statistics_of_empty_catalog_are_zero() -> None:
    assert get_statistics([]) == {
        "count": 0,
        "average_price": 0.0,
        "min_price": 0.0,
        "max_price": 0.0,
        "average_mileage": 0.0,
    }


def test_car_catalog_facade_delegates_to_functions(sample_cars) -> None:
    catalog = CarCatalog(sample_cars)
    assert len(catalog) == 5
    assert catalog.search_by_brand("audi")[0].model == "A4"
    assert catalog.filter_by_year(2018)[0].brand == "Audi"
    assert catalog.most_expensive() is not None
    assert catalog.average_price() == pytest.approx(28700.0)
    assert catalog.lowest_mileage() is not None
    assert catalog.sorted_by_price()[0].price == 48200.0


def test_car_catalog_add_and_empty_start(car_factory) -> None:
    catalog = CarCatalog()
    assert len(catalog) == 0
    catalog.add(car_factory())
    assert len(catalog) == 1
