"""Unit tests of small database helpers (no real database files)."""

import pytest
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker

from car_catalog.database import (
    DATABASE_URL_ENV,
    DEFAULT_DATABASE_URL,
    create_db_engine,
    create_session_factory,
    get_database_url,
    init_db,
    session_scope,
)
from car_catalog.exceptions import InvalidCarDataError
from car_catalog.orm_models import CarEntity, Manufacturer
from car_catalog.validators import normalize_vin


def test_default_database_url() -> None:
    assert get_database_url() == DEFAULT_DATABASE_URL == "sqlite:///cars.db"


def test_environment_overrides_the_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(DATABASE_URL_ENV, "sqlite:///from_env.db")
    assert get_database_url() == "sqlite:///from_env.db"


def test_explicit_url_wins_over_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(DATABASE_URL_ENV, "sqlite:///from_env.db")
    assert get_database_url("sqlite:///explicit.db") == "sqlite:///explicit.db"


def test_engine_enables_foreign_keys() -> None:
    engine = create_db_engine("sqlite://")
    with engine.connect() as connection:
        assert connection.execute(text("PRAGMA foreign_keys")).scalar() == 1


def test_init_db_creates_both_tables() -> None:
    engine = create_db_engine("sqlite://")
    init_db(engine)
    with engine.connect() as connection:
        names = {
            row[0]
            for row in connection.execute(
                text("SELECT name FROM sqlite_master WHERE type = 'table'")
            )
        }
    assert {"manufacturers", "cars"} <= names


def test_session_factory_does_not_expire_objects() -> None:
    engine = create_db_engine("sqlite://")
    init_db(engine)
    factory: sessionmaker = create_session_factory(engine)
    with session_scope(factory) as session:
        manufacturer = Manufacturer(name="BMW")
        session.add(manufacturer)
    assert manufacturer.name == "BMW"  # usable after commit and close


def test_session_scope_rolls_back_when_the_block_fails() -> None:
    engine = create_db_engine("sqlite://")
    init_db(engine)
    factory = create_session_factory(engine)
    with pytest.raises(ValueError):
        with session_scope(factory) as session:
            session.add(Manufacturer(name="Ghost"))
            session.flush()
            raise ValueError("fail")
    with factory() as session:
        assert session.query(Manufacturer).count() == 0


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("5UXKR0C58J0000003", "5UXKR0C58J0000003"),
        (" 5uxkr0c58j0000003 ", "5UXKR0C58J0000003"),
    ],
)
def test_normalize_vin(raw: str, expected: str) -> None:
    assert normalize_vin(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "SHORT",
        "5UXKR0C58J00000033",
        "5UXKR0C58J000000O",
        "5UXKR0C58J0000-03",
        None,
        17,
    ],
)
def test_normalize_vin_rejects_bad_values(raw) -> None:
    with pytest.raises(InvalidCarDataError):
        normalize_vin(raw)


def test_entity_converts_to_the_lab01_dataclass() -> None:
    entity = CarEntity(
        model="X5", year=2021, price=48200.0, mileage=18000, vin=None
    )
    entity.manufacturer = Manufacturer(name="BMW")
    car = entity.to_domain()
    assert (car.brand, car.model, car.year) == ("BMW", "X5", 2021)


def test_reprs_are_readable() -> None:
    assert "BMW" in repr(Manufacturer(id=1, name="BMW"))
    assert "X5" in repr(CarEntity(id=2, model="X5"))
