"""Shared fixtures: an application on an in-memory database."""

from collections.abc import Iterator
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from car_catalog.api import create_app
from car_catalog.config import Settings
from car_catalog.database import Database

CARS: list[dict[str, Any]] = [
    {
        "brand": "Toyota",
        "model": "Camry",
        "year": 2019,
        "price": 21500,
        "mileage": 45000,
    },
    {
        "brand": "BMW",
        "model": "X5",
        "year": 2021,
        "price": 48200,
        "mileage": 18000,
    },
    {
        "brand": "Toyota",
        "model": "Corolla",
        "year": 2022,
        "price": 19800,
        "mileage": 9000,
    },
    {
        "brand": "Audi",
        "model": "A4",
        "year": 2018,
        "price": 23000,
        "mileage": 62000,
    },
    {
        "brand": "BMW",
        "model": "3 Series",
        "year": 2020,
        "price": 31000,
        "mileage": 27000,
    },
]


@pytest.fixture
def settings() -> Settings:
    return Settings(
        database_url="sqlite://",
        backoff_seconds=0.001,
        batch_timeout=2.0,
    )


@pytest.fixture
def database(settings: Settings) -> Database:
    return Database(settings.database_url)


@pytest.fixture
def session(database: Database) -> Iterator[Session]:
    yield from database.session()


@pytest.fixture
def app(settings: Settings, database: Database) -> FastAPI:
    return create_app(settings, database)


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def seeded(client: TestClient) -> TestClient:
    """A client whose catalog already contains the five demo cars."""
    for payload in CARS:
        assert client.post("/cars", json=payload).status_code == 201
    return client
