"""Integration: transactions, commit, rollback and the ACID properties."""

import math
import sqlite3
from pathlib import Path

import pytest
from sqlalchemy import Engine, event, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from car_catalog.config import AppConfig
from car_catalog.database import create_db_engine, session_scope
from car_catalog.db_services import CarDatabaseService
from car_catalog.exceptions import (
    DuplicateRecordError,
    InvalidCarDataError,
    RecordNotFoundError,
)
from car_catalog.orm_models import Manufacturer

pytestmark = pytest.mark.integration


def prices_from_file(db_path: Path, brand: str) -> list[float]:
    """Read prices through an independent DB-API connection."""
    with sqlite3.connect(db_path) as connection:
        rows = connection.execute(
            "SELECT cars.price FROM cars JOIN manufacturers "
            "ON cars.manufacturer_id = manufacturers.id "
            "WHERE manufacturers.name = ? ORDER BY cars.id",
            (brand,),
        ).fetchall()
    connection.close()
    return [price for (price,) in rows]


@pytest.fixture
def statements(engine: Engine) -> list[str]:
    """Collect every SQL statement executed by the engine."""
    log: list[str] = []

    @event.listens_for(engine, "before_cursor_execute")
    def record(conn, cursor, statement, params, context, executemany):
        log.append(statement)

    return log


# --- commit -----------------------------------------------------------


def test_bulk_update_commits_all_prices(seeded, db_path: Path) -> None:
    assert seeded.bulk_update_prices("BMW", 10) == 2
    assert prices_from_file(db_path, "BMW") == [53020.0, 34100.0]


def test_negative_percent_lowers_the_prices(seeded) -> None:
    seeded.bulk_update_prices("Toyota", -50)
    assert [c.price for c in seeded.find_by_brand("Toyota")] == [
        9900.0,
        10750.0,
    ]


def test_other_manufacturers_are_not_touched(seeded, db_path: Path) -> None:
    seeded.bulk_update_prices("BMW", 10)
    assert prices_from_file(db_path, "Toyota") == [19800.0, 21500.0]
    assert prices_from_file(db_path, "Audi") == [23000.0]


def test_manufacturer_without_cars_updates_nothing(seeded) -> None:
    seeded.add_manufacturer("Tesla")
    assert seeded.bulk_update_prices("Tesla", 10) == 0


def test_prices_are_rounded_to_cents(seeded) -> None:
    seeded.bulk_update_prices("Audi", 3.333)
    assert seeded.find_by_brand("Audi")[0].price == 23766.59


# --- rollback ---------------------------------------------------------


def test_invalid_data_rolls_back_updates_that_were_already_executed(
    seeded, db_path: Path, statements: list[str]
) -> None:
    """Corolla (first) is updated, Camry (second) becomes too expensive."""
    statements.clear()
    with pytest.raises(InvalidCarDataError, match="outside"):
        seeded.bulk_update_prices("Toyota", 46500)

    updates = [s for s in statements if s.startswith("UPDATE cars")]
    assert len(updates) == 1  # the first car really was updated ...
    # ... and restored by the rollback
    assert prices_from_file(db_path, "Toyota") == [19800.0, 21500.0]
    assert [c.price for c in seeded.find_by_brand("Toyota")] == [
        19800.0,
        21500.0,
    ]


@pytest.mark.parametrize(
    "percent", [math.nan, math.inf, -100, -250, "10", None, True]
)
def test_invalid_percent_is_rejected_before_any_update(
    seeded, statements: list[str], percent
) -> None:
    statements.clear()
    with pytest.raises(InvalidCarDataError):
        seeded.bulk_update_prices("BMW", percent)
    assert not [s for s in statements if s.startswith("UPDATE")]


def test_unknown_manufacturer_rolls_back(seeded) -> None:
    with pytest.raises(RecordNotFoundError):
        seeded.bulk_update_prices("Tesla", 10)
    assert seeded.cars.count() == 5


def test_configured_price_limit_is_part_of_the_validation(
    session: Session, seeded
) -> None:
    strict = CarDatabaseService(session, AppConfig(max_price=50_000.0))
    with pytest.raises(InvalidCarDataError):
        strict.bulk_update_prices("BMW", 10)  # 48200 -> 53020 > 50000
    assert [c.price for c in strict.find_by_brand("BMW")] == [48200.0, 31000.0]


def test_session_is_usable_after_a_rollback(seeded) -> None:
    with pytest.raises(InvalidCarDataError):
        seeded.bulk_update_prices("Toyota", 46500)
    assert seeded.bulk_update_prices("Toyota", 10) == 2


def test_failed_add_car_leaves_no_trace(seeded) -> None:
    with pytest.raises(InvalidCarDataError):
        seeded.add_car("BMW", "M3", 2020, 10.0, 1, "BADVIN")
    with pytest.raises(DuplicateRecordError):
        seeded.add_car("BMW", "M3", 2020, 10.0, 1, "WBA8E9C50GK000004")
    assert seeded.cars.find_by_model("M3") == []


# --- session_scope ----------------------------------------------------


def test_session_scope_commits_on_success(
    session_factory: sessionmaker[Session], db_path: Path
) -> None:
    with session_scope(session_factory) as scoped:
        CarDatabaseService(scoped).add_manufacturer("Kia", "Korea")
    with sqlite3.connect(db_path) as connection:
        assert connection.execute(
            "SELECT country FROM manufacturers WHERE name = 'Kia'"
        ).fetchone() == ("Korea",)
    connection.close()


def test_session_scope_rolls_back_on_error(
    session_factory: sessionmaker[Session], db_path: Path
) -> None:
    with pytest.raises(RuntimeError):
        with session_scope(session_factory) as scoped:
            scoped.add(Manufacturer(name="Ghost"))
            scoped.flush()
            raise RuntimeError("boom")
    with sqlite3.connect(db_path) as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM manufacturers"
        ).fetchone() == (0,)
    connection.close()


# --- ACID -------------------------------------------------------------


def test_atomicity_all_or_nothing(seeded, db_path: Path) -> None:
    before = prices_from_file(db_path, "Toyota")
    with pytest.raises(InvalidCarDataError):
        seeded.bulk_update_prices("Toyota", 46500)
    assert prices_from_file(db_path, "Toyota") == before


def test_consistency_constraints_keep_the_database_valid(seeded) -> None:
    with pytest.raises(IntegrityError):
        seeded.session.execute(text("UPDATE cars SET price = -5 WHERE id = 1"))
    seeded.session.rollback()
    assert all(car.price >= 0 for car in seeded.cars.list_all())


def test_isolation_uncommitted_changes_are_not_visible(
    seeded, db_path: Path
) -> None:
    seeded.session.execute(text("UPDATE cars SET price = 1 WHERE id = 1"))
    # not committed yet: another connection still sees the old value
    assert prices_from_file(db_path, "Toyota")[0] == 19800.0
    seeded.session.commit()
    assert prices_from_file(db_path, "Toyota")[0] == 1.0


def test_durability_data_survives_a_new_engine(seeded, db_path: Path) -> None:
    seeded.session.close()
    fresh = create_db_engine(f"sqlite:///{db_path}")
    try:
        with sessionmaker(bind=fresh)() as other:
            assert CarDatabaseService(other).cars.count() == 5
    finally:
        fresh.dispose()
