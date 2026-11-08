"""Integration: Alembic migrations on a separate SQLite file."""

import sqlite3
from pathlib import Path

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect

from car_catalog.orm_models import Base

pytestmark = pytest.mark.integration

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def alembic_config(db_path: Path) -> Config:
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "migrations"))
    config.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")
    return config


@pytest.fixture
def raw_db(db_path: Path):
    # `engine` fixture of this package would create the tables itself, so
    # the migration tests use plain DB-API connections instead
    connection = sqlite3.connect(db_path)
    connection.execute("PRAGMA foreign_keys=ON")
    yield connection
    connection.close()


def column_names(db_path: Path, table: str) -> list[str]:
    engine = create_engine(f"sqlite:///{db_path}")
    try:
        return [c["name"] for c in inspect(engine).get_columns(table)]
    finally:
        engine.dispose()


def test_there_are_two_linear_revisions(alembic_config: Config) -> None:
    script = ScriptDirectory.from_config(alembic_config)
    assert script.get_heads() == ["0002"]
    revisions = [rev.revision for rev in script.walk_revisions()]
    assert revisions == ["0002", "0001"]


def test_first_migration_creates_the_tables_without_vin(
    alembic_config: Config, db_path: Path
) -> None:
    command.upgrade(alembic_config, "0001")
    engine = create_engine(f"sqlite:///{db_path}")
    tables = set(inspect(engine).get_table_names())
    engine.dispose()
    assert {"manufacturers", "cars", "alembic_version"} <= tables
    assert "vin" not in column_names(db_path, "cars")


def test_second_migration_adds_vin_with_a_unique_constraint(
    alembic_config: Config, db_path: Path
) -> None:
    command.upgrade(alembic_config, "head")
    assert "vin" in column_names(db_path, "cars")
    engine = create_engine(f"sqlite:///{db_path}")
    uniques = inspect(engine).get_unique_constraints("cars")
    engine.dispose()
    assert {"name": "uq_cars_vin", "column_names": ["vin"]} in uniques


def test_unique_vin_is_enforced_after_the_migration(
    alembic_config: Config, db_path: Path, raw_db
) -> None:
    command.upgrade(alembic_config, "head")
    raw_db.execute("INSERT INTO manufacturers (name) VALUES ('BMW')")
    insert = (
        "INSERT INTO cars (manufacturer_id, model, year, price, mileage, vin)"
        " VALUES (1, ?, 2020, 1, 1, ?)"
    )
    raw_db.execute(insert, ("X5", "5UXKR0C58J0000003"))
    with pytest.raises(sqlite3.IntegrityError, match="UNIQUE"):
        raw_db.execute(insert, ("X3", "5UXKR0C58J0000003"))
    raw_db.execute(insert, ("X1", None))  # NULL is allowed many times
    raw_db.execute(insert, ("X2", None))


def test_existing_rows_survive_the_migration(
    alembic_config: Config, db_path: Path, raw_db
) -> None:
    command.upgrade(alembic_config, "0001")
    raw_db.execute("INSERT INTO manufacturers (name) VALUES ('BMW')")
    raw_db.execute(
        "INSERT INTO cars (manufacturer_id, model, year, price, mileage) "
        "VALUES (1, 'X5', 2021, 48200, 18000)"
    )
    raw_db.commit()

    command.upgrade(alembic_config, "head")

    row = raw_db.execute("SELECT model, price, vin FROM cars").fetchone()
    assert row == ("X5", 48200.0, None)


def test_constraints_survive_the_batch_migration(
    alembic_config: Config, raw_db
) -> None:
    command.upgrade(alembic_config, "head")
    raw_db.execute("INSERT INTO manufacturers (name) VALUES ('BMW')")
    with pytest.raises(sqlite3.IntegrityError, match="ck_cars_year_range"):
        raw_db.execute(
            "INSERT INTO cars (manufacturer_id, model, year, price, mileage)"
            " VALUES (1, 'Old', 1500, 1, 1)"
        )
    with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY"):
        raw_db.execute(
            "INSERT INTO cars (manufacturer_id, model, year, price, mileage)"
            " VALUES (99, 'Lost', 2020, 1, 1)"
        )


def test_downgrade_removes_vin_and_keeps_the_data(
    alembic_config: Config, db_path: Path, raw_db
) -> None:
    command.upgrade(alembic_config, "head")
    raw_db.execute("INSERT INTO manufacturers (name) VALUES ('BMW')")
    raw_db.execute(
        "INSERT INTO cars (manufacturer_id, model, year, price, mileage, vin)"
        " VALUES (1, 'X5', 2021, 48200, 18000, '5UXKR0C58J0000003')"
    )
    raw_db.commit()

    command.downgrade(alembic_config, "0001")

    assert "vin" not in column_names(db_path, "cars")
    assert raw_db.execute("SELECT COUNT(*) FROM cars").fetchone() == (1,)


def test_upgrade_after_downgrade_works_again(
    alembic_config: Config, db_path: Path
) -> None:
    command.upgrade(alembic_config, "head")
    command.downgrade(alembic_config, "base")
    assert "cars" not in column_names_or_empty(db_path)
    command.upgrade(alembic_config, "head")
    assert "vin" in column_names(db_path, "cars")


def column_names_or_empty(db_path: Path) -> list[str]:
    engine = create_engine(f"sqlite:///{db_path}")
    try:
        return inspect(engine).get_table_names()
    finally:
        engine.dispose()


def test_orm_models_match_the_migrated_schema(
    alembic_config: Config, db_path: Path
) -> None:
    """No drift between models.py and the migrations."""
    command.upgrade(alembic_config, "head")
    engine = create_engine(f"sqlite:///{db_path}")
    with engine.connect() as connection:
        context = MigrationContext.configure(
            connection, opts={"compare_type": True}
        )
        differences = compare_metadata(context, Base.metadata)
    engine.dispose()
    assert differences == []


def test_url_is_taken_from_the_environment(
    db_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "migrations"))
    monkeypatch.setenv("CAR_CATALOG_DATABASE_URL", f"sqlite:///{db_path}")
    command.upgrade(config, "head")
    assert "vin" in column_names(db_path, "cars")
