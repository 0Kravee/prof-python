"""Settings and Pydantic schema validation."""

import pytest
from pydantic import ValidationError

from car_catalog.config import Settings
from car_catalog.schemas import (
    BatchRequest,
    CarCreate,
    CarUpdate,
    ManufacturerCreate,
)

GOOD = {"model": "Camry", "year": 2019, "price": 1.5, "mileage": 0}


def test_settings_defaults_and_env() -> None:
    assert Settings().max_attempts == 3 and Settings().api_base_url is None
    env = {
        "CARS_DATABASE_URL": "sqlite://",
        "CARS_API_BASE_URL": "http://x:1",
        "CARS_MAX_ATTEMPTS": "5",
        "CARS_BACKOFF_SECONDS": "0.5",
        "CARS_BATCH_TIMEOUT": "7",
        "CARS_MAX_CONCURRENCY": "2",
    }
    settings = Settings.from_env(env)
    assert settings.database_url == "sqlite://"
    assert settings.api_base_url == "http://x:1"
    assert (settings.max_attempts, settings.backoff_seconds) == (5, 0.5)
    assert (settings.batch_timeout, settings.max_concurrency) == (7.0, 2)
    assert Settings.from_env({}) == Settings()


@pytest.mark.parametrize(
    "kwargs",
    [
        {"max_attempts": 0},
        {"max_concurrency": 0},
        {"max_batch_size": 0},
        {"backoff_seconds": -1.0},
        {"request_timeout": 0},
        {"batch_timeout": 0},
    ],
)
def test_invalid_settings(kwargs: dict[str, float]) -> None:
    with pytest.raises(ValueError):
        Settings(**kwargs)  # type: ignore[arg-type]


def test_car_create_requires_exactly_one_manufacturer_reference() -> None:
    by_brand = CarCreate.model_validate({"brand": "Audi", **GOOD})
    assert by_brand.brand == "Audi"
    by_id = CarCreate.model_validate({"manufacturer_id": 1, **GOOD})
    assert by_id.manufacturer_id == 1
    with pytest.raises(ValidationError, match="exactly one"):
        CarCreate.model_validate(GOOD)
    with pytest.raises(ValidationError, match="exactly one"):
        CarCreate.model_validate({"brand": "A", "manufacturer_id": 1, **GOOD})


@pytest.mark.parametrize(
    "override",
    [
        {"year": 1885},
        {"year": 2101},
        {"price": -0.01},
        {"mileage": -1},
        {"price": float("nan")},
        {"price": float("inf")},
        {"model": ""},
        {"model": "   "},
        {"unknown": 1},
        {"year": "abc"},
    ],
)
def test_car_create_rejects_bad_values(override: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        CarCreate.model_validate({"brand": "A", **GOOD, **override})


def test_strings_are_trimmed() -> None:
    car = CarCreate.model_validate(
        {"brand": "  Audi ", **GOOD, "model": " A4 "}
    )
    assert (car.brand, car.model) == ("Audi", "A4")
    assert ManufacturerCreate(name="  BMW  ").name == "BMW"


def test_car_update_rules() -> None:
    assert CarUpdate(price=5.0).model_dump(exclude_unset=True) == {
        "price": 5.0
    }
    with pytest.raises(ValidationError, match="at least one"):
        CarUpdate()
    with pytest.raises(ValidationError, match="null"):
        CarUpdate.model_validate({"price": None})
    with pytest.raises(ValidationError):
        CarUpdate.model_validate({"brand": "x"})  # brand is not updatable


def test_batch_request_limits() -> None:
    assert BatchRequest(ids=[1, 2]).ids == [1, 2]
    for ids in ([], [0], [-1], list(range(1, 1002))):
        with pytest.raises(ValidationError):
            BatchRequest(ids=ids)
