"""Unit tests of the analytics: Python (baseline) versus NumPy."""

import time

import numpy as np
import pytest

from car_catalog import analytics as an
from car_catalog.datagen import generate_cars
from car_catalog.models import Car


@pytest.fixture(scope="module")
def cars() -> list[Car]:
    return generate_cars(3000, seed=11)


@pytest.fixture(scope="module")
def columns(cars: list[Car]) -> an.CarColumns:
    return an.to_columns(cars)


def reference_value(year: int, price: float, mileage: int) -> float:
    """Independent closed-form formula for estimated_value."""
    months = max(an.CURRENT_YEAR - year, 0) * 12
    factor = max(0.5, 1.0 - mileage * 1e-6)
    return price * (1.0 - 0.12 / 12) ** months * factor


# --- estimated_value ---------------------------------------------------


def test_new_car_keeps_its_price_apart_from_mileage() -> None:
    assert an.estimated_value(an.CURRENT_YEAR, 10_000.0, 0) == 10_000.0


def test_value_decreases_with_age() -> None:
    newer = an.estimated_value(2024, 20_000.0, 10_000)
    older = an.estimated_value(2014, 20_000.0, 10_000)
    assert older < newer < 20_000.0


@pytest.mark.parametrize(
    ("year", "price", "mileage"),
    [
        (2026, 100.0, 0),
        (2020, 25_000.0, 80_000),
        (2000, 3_000.0, 500_000),
        (2010, 12_345.67, 2_000_000),
    ],
)
def test_loop_matches_the_closed_formula(year, price, mileage) -> None:
    assert an.estimated_value(year, price, mileage) == pytest.approx(
        reference_value(year, price, mileage), rel=1e-12
    )


def test_future_year_has_no_depreciation() -> None:
    assert an.estimated_value(2030, 10_000.0, 0) == 10_000.0


def test_high_mileage_discount_is_limited() -> None:
    low = an.estimated_value(2026, 10_000.0, 5_000_000)
    assert low == pytest.approx(5_000.0)  # never below half of the price


# --- manufacturer statistics ---------------------------------------


def test_manufacturer_statistics_of_a_tiny_catalog(car_factory) -> None:
    cars = [
        car_factory(brand="BMW", year=2026, price=100.0, mileage=10),
        car_factory(brand="BMW", year=2026, price=300.0, mileage=30),
        car_factory(brand="Audi", year=2026, price=50.0, mileage=0),
    ]
    stats = an.manufacturer_statistics_python(cars)
    assert list(stats) == ["Audi", "BMW"]  # sorted
    bmw = stats["BMW"]
    assert bmw.count == 2
    assert bmw.average_price == pytest.approx(200.0)
    assert bmw.average_mileage == pytest.approx(20.0)
    assert bmw.total_value == pytest.approx(
        100.0 * (1 - 10e-6) + 300.0 * (1 - 30e-6)
    )


def test_empty_catalog_has_no_statistics() -> None:
    assert an.manufacturer_statistics_python([]) == {}
    assert an.manufacturer_statistics_numpy(an.to_columns([])) == {}


def test_numpy_manufacturer_statistics_match_python(cars, columns) -> None:
    python = an.manufacturer_statistics_python(cars)
    numpy_result = an.manufacturer_statistics_numpy(columns)
    assert an.statistics_close(python, numpy_result)


def test_partial_results_can_be_merged(cars) -> None:
    half = len(cars) // 2
    merged = an.merge_partials(
        [
            an.partial_manufacturer_statistics(cars[:half]),
            an.partial_manufacturer_statistics(cars[half:]),
        ]
    )
    whole = an.manufacturer_statistics_python(cars)
    assert an.statistics_close(an.finalize_statistics(merged), whole)


def test_statistics_close_detects_differences(cars) -> None:
    stats = an.manufacturer_statistics_python(cars)
    brand = next(iter(stats))
    changed = dict(stats)
    original = stats[brand]
    changed[brand] = an.BrandStats(
        brand,
        original.count,
        original.average_price * 1.001,
        original.average_mileage,
        original.total_value,
    )
    assert not an.statistics_close(stats, changed)
    wrong_count = dict(stats)
    wrong_count[brand] = an.BrandStats(
        brand,
        original.count + 1,
        original.average_price,
        original.average_mileage,
        original.total_value,
    )
    assert not an.statistics_close(stats, wrong_count)
    missing = {k: v for k, v in stats.items() if k != brand}
    assert not an.statistics_close(stats, missing)


