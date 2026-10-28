"""Shared fixtures of the whole test suite."""

from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

from car_catalog.config import ENV_PREFIX, AppConfig
from car_catalog.models import Car
from car_catalog.repositories import InMemoryVehicleRepository

CSV_HEADER = "brand,model,year,price,mileage"

CSV_VALID = f"""{CSV_HEADER}
Toyota,Camry,2019,21500,45000
BMW,X5,2021,48200,18000
Toyota,Corolla,2022,19800,9000
Audi,A4,2018,23000,62000
BMW,3 Series,2020,31000,27000
"""

CarFactory = Callable[..., Car]


@pytest.fixture(autouse=True)
def clean_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Isolation: no CAR_CATALOG_* variable of the developer leaks in."""
    for name in (
        "MIN_YEAR",
        "MAX_YEAR",
        "MIN_PRICE",
        "MAX_PRICE",
        "CURRENCY",
    ):
        monkeypatch.delenv(ENV_PREFIX + name, raising=False)


@pytest.fixture
def car_factory() -> CarFactory:
    """Fixture factory: build a valid car, override only what matters."""

    def make(**overrides: object) -> Car:
        values: dict[str, object] = {
            "brand": "Toyota",
            "model": "Camry",
            "year": 2019,
            "price": 21500.0,
            "mileage": 45000,
        }
        values.update(overrides)
        return Car(**values)  # type: ignore[arg-type]

    return make


@pytest.fixture
def sample_cars(car_factory: CarFactory) -> list[Car]:
    return [
        car_factory(),
        car_factory(brand="BMW", model="X5", year=2021,
                    price=48200.0, mileage=18000),
        car_factory(model="Corolla", year=2022, price=19800.0, mileage=9000),
        car_factory(brand="Audi", model="A4", year=2018,
                    price=23000.0, mileage=62000),
        car_factory(brand="BMW", model="3 Series", year=2020,
                    price=31000.0, mileage=27000),
    ]


@pytest.fixture
def repository(sample_cars: list[Car]) -> InMemoryVehicleRepository:
    """A real in-memory repository used as a fake."""
    return InMemoryVehicleRepository(sample_cars)


@pytest.fixture
def default_config() -> AppConfig:
    return AppConfig()


@pytest.fixture
def csv_file(tmp_path: Path) -> Path:
    path = tmp_path / "cars.csv"
    path.write_text(CSV_VALID, encoding="utf-8")
    return path


@pytest.fixture
def write_csv(tmp_path: Path) -> Callable[[str], Path]:
    """Create a CSV file with the given body (header is added)."""

    def write(body: str, name: str = "input.csv") -> Path:
        path = tmp_path / name
        path.write_text(f"{CSV_HEADER}\n{body}", encoding="utf-8")
        return path

    return write


@pytest.fixture
def export_dir(tmp_path: Path) -> Iterator[Path]:
    """Fixture with teardown: no temporary export file may remain."""
    folder = tmp_path / "exports"
    folder.mkdir()
    yield folder
    leftovers = list(folder.glob("*.tmp"))
    assert not leftovers, f"temporary files were not cleaned: {leftovers}"
