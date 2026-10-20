"""Data model passed between pipeline stages."""

from dataclasses import dataclass

from stream_processor.config import (
    MAX_YEAR,
    MIN_MILEAGE,
    MIN_PRICE,
    MIN_YEAR,
)
from stream_processor.exceptions import InvalidCarDataError


@dataclass(frozen=True, slots=True)
class CarRecord:
    """One validated row of the car catalog."""

    car_id: int
    brand: str
    model: str
    year: int
    price: float
    mileage: int

    def __post_init__(self) -> None:
        if self.car_id <= 0:
            raise InvalidCarDataError("Car id must be positive")
        if not self.brand.strip() or not self.model.strip():
            raise InvalidCarDataError("Brand and model must not be empty")
        if not MIN_YEAR <= self.year <= MAX_YEAR:
            raise InvalidCarDataError(
                f"Year must be between {MIN_YEAR} and {MAX_YEAR}"
            )
        if self.price <= MIN_PRICE:
            raise InvalidCarDataError("Price must be positive")
        if self.mileage < MIN_MILEAGE:
            raise InvalidCarDataError("Mileage cannot be negative")

    @property
    def full_name(self) -> str:
        """Return brand and model combined, e.g. 'Toyota Camry'."""
        return f"{self.brand} {self.model}"
