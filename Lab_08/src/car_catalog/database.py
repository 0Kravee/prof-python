"""Database access: engine, sessions and schema creation."""

import threading
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool

IN_MEMORY_URLS = ("sqlite://", "sqlite:///:memory:")


class Base(DeclarativeBase):
    """Declarative base of all ORM models."""


def _enable_foreign_keys(dbapi_connection: Any, _record: Any) -> None:
    """SQLite ignores foreign keys unless they are switched on."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


class Database:
    """Owns the engine and hands out short-lived sessions."""

    def __init__(self, url: str) -> None:
        self.url = url
        options: dict[str, Any] = {}
        if url.startswith("sqlite"):
            options["connect_args"] = {"check_same_thread": False}
            if url in IN_MEMORY_URLS:
                options["poolclass"] = StaticPool
            else:
                path = Path(url.removeprefix("sqlite:///"))
                path.parent.mkdir(parents=True, exist_ok=True)
        self.engine: Engine = create_engine(url, **options)
        if url.startswith("sqlite"):
            event.listen(self.engine, "connect", _enable_foreign_keys)
        self.session_factory = sessionmaker(
            self.engine, expire_on_commit=False
        )
        self._schema_ready = False
        self._lock = threading.Lock()

    def ensure_schema(self) -> None:
        """Create the tables once (idempotent and thread-safe)."""
        if self._schema_ready:
            return
        with self._lock:
            if not self._schema_ready:
                Base.metadata.create_all(self.engine)
                self._schema_ready = True

    def session(self) -> Iterator[Session]:
        """Yield a session and always close it (FastAPI dependency body)."""
        self.ensure_schema()
        session = self.session_factory()
        try:
            yield session
        finally:
            session.close()

    def dispose(self) -> None:
        """Close pooled connections (an in-memory database is kept)."""
        if self.url not in IN_MEMORY_URLS:
            self.engine.dispose()
