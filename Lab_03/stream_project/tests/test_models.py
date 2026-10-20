"""Tests for the data model, configuration and custom exceptions."""

import dataclasses
from collections.abc import Iterator

import pytest

import student_project
from stream_processor import batches, config
from stream_processor.exceptions import (
    InvalidBatchSizeError,
    InvalidCarDataError,
    StreamProcessorError,
)
from stream_processor.filters import validate_row
from stream_processor.models import CarRecord
from stream_processor.transformations import normalize_cars
from student_project.models import CarRecord as CompatCarRecord


def make(**changes: object) -> CarRecord:
    values: dict[str, object] = {
        "car_id": 1,
        "brand": "BMW",
        "model": "X5",
        "year": 2021,
        "price": 48200.0,
        "mileage": 18000,
    }
    values.update(changes)
    return CarRecord(**values)  # type: ignore[arg-type]


def test_car_record_is_a_dataclass() -> None:
    assert dataclasses.is_dataclass(CarRecord)
    assert make().full_name == "BMW X5"


def test_car_record_is_immutable() -> None:
    car = make()
    with pytest.raises(dataclasses.FrozenInstanceError):
        car.price = 1.0  # type: ignore[misc]


@pytest.mark.parametrize(
    "changes",
    [
        {"car_id": 0},
        {"brand": "  "},
        {"model": ""},
        {"year": config.MIN_YEAR - 1},
        {"year": config.MAX_YEAR + 1},
        {"price": 0.0},
        {"price": -5.0},
        {"mileage": -1},
    ],
)
def test_invalid_data_raises_custom_exception(
    changes: dict[str, object],
) -> None:
    with pytest.raises(InvalidCarDataError):
        make(**changes)


def test_exception_hierarchy() -> None:
    assert issubclass(InvalidCarDataError, StreamProcessorError)
    assert issubclass(InvalidCarDataError, ValueError)
    assert issubclass(InvalidBatchSizeError, StreamProcessorError)
    assert issubclass(InvalidBatchSizeError, ValueError)


def test_invalid_batch_size_uses_custom_exception() -> None:
    with pytest.raises(InvalidBatchSizeError):
        list(batches.batched(range(3), 0))


def test_validate_row_still_returns_none_for_bad_rows() -> None:
    bad = {"id": "1", "brand": "BMW", "model": "X5", "year": "1850",
           "price": "100", "mileage": "0"}
    assert validate_row(bad) is None


def test_normalize_keeps_record_type() -> None:
    stream: Iterator[CarRecord] = iter([make(brand="bmw")])
    (result,) = list(normalize_cars(stream))
    assert isinstance(result, CarRecord)
    assert result.brand == "BMW"


def test_config_constants() -> None:
    assert config.MIN_YEAR < config.MAX_YEAR
    assert config.CURRENCY == "USD"
    assert config.CSV_HEADER[0] == "id"


def test_student_project_reexports_same_objects() -> None:
    assert CompatCarRecord is CarRecord
    assert student_project.__version__
