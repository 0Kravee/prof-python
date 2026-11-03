"""Unit tests of the test-data generator."""

from pathlib import Path

import pytest

from car_catalog.datagen import (
    BRANDS,
    LAST_YEAR,
    generate_cars,
    generate_csv_files,
    write_catalog_csv,
)
from car_catalog.importers import import_cars_csv


def test_requested_number_of_cars_is_generated() -> None:
    assert len(generate_cars(1234)) == 1234


def test_empty_catalog_is_allowed() -> None:
    assert generate_cars(0) == []


def test_negative_count_is_rejected() -> None:
    with pytest.raises(ValueError):
        generate_cars(-1)


def test_same_seed_gives_the_same_catalog() -> None:
    assert generate_cars(500, seed=7) == generate_cars(500, seed=7)


def test_different_seed_gives_a_different_catalog() -> None:
    assert generate_cars(500, seed=1) != generate_cars(500, seed=2)


def test_generated_cars_are_valid_and_realistic() -> None:
    cars = generate_cars(3000)
    assert {car.brand for car in cars} <= set(BRANDS)
    assert all(car.year <= LAST_YEAR for car in cars)
    assert all(car.price >= 500.0 for car in cars)
    assert all(car.mileage >= 0 for car in cars)
    assert len({car.brand for car in cars}) == len(BRANDS)  # every brand


def test_csv_roundtrip_keeps_every_car(tmp_path: Path) -> None:
    cars = generate_cars(300)
    path = write_catalog_csv(cars, tmp_path / "catalog.csv")
    assert import_cars_csv(path) == cars


def test_generate_csv_files_creates_distinct_files(tmp_path: Path) -> None:
    paths = generate_csv_files(tmp_path / "data", files=3, rows_per_file=50)
    assert [p.name for p in paths] == [
        "catalog_00.csv", "catalog_01.csv", "catalog_02.csv",
    ]
    contents = [import_cars_csv(p) for p in paths]
    assert all(len(rows) == 50 for rows in contents)
    assert contents[0] != contents[1]


def test_generate_csv_files_needs_at_least_one_file(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        generate_csv_files(tmp_path, files=0, rows_per_file=10)
