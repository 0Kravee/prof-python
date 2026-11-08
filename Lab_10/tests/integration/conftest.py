"""Fixtures of the database integration tests.

Every test gets its own SQLite file in ``tmp_path``: the real
``cars.db`` is never touched and tests cannot influence each other.
"""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from car_catalog.api import create_app
from car_catalog.config import Settings
from car_catalog.database import (
    create_db_engine,
    create_session_factory,
    init_db,
)
from car_catalog.db_services import CarDatabaseService
from car_catalog.repositories import CarRepository, ManufacturerRepository

# manufacturer, country, [(model, year, price, mileage, vin), ...]
SEED_DATA = (
    (
        "Toyota",
        "Japan",
        [
            ("Corolla", 2022, 19800.0, 9000, "JTDKARFU5H3000002"),
            ("Camry", 2019, 21500.0, 45000, "4T1BF1FK5HU000001"),
        ],
    ),
    (
        "BMW",
        "Germany",
        [
            ("X5", 2021, 48200.0, 18000, "5UXKR0C58J0000003"),
            ("3 Series", 2020, 31000.0, 27000, "WBA8E9C50GK000004"),
        ],
    ),
    (
        "Audi",
        "Germany",
        [
            ("A4", 2018, 23000.0, 62000, "WAUZZZ8K9DA000005"),
        ],
    ),
)


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "test_cars.db"


@pytest.fixture
def engine(db_path: Path) -> Iterator[Engine]:
    test_engine = create_db_engine(f"sqlite:///{db_path}")
    init_db(test_engine)
    yield test_engine
    test_engine.dispose()


@pytest.fixture
def session_factory(engine: Engine) -> sessionmaker[Session]:
    return create_session_factory(engine)


@pytest.fixture
def session(session_factory: sessionmaker[Session]) -> Iterator[Session]:
    with session_factory() as db_session:
        yield db_session


@pytest.fixture
def manufacturer_repo(session: Session) -> ManufacturerRepository:
    return ManufacturerRepository(session)


@pytest.fixture
def car_repo(session: Session) -> CarRepository:
    return CarRepository(session)


@pytest.fixture
def service(session: Session) -> CarDatabaseService:
    """Service over an empty database."""
    return CarDatabaseService(session)


@pytest.fixture
def seeded(service: CarDatabaseService) -> CarDatabaseService:
    """Service over a database with 3 manufacturers and 5 cars."""
    for name, country, cars in SEED_DATA:
        service.add_manufacturer(name, country)
        for model, year, price, mileage, vin in cars:
            service.add_car(name, model, year, price, mileage, vin)
    return service


# --- REST API fixtures (laboratory work 10) --------------------------------

API_KEY = "test-only-api-key"


def _api_settings(db_path: Path, **values: object) -> Settings:
    return Settings(
        _env_file=None,  # type: ignore[call-arg]
        database_url=f"sqlite:///{db_path}",
        app_env="test",
        auto_create_tables=True,
        **values,  # type: ignore[arg-type]
    )


@pytest.fixture
def api_key() -> str:
    return API_KEY


@pytest.fixture
def client(db_path: Path) -> Iterator[TestClient]:
    """API without an API key; its own empty database file."""
    with TestClient(create_app(_api_settings(db_path))) as test_client:
        yield test_client


@pytest.fixture
def secured_client(db_path: Path) -> Iterator[TestClient]:
    """API that requires the X-API-Key header for changing requests."""
    settings = _api_settings(db_path, api_key=API_KEY)
    with TestClient(create_app(settings)) as test_client:
        yield test_client


@pytest.fixture
def api_data(client: TestClient) -> dict[str, int]:
    """Three manufacturers and five cars created through the API."""
    ids: dict[str, int] = {}
    for name, country, cars in SEED_DATA:
        created = client.post(
            "/manufacturers", json={"name": name, "country": country}
        )
        assert created.status_code == 201
        ids[name] = created.json()["id"]
        for model, year, price, mileage, vin in cars:
            response = client.post(
                "/cars",
                json={
                    "manufacturer_id": ids[name],
                    "model": model,
                    "year": year,
                    "price": price,
                    "mileage": mileage,
                    "vin": vin,
                },
            )
            assert response.status_code == 201
    return ids
