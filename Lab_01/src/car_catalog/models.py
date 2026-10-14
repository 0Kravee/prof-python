"""Data model for the car catalog laboratory project."""

from dataclasses import dataclass

from car_catalog.config import (
    CURRENCY,
    MAX_YEAR,
    MIN_MILEAGE,
    MIN_PRICE,
    MIN_YEAR,
)
from car_catalog.exceptions import InvalidCarDataError


@dataclass(slots=True)
class Car:
    """Represents a single car in the catalog."""

    brand: str
    model: str
    year: int
    price: float
    mileage: int

    def __post_init__(self) -> None:
        if not self.brand.strip() or not self.model.strip():
            raise InvalidCarDataError("Brand and model must not be empty")
        if not MIN_YEAR <= self.year <= MAX_YEAR:
            raise InvalidCarDataError(
                f"Year must be between {MIN_YEAR} and {MAX_YEAR}"
            )
        if self.price < MIN_PRICE:
            raise InvalidCarDataError("Price cannot be negative")
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
