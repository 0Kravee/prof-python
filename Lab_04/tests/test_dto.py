"""Tests for TypedDict payloads and DTOs."""

import pytest

from domain_app.dto import (
    CatalogStatistics,
    VehiclePayload,
    VehicleSummary,
    parse_payload,
    vehicle_from_payload,
)
from domain_app.exceptions import InvalidPayloadError
from domain_app.models import Car, ElectricCar
from domain_app.value_objects import Money

CAR_RAW: dict[str, object] = {
    "kind": "car",
    "brand": "Audi",
    "model": "A4",
    "year": 2018,
    "price": 23000,
    "mileage": 62000,
}


def test_parse_valid_payload_and_convert() -> None:
    payload = parse_payload({**CAR_RAW, "body_type": "wagon", "vehicle_id": 4})
    assert payload["kind"] == "car" and payload["price"] == 23000.0
    vehicle = vehicle_from_payload(payload)
    assert type(vehicle) is Car and vehicle.vehicle_id == 4
    assert vehicle.describe().startswith("Audi A4 (2018): wagon")


def test_electric_payload() -> None:
    raw = {**CAR_RAW, "kind": "electric", "battery_kwh": 60, "range_km": 400}
    vehicle = vehicle_from_payload(parse_payload(raw))
    assert isinstance(vehicle, ElectricCar) and vehicle.range_km == 400


def test_electric_payload_requires_battery_fields() -> None:
    payload: VehiclePayload = {
        "kind": "electric",
        "brand": "A",
        "model": "B",
        "year": 2020,
        "price": 1.0,
        "mileage": 1,
    }
    with pytest.raises(InvalidPayloadError):
        vehicle_from_payload(payload)


@pytest.mark.parametrize(
    "override",
    [
        {"year": "2018"},
        {"year": True},
        {"price": "free"},
        {"brand": 5},
        {"kind": "bike"},
        {"kind": None},
        {"battery_kwh": "big"},
        {"range_km": 1.5},
    ],
)
def test_invalid_payloads_are_rejected(override: dict[str, object]) -> None:
    with pytest.raises(InvalidPayloadError):
        parse_payload({**CAR_RAW, **override})
    with pytest.raises(ValueError):  # custom error is also a ValueError
        parse_payload({**CAR_RAW, **override})


def test_missing_field_is_rejected() -> None:
    raw = dict(CAR_RAW)
    del raw["mileage"]
    with pytest.raises(InvalidPayloadError):
        parse_payload(raw)


def test_summary_and_statistics_are_frozen_dtos() -> None:
    car = Car("A", "B", 2020, 1000, 10, 1)
    summary = VehicleSummary.from_vehicle(car)
    assert summary == VehicleSummary(
        1, "A B (2020)", "Car", "1000.00 USD", "10 km"
    )
    stats = CatalogStatistics(1, Money.of(1), Money.of(1), summary, None)
    with pytest.raises(AttributeError):
        stats.count = 2  # type: ignore[misc]