def test_statistics_close_accepts_rounding_noise(cars) -> None:
    stats = an.manufacturer_statistics_python(cars)
    brand = next(iter(stats))
    value = stats[brand]
    noisy = dict(stats)
    noisy[brand] = an.BrandStats(
        brand,
        value.count,
        value.average_price * (1 + 1e-13),
        value.average_mileage,
        value.total_value,
    )
    assert an.statistics_close(stats, noisy)


# --- mileage statistics -----------------------------------------------


def test_mileage_statistics_of_known_values(car_factory) -> None:
    cars = [car_factory(mileage=m) for m in (10, 20, 30, 40)]
    stats = an.mileage_statistics_python(cars)
    assert (stats.count, stats.minimum, stats.maximum) == (4, 10, 40)
    assert stats.mean == pytest.approx(25.0)
    assert stats.std == pytest.approx(np.std([10, 20, 30, 40]))


def test_numpy_mileage_statistics_match_python(cars, columns) -> None:
    python = an.mileage_statistics_python(cars)
    numpy_result = an.mileage_statistics_numpy(columns)
    assert numpy_result.count == python.count
    assert numpy_result.minimum == python.minimum
    assert numpy_result.maximum == python.maximum
    assert numpy_result.mean == pytest.approx(python.mean)
    assert numpy_result.std == pytest.approx(python.std)


def test_mileage_statistics_of_empty_catalog() -> None:
    empty = an.MileageStats(0, 0, 0, 0.0, 0.0)
    assert an.mileage_statistics_python([]) == empty
    assert an.mileage_statistics_numpy(an.to_columns([])) == empty


# --- the simple Lab_01 operations --------------------------------------


def test_average_price_numpy_matches_python(cars, columns) -> None:
    assert an.average_price_numpy(columns) == pytest.approx(
        an.average_price_python(cars)
    )


def test_average_price_of_empty_catalog() -> None:
    assert an.average_price_numpy(an.to_columns([])) == 0.0


def test_most_expensive_numpy_finds_the_same_car(cars, columns) -> None:
    index = an.most_expensive_index_numpy(columns)
    assert index is not None
    expected = an.most_expensive_python(cars)
    assert expected is not None
    assert cars[index].price == expected.price


def test_most_expensive_of_empty_catalog() -> None:
    assert an.most_expensive_index_numpy(an.to_columns([])) is None


@pytest.mark.parametrize("year", [2000, 2013, 2020, 2026, 1999])
def test_filter_by_year_numpy_matches_python(cars, columns, year) -> None:
    expected = an.filter_by_year_python(cars, year)
    indexes = an.filter_by_year_numpy(columns, year)
    assert [cars[i] for i in indexes] == expected


@pytest.mark.parametrize("brand", ["BMW", "bmw", " Audi ", "Tesla"])
def test_search_by_brand_numpy_matches_python(cars, columns, brand) -> None:
    expected = an.search_by_brand_python(cars, brand)
    indexes = an.search_by_brand_numpy(columns, brand)
    assert [cars[i] for i in indexes] == expected


# --- conversion and speed ------------------------------------------------


def test_columns_have_one_value_per_car(cars, columns) -> None:
    assert len(columns) == len(cars)
    assert columns.prices.dtype == np.float64
    assert columns.brand_names == tuple(sorted({c.brand for c in cars}))


def test_numpy_is_much_faster_than_the_python_loop() -> None:
    cars = generate_cars(20_000, seed=3)
    columns = an.to_columns(cars)
    started = time.perf_counter()
    an.manufacturer_statistics_python(cars)
    python_time = time.perf_counter() - started
    started = time.perf_counter()
    an.manufacturer_statistics_numpy(columns)
    numpy_time = time.perf_counter() - started
    assert numpy_time < python_time / 5  # a huge margin: no flakiness
