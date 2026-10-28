"""Repository implementations."""

from collections.abc import Iterable

from car_catalog.exceptions import CarNotFoundError
from car_catalog.models import Car


class InMemoryVehicleRepository:
    """Simple list-backed repository (also used as a fake in tests)."""

    def __init__(self, cars: Iterable[Car] | None = None) -> None:
        self._cars: list[Car] = list(cars) if cars is not None else []

    def __len__(self) -> int:
        return len(self._cars)

    def add(self, car: Car) -> None:
        self._cars.append(car)

    def list_all(self) -> list[Car]:
        """Return a copy, so callers cannot change the storage."""
        return list(self._cars)

    def remove(self, brand: str, model: str) -> Car:
        for index, car in enumerate(self._cars):
            if (
                car.brand.lower() == brand.strip().lower()
                and car.model.lower() == model.strip().lower()
            ):
                return self._cars.pop(index)
        raise CarNotFoundError(f"Car {brand} {model} was not found")
