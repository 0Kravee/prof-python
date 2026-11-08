"""Validation of cars against the configured limits."""

import re

from car_catalog.config import AppConfig
from car_catalog.exceptions import InvalidCarDataError
from car_catalog.models import Car


def validate_car(car: Car, config: AppConfig | None = None) -> Car:
    """Return the car if it fits the configured ranges, else raise."""
    limits = config or AppConfig()
    if not limits.min_year <= car.year <= limits.max_year:
        raise InvalidCarDataError(
            f"Year {car.year} is outside {limits.min_year}..{limits.max_year}"
        )
    if not limits.min_price <= car.price <= limits.max_price:
        raise InvalidCarDataError(
            f"Price {car.price} is outside "
            f"{limits.min_price}..{limits.max_price}"
        )
    return car


def is_valid_car(car: Car, config: AppConfig | None = None) -> bool:
    """Boolean form of :func:`validate_car`."""
    try:
        validate_car(car, config)
    except InvalidCarDataError:
        return False
    return True


_VIN_PATTERN = re.compile(r"^[A-HJ-NPR-Z0-9]{17}$")


def normalize_vin(vin: str) -> str:
    """Return the VIN in upper case or raise InvalidCarDataError.

    A VIN has exactly 17 characters; the letters I, O and Q are not used.
    """
    if not isinstance(vin, str):
        raise InvalidCarDataError("VIN must be text")
    value = vin.strip().upper()
    if not _VIN_PATTERN.match(value):
        raise InvalidCarDataError(
            "VIN must have 17 characters (digits and letters except I, O, Q)"
        )
    return value
