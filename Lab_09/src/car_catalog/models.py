"""Data model for the car catalog laboratory project."""

import math
from dataclasses import dataclass

from car_catalog.config import (
    CURRENCY,
    MAX_YEAR,
    MIN_MILEAGE,
    MIN_PRICE,
    MIN_YEAR,
)
from car_catalog.exceptions import InvalidCarDataError


def _is_int(value: object) -> bool:
    """True for real integers (bool is not accepted)."""
    return isinstance(value, int) and not isinstance(value, bool)


def _is_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


@dataclass(slots=True)
class Car:
    """Represents a single car in the catalog."""

    brand: str
    model: str
    year: int
    price: float
    mileage: int

    def __post_init__(self) -> None:
        if not isinstance(self.brand, str) or not isinstance(self.model, str):
            raise InvalidCarDataError("Brand and model must be text")
        self.brand = self.brand.strip()
        self.model = self.model.strip()
        if not self.brand or not self.model:
            raise InvalidCarDataError("Brand and model must not be empty")
        if not _is_int(self.year):
            raise InvalidCarDataError("Year must be an integer")
        if not MIN_YEAR <= self.year <= MAX_YEAR:
            raise InvalidCarDataError(
                f"Year must be between {MIN_YEAR} and {MAX_YEAR}"
            )
        if not _is_number(self.price) or not math.isfinite(self.price):
            raise InvalidCarDataError("Price must be a finite number")
        self.price = float(self.price)
        if self.price < MIN_PRICE:
            raise InvalidCarDataError("Price cannot be negative")
        if not _is_int(self.mileage):
            raise InvalidCarDataError("Mileage must be an integer")
        if self.mileage < MIN_MILEAGE:
            raise InvalidCarDataError("Mileage cannot be negative")

    @property
    def full_name(self) -> str:
        """Return brand and model combined, e.g. 'Toyota Camry'."""
        return f"{self.brand} {self.model}"

    @property
    def name(self) -> str:
        """Alias of ``full_name``."""
        return self.full_name

    @property
    def make(self) -> str:
        """Alias of ``brand``."""
        return self.brand

    def __str__(self) -> str:
        return (
            f"{self.full_name} ({self.year}), "
            f"{self.price:.2f} {CURRENCY}, {self.mileage} km"
        )
