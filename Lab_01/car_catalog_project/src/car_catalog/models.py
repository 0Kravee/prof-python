"""Data model for the car catalog laboratory project."""

from dataclasses import dataclass


@dataclass(slots=True)
class Car:
    """Represents a single car in the catalog."""

    brand: str
    model: str
    year: int
    price: float
    mileage: int

    def __post_init__(self) -> None:
        if self.year <= 1900:
            raise ValueError("Year must be greater than 1900")
        if self.price < 0:
            raise ValueError("Price cannot be negative")
        if self.mileage < 0:
            raise ValueError("Mileage cannot be negative")

    @property
    def full_name(self) -> str:
        """Return brand and model combined, e.g. 'Toyota Camry'."""
        return f"{self.brand} {self.model}"
