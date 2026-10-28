"""Interfaces of the external dependencies (system boundaries)."""

from typing import Protocol

from car_catalog.models import Car


class VehicleRepository(Protocol):
    """Storage of cars."""

    def add(self, car: Car) -> None: ...

    def list_all(self) -> list[Car]: ...

    def remove(self, brand: str, model: str) -> Car: ...


class VehicleInfoService(Protocol):
    """External synchronous service with extra vehicle data."""

    def lookup(self, brand: str, model: str) -> dict[str, str]: ...


class AsyncVehicleInfoService(Protocol):
    """External asynchronous service with extra vehicle data."""

    async def fetch(self, brand: str, model: str) -> dict[str, str]: ...
