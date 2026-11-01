"""Integration: plain DB-API (sqlite3) with parameterized queries."""

import sqlite3
from pathlib import Path

import pytest

from car_catalog.dbapi import (
    count_cars_by_manufacturer,
    find_cars_by_manufacturer,
    search_cars,
)

pytestmark = pytest.mark.integration

INJECTION = "x' OR '1'='1"
# breaks out of LOWER('...') used by the real queries
INJECTION_IN_LOWER = "x') OR ('1'='1"
PAYLOADS = [INJECTION, INJECTION_IN_LOWER, "'; DROP TABLE cars; --"]


@pytest.fixture
def populated_db(seeded, db_path: Path) -> Path:
    """The file written by the ORM, read below without the ORM."""
    seeded.add_manufacturer("Tesla", "USA")  # a manufacturer without cars
    return db_path


def test_find_cars_by_manufacturer(populated_db: Path) -> None:
    rows = find_cars_by_manufacturer(populated_db, "BMW")
    assert [row["model"] for row in rows] == ["X5", "3 Series"]
    assert rows[0]["manufacturer"] == "BMW"
    assert rows[0]["price"] == 48200.0


def test_manufacturer_search_ignores_case_and_spaces(
    populated_db: Path,
) -> None:
    assert len(find_cars_by_manufacturer(populated_db, "  toyota ")) == 2


def test_unknown_manufacturer_gives_empty_list(populated_db: Path) -> None:
    assert find_cars_by_manufacturer(populated_db, "Opel") == []


def test_result_contains_the_migrated_vin_column(populated_db: Path) -> None:
    row = find_cars_by_manufacturer(populated_db, "Audi")[0]
    assert row["vin"] == "WAUZZZ8K9DA000005"


def test_search_cars_without_criteria_returns_everything(
    populated_db: Path,
) -> None:
    assert len(search_cars(populated_db)) == 5


@pytest.mark.parametrize(
    ("criteria", "expected"),
    [
        ({"manufacturer": "bmw"}, ["X5", "3 Series"]),
        ({"model": "camry"}, ["Camry"]),
        ({"min_year": 2021}, ["Corolla", "X5"]),
        ({"manufacturer": "bmw", "min_year": 2021}, ["X5"]),
        ({"manufacturer": "audi", "model": "a4", "min_year": 2018}, ["A4"]),
        ({"manufacturer": "audi", "min_year": 2019}, []),
    ],
)
def test_search_cars_combines_criteria(
    populated_db: Path, criteria, expected
) -> None:
    rows = search_cars(populated_db, **criteria)
    assert [row["model"] for row in rows] == expected


@pytest.mark.parametrize("payload", PAYLOADS)
def test_sql_injection_through_a_value_finds_nothing(
    populated_db: Path, payload: str
) -> None:
    assert find_cars_by_manufacturer(populated_db, payload) == []
    assert search_cars(populated_db, manufacturer=payload) == []
    assert search_cars(populated_db, model=payload) == []
    assert len(search_cars(populated_db)) == 5  # the table is intact


def unsafe_find(database_path: Path, manufacturer: str) -> list[tuple]:
    """What NOT to do: the value is pasted into the SQL text."""
    query = (
        "SELECT cars.model FROM cars JOIN manufacturers "
        "ON cars.manufacturer_id = manufacturers.id "
        f"WHERE manufacturers.name = '{manufacturer}'"
    )
    with sqlite3.connect(database_path) as connection:
        rows = connection.execute(query).fetchall()
    connection.close()
    return rows


def test_f_string_query_is_vulnerable_but_parameterized_query_is_not(
    populated_db: Path,
) -> None:
    assert len(unsafe_find(populated_db, INJECTION)) == 5  # leaks every car
    assert find_cars_by_manufacturer(populated_db, INJECTION) == []


def test_count_by_manufacturer_includes_empty_manufacturers(
    populated_db: Path,
) -> None:
    assert count_cars_by_manufacturer(populated_db) == [
        ("Audi", 1),
        ("BMW", 2),
        ("Tesla", 0),
        ("Toyota", 2),
    ]


def test_dbapi_sees_changes_made_through_the_orm(
    seeded, populated_db: Path
) -> None:
    seeded.update_price(seeded.cars.find_by_model("X5")[0].id, 50000.0)
    rows = find_cars_by_manufacturer(populated_db, "BMW")
    assert rows[0]["price"] == 50000.0


def test_querying_an_empty_database_file_fails_with_no_such_table(
    tmp_path: Path,
) -> None:
    with pytest.raises(sqlite3.OperationalError, match="no such table"):
        find_cars_by_manufacturer(tmp_path / "empty.db", "BMW")
