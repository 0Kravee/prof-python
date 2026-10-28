"""Record validation (boundary between external data and the domain)."""

from collections.abc import Mapping

import pytest

from reliable_importer.exceptions import RecordValidationError
from reliable_importer.models import ValidationRules, Vehicle
from reliable_importer.validators import parse_vehicle

GOOD: dict[str, object] = {
    "vehicle_id": "1",
    "brand": " Toyota ",
    "model": "Camry",
    "year": "2019",
    "price": "21500",
    "mileage": "45000",
}


def parse(data: Mapping[str, object], rules: ValidationRules) -> Vehicle:
    return parse_vehicle(data, line_number=5, rules=rules)


def test_valid_record(rules: ValidationRules) -> None:
    vehicle = parse(GOOD, rules)
    assert vehicle == Vehicle(1, "Toyota", "Camry", 2019, 21500.0, 45000)
    assert vehicle.to_dict()["brand"] == "Toyota"


@pytest.mark.parametrize(
    ("override", "field", "text"),
    [
        ({"vehicle_id": "abc"}, "vehicle_id", "Invalid vehicle ID"),
        ({"vehicle_id": "0"}, "vehicle_id", "must be positive"),
        ({"vehicle_id": "-3"}, "vehicle_id", "must be positive"),
        ({"vehicle_id": "1.5"}, "vehicle_id", "Invalid vehicle ID"),
        ({"brand": ""}, "brand", "brand is empty"),
        ({"brand": "   "}, "brand", "brand is empty"),
        ({"brand": None}, "brand", "brand is empty"),
        ({"model": ""}, "model", "model is empty"),
        ({"year": "abc"}, "year", "Invalid year"),
        ({"year": "1850"}, "year", "Year must be between"),
        ({"year": "2099"}, "year", "Year must be between"),
        ({"price": "x"}, "price", "Invalid price"),
        ({"price": "-1"}, "price", "non-negative"),
        ({"price": "nan"}, "price", "non-negative"),
        ({"price": "inf"}, "price", "non-negative"),
        ({"price": "999999"}, "price", "Price must be between"),
        ({"mileage": "abc"}, "mileage", "Invalid mileage"),
        ({"mileage": "-1"}, "mileage", "cannot be negative"),
        ({"mileage": "1.5"}, "mileage", "Invalid mileage"),
        ({"year": True}, "year", "Invalid year"),
        ({"price": None}, "price", "Invalid price"),
    ],
)
def test_invalid_records(
    override: dict[str, object], field: str, text: str, rules: ValidationRules
) -> None:
    with pytest.raises(RecordValidationError) as info:
        parse({**GOOD, **override}, rules)
    assert info.value.field == field
    assert info.value.line_number == 5
    assert text in str(info.value)


@pytest.mark.parametrize("key", list(GOOD))
def test_missing_field_is_reported(key: str, rules: ValidationRules) -> None:
    data = {k: v for k, v in GOOD.items() if k != key}
    with pytest.raises(RecordValidationError):
        parse(data, rules)


def test_json_native_types_are_accepted(rules: ValidationRules) -> None:
    data: dict[str, object] = {
        "vehicle_id": 7,
        "brand": "Audi",
        "model": "A4",
        "year": 2020.0,
        "price": 100,
        "mileage": 5,
    }
    assert parse(data, rules).year == 2020


def test_extra_fields_are_rejected(rules: ValidationRules) -> None:
    data: dict[object, object] = {**GOOD, None: ["surplus"]}
    with pytest.raises(RecordValidationError, match="more fields"):
        parse(data, rules)  # type: ignore[arg-type]


def test_boundaries_are_inclusive(rules: ValidationRules) -> None:
    low = {**GOOD, "year": "1990", "price": "0", "mileage": "0"}
    high = {**GOOD, "year": "2026", "price": "200000"}
    assert parse(low, rules).year == 1990
    assert parse(high, rules).price == 200000.0
