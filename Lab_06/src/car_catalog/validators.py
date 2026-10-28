"""Validation of cars against the configured limits."""

from car_catalog.config import AppConfig
from car_catalog.exceptions import InvalidCarDataError
from car_catalog.models import Car


def validate_car(car: Car, config: AppConfig | None = None) -> Car:
    """Return the car if it fits the configured ranges, else raise."""
    limits = config or AppConfig()
    if not limits.min_year <= car.year <= limits.max_year:
        raise InvalidCarDataError(
            f"Year {car.year} is outside "
            f"{limits.min_year}..{limits.max_year}"
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
