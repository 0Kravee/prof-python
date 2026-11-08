"""Integration: search, year filter, sorting, pagination, Lab_01 parity."""

import pytest

from car_catalog import services as lab01
from car_catalog.exceptions import InvalidQueryError

pytestmark = pytest.mark.integration


def models(cars) -> list[str]:
    return [car.model for car in cars]


@pytest.mark.parametrize(
    ("brand", "expected"),
    [
        ("toyota", ["Corolla", "Camry"]),
        (" BMW ", ["X5", "3 Series"]),
        ("Audi", ["A4"]),
        ("Tesla", []),
    ],
)
def test_search_by_brand_uses_the_manufacturer_relationship(
    seeded, brand, expected
) -> None:
    assert models(seeded.find_by_brand(brand)) == expected


def test_find_by_model_ignores_case(seeded) -> None:
    assert models(seeded.cars.find_by_model("X5")) == ["X5"]
    assert models(seeded.cars.find_by_model("3 SERIES")) == ["3 Series"]


@pytest.mark.parametrize(
    ("year", "expected"),
    [(2022, ["Corolla"]), (2021, ["X5"]), (2018, ["A4"]), (1999, [])],
)
def test_filter_by_year(seeded, year, expected) -> None:
    assert models(seeded.filter_by_year(year)) == expected


@pytest.mark.parametrize(
    ("criteria", "expected"),
    [
        ({}, 5),
        ({"brand": "bmw"}, 2),
        ({"min_year": 2020}, 3),
        ({"max_year": 2019}, 2),
        ({"min_price": 30000}, 2),
        ({"max_price": 21500}, 2),
        ({"max_mileage": 18000}, 2),
        ({"brand": "bmw", "min_year": 2021}, 1),
        ({"brand": "toyota", "max_price": 20000, "max_mileage": 10000}, 1),
        ({"brand": "audi", "min_year": 2022}, 0),
        ({"model": "camry", "brand": "toyota"}, 1),
    ],
)
def test_search_by_several_criteria(seeded, criteria, expected) -> None:
    assert len(seeded.cars.search(**criteria)) == expected


def test_sorting_in_both_directions(seeded) -> None:
    cheapest_first = seeded.cars.search(sort_by="price")
    assert models(cheapest_first)[0] == "Corolla"
    dearest_first = seeded.cars.search(sort_by="price", descending=True)
    assert models(dearest_first)[0] == "X5"
    assert models(seeded.cars.search(sort_by="year", descending=True))[0] == (
        "Corolla"
    )


def test_pagination_pages_do_not_overlap(seeded) -> None:
    first = seeded.cars.search(sort_by="price", limit=2)
    second = seeded.cars.search(sort_by="price", limit=2, offset=2)
    third = seeded.cars.search(sort_by="price", limit=2, offset=4)
    assert (len(first), len(second), len(third)) == (2, 2, 1)
    all_ids = [c.id for c in first + second + third]
    assert len(set(all_ids)) == 5


def test_offset_beyond_the_end_gives_empty_page(seeded) -> None:
    assert seeded.cars.search(offset=100, limit=10) == []


@pytest.mark.parametrize(
    "kwargs",
    [
        {"sort_by": "color"},
        {"sort_by": "price; DROP TABLE cars"},
        {"offset": -1},
        {"limit": -1},
    ],
)
def test_invalid_search_parameters(seeded, kwargs) -> None:
    with pytest.raises(InvalidQueryError):
        seeded.cars.search(**kwargs)


def test_sort_field_injection_did_not_touch_the_table(seeded) -> None:
    with pytest.raises(InvalidQueryError):
        seeded.cars.search(sort_by="price; DROP TABLE cars")
    assert seeded.cars.count() == 5


def test_sql_results_match_the_lab01_functions(seeded) -> None:
    """The database gives the same answers as the old in-memory code."""
    cars = seeded.domain_cars()
    assert seeded.average_price() == pytest.approx(
        lab01.calculate_average_price(cars)
    )
    assert seeded.most_expensive().to_domain() == (
        lab01.find_most_expensive(cars)
    )
    assert seeded.lowest_mileage().to_domain() == (
        lab01.find_lowest_mileage(cars)
    )
    assert [c.to_domain() for c in seeded.find_by_brand("bmw")] == (
        lab01.search_by_brand(cars, "bmw")
    )
    assert [c.to_domain() for c in seeded.filter_by_year(2020)] == (
        lab01.filter_by_year(cars, 2020)
    )
