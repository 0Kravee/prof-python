"""Engine and session factory (SQLite)."""

from __future__ import annotations

import os
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from car_catalog.config import ENV_PREFIX
from car_catalog.orm_models import Base

DATABASE_URL_ENV = "DATABASE_URL"
LEGACY_DATABASE_URL_ENV = ENV_PREFIX + "DATABASE_URL"  # used in labs 7 - 9
DEFAULT_DATABASE_URL = "sqlite:///cars.db"


def get_database_url(url: str | None = None) -> str:
    """Explicit argument > DATABASE_URL > legacy variable > default file."""
    return (
        url
        or os.environ.get(DATABASE_URL_ENV)
        or os.environ.get(LEGACY_DATABASE_URL_ENV)
        or DEFAULT_DATABASE_URL
    )


def _configure_sqlite(dbapi_connection: sqlite3.Connection, _: Any) -> None:
    # SQLite does not enforce foreign keys unless it is asked to.
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()
    # let SQLAlchemy emit BEGIN itself: SAVEPOINT then works correctly
    dbapi_connection.isolation_level = None


def _begin(connection: Any) -> None:
    connection.exec_driver_sql("BEGIN")


def create_db_engine(url: str | None = None, echo: bool = False) -> Engine:
    """Create an engine with foreign key enforcement enabled."""
    engine = create_engine(get_database_url(url), echo=echo)
    event.listen(engine, "connect", _configure_sqlite)
    event.listen(engine, "begin", _begin)
    return engine


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def init_db(engine: Engine) -> None:
    """Create all tables (the migrations do the same for real databases)."""
    Base.metadata.create_all(engine)


@contextmanager
def session_scope(factory: sessionmaker[Session]) -> Iterator[Session]:
    """Commit on success, rollback on any error."""
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
