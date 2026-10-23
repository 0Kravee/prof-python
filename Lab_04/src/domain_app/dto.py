"""External payloads (TypedDict) and data transfer objects."""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal, NotRequired, TypedDict

from domain_app.exceptions import InvalidPayloadError
from domain_app.models import Car, ElectricCar, Vehicle
from domain_app.value_objects import Money


class VehiclePayload(TypedDict):
    """Shape of vehicle data that comes from outside (JSON, API, file).

    It is only a typed dictionary, not a domain entity: it has no behaviour
    and no invariants, they appear after conversion to a domain object.
    """

    kind: Literal["car", "electric"]
    brand: str
    model: str
    year: int
    price: float
    mileage: int
    body_type: NotRequired[str]
    battery_kwh: NotRequired[float]
    range_km: NotRequired[int]
    vehicle_id: NotRequired[int]


def _text(raw: Mapping[str, object], key: str) -> str:
    value = raw.get(key)
    if not isinstance(value, str):
        raise InvalidPayloadError(f"Field {key!r} must be a string")
    return value


def _integer(raw: Mapping[str, object], key: str) -> int:
    value = raw.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise InvalidPayloadError(f"Field {key!r} must be an integer")
    return value


def _number(raw: Mapping[str, object], key: str) -> float:
    value = raw.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise InvalidPayloadError(f"Field {key!r} must be a number")
    return float(value)


def parse_payload(raw: Mapping[str, object]) -> VehiclePayload:
    """Check an untyped mapping and turn it into a typed payload.

    Type hints are not checked by Python at runtime, so data from the
    outside world must be validated explicitly.
    """
    kind = _text(raw, "kind")
    payload_kind: Literal["car", "electric"]
    if kind == "car":
        payload_kind = "car"
    elif kind == "electric":
        payload_kind = "electric"
    else:
        raise InvalidPayloadError(f"Unknown vehicle kind: {kind!r}")

    payload: VehiclePayload = {
        "kind": payload_kind,
        "brand": _text(raw, "brand"),
        "model": _text(raw, "model"),
        "year": _integer(raw, "year"),
        "price": _number(raw, "price"),
        "mileage": _integer(raw, "mileage"),
    }
    if "body_type" in raw:
        payload["body_type"] = _text(raw, "body_type")
    if "battery_kwh" in raw:
        payload["battery_kwh"] = _number(raw, "battery_kwh")
    if "range_km" in raw:
        payload["range_km"] = _integer(raw, "range_km")
    if "vehicle_id" in raw:
        payload["vehicle_id"] = _integer(raw, "vehicle_id")
    return payload


def vehicle_from_payload(payload: VehiclePayload) -> Vehicle:
    """Convert an external payload into a domain object."""
    body_type = payload.get("body_type", "sedan")
    vehicle_id = payload.get("vehicle_id")
    if payload["kind"] == "electric":
        if "battery_kwh" not in payload or "range_km" not in payload:
            raise InvalidPayloadError(
                "Electric car requires battery_kwh and range_km"
            )
        return ElectricCar(
            payload["brand"],
            payload["model"],
            payload["year"],
            payload["price"],
            payload["mileage"],
            vehicle_id,
            battery_kwh=payload["battery_kwh"],
            range_km=payload["range_km"],
            body_type=body_type,
        )
    return Car(
        payload["brand"],
        payload["model"],
        payload["year"],
        payload["price"],
        payload["mileage"],
        vehicle_id,
        body_type=body_type,
    )


@dataclass(frozen=True)
class VehicleSummary:
    """Flat read-only view of a vehicle for reports."""

    vehicle_id: int
    title: str
    kind: str
    price: str
    mileage: str

    @classmethod
    def from_vehicle(cls, vehicle: Vehicle) -> "VehicleSummary":
        return cls(
            vehicle_id=vehicle.vehicle_id,
            title=vehicle.specification.title,
            kind=type(vehicle).__name__,
            price=str(vehicle.price),
            mileage=str(vehicle.mileage),
        )


@dataclass(frozen=True)
class CatalogStatistics:
    """Aggregated catalog statistics."""

    count: int
    total_value: Money
    average_price: Money
    most_expensive: VehicleSummary | None
    lowest_mileage: VehicleSummary | None
