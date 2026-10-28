"""Validation of external records at the system boundary."""

import math
from collections.abc import Mapping

from reliable_importer.exceptions import RecordValidationError
from reliable_importer.models import ValidationRules, Vehicle


def _as_int(value: object) -> int:
    if isinstance(value, bool):
        raise ValueError("a boolean is not an integer")
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, str):
        return int(value.strip())
    raise ValueError(f"unsupported type {type(value).__name__}")


def _as_float(value: object) -> float:
    if isinstance(value, bool):
        raise ValueError("a boolean is not a number")
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        return float(value.strip())
    raise ValueError(f"unsupported type {type(value).__name__}")


def _as_text(value: object) -> str:
    return "" if value is None else str(value).strip()


def parse_vehicle(
    data: Mapping[str, object],
    *,
    line_number: int,
    rules: ValidationRules,
) -> Vehicle:
    """Convert a raw record into a Vehicle or raise RecordValidationError.

    The original low-level error (ValueError, ...) is kept as ``__cause__``.
    """
    if any(key is None for key in data):
        raise RecordValidationError(
            "Record has more fields than the header",
            line_number=line_number,
        )
    try:
        vehicle_id = _as_int(data["vehicle_id"])
    except (KeyError, TypeError, ValueError) as error:
        raise RecordValidationError(
            "Invalid vehicle ID", line_number=line_number, field="vehicle_id"
        ) from error
    if vehicle_id <= 0:
        raise RecordValidationError(
            "Vehicle ID must be positive",
            line_number=line_number,
            field="vehicle_id",
        )

    brand = _as_text(data.get("brand"))
    if not brand:
        raise RecordValidationError(
            "Vehicle brand is empty", line_number=line_number, field="brand"
        )
    model = _as_text(data.get("model"))
    if not model:
        raise RecordValidationError(
            "Vehicle model is empty", line_number=line_number, field="model"
        )

    try:
        year = _as_int(data["year"])
    except (KeyError, TypeError, ValueError) as error:
        raise RecordValidationError(
            "Invalid year", line_number=line_number, field="year"
        ) from error
    if not rules.minimum_year <= year <= rules.maximum_year:
        raise RecordValidationError(
            f"Year must be between {rules.minimum_year} "
            f"and {rules.maximum_year}",
            line_number=line_number,
            field="year",
        )

    try:
        price = _as_float(data["price"])
    except (KeyError, TypeError, ValueError) as error:
        raise RecordValidationError(
            "Invalid price", line_number=line_number, field="price"
        ) from error
    if not math.isfinite(price) or price < 0:
        raise RecordValidationError(
            "Price must be a non-negative number",
            line_number=line_number,
            field="price",
        )
    if not rules.minimum_price <= price <= rules.maximum_price:
        raise RecordValidationError(
            f"Price must be between {rules.minimum_price:g} "
            f"and {rules.maximum_price:g}",
            line_number=line_number,
            field="price",
        )

    try:
        mileage = _as_int(data["mileage"])
    except (KeyError, TypeError, ValueError) as error:
        raise RecordValidationError(
            "Invalid mileage", line_number=line_number, field="mileage"
        ) from error
    if mileage < 0:
        raise RecordValidationError(
            "Mileage cannot be negative",
            line_number=line_number,
            field="mileage",
        )

    return Vehicle(
        vehicle_id=vehicle_id,
        brand=brand,
        model=model,
        year=year,
        price=price,
        mileage=mileage,
    )
