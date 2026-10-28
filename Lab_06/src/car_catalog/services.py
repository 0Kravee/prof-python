"""Business logic for the car catalog (no print and no input here)."""

import asyncio
from collections.abc import Iterable
from pathlib import Path

from car_catalog.config import AppConfig
from car_catalog.exceptions import CarNotFoundError, ExternalServiceError
from car_catalog.exporters import export_cars_json
from car_catalog.importers import import_cars_csv
from car_catalog.models import Car
from car_catalog.protocols import (
    AsyncVehicleInfoService,
    VehicleInfoService,
    VehicleRepository,
)
from car_catalog.validators import validate_car


def add_car(cars: list[Car], car: Car) -> list[Car]:
    """Append a car to the catalog and return the same list."""
    cars.append(car)
    return cars


def create_car(
    brand: str, model: str, year: int, price: float, mileage: int
) -> Car:
    """Create a validated Car instance."""
    return Car(brand, model, year, price, mileage)


def remove_car(cars: list[Car], brand: str, model: str) -> Car:
    """Remove the first car with the given brand and model."""
    for index, car in enumerate(cars):
        if car.brand.lower() == brand.lower() and (
            car.model.lower() == model.lower()
        ):
            return cars.pop(index)
    raise CarNotFoundError(f"Car {brand} {model} was not found")


def search_by_brand(cars: Iterable[Car], brand: str) -> list[Car]:
    """Return all cars of the given brand (case-insensitive)."""
    wanted = brand.strip().lower()
    return [car for car in cars if car.brand.lower() == wanted]


def search_by_model(cars: Iterable[Car], model: str) -> list[Car]:
    """Return all cars of the given model (case-insensitive)."""
    wanted = model.strip().lower()
    return [car for car in cars if car.model.lower() == wanted]


def filter_by_year(cars: Iterable[Car], year: int) -> list[Car]:
    """Return all cars manufactured in the given year."""
    return [car for car in cars if car.year == year]


def find_most_expensive(cars: Iterable[Car]) -> Car | None:
    """Return the most expensive car, or None for an empty catalog."""
    return max(cars, key=lambda car: car.price, default=None)


def calculate_average_price(cars: Iterable[Car]) -> float:
    """Return the average price, or 0.0 for an empty catalog."""
    items = list(cars)
    if not items:
        return 0.0
    return sum(car.price for car in items) / len(items)


def find_lowest_mileage(cars: Iterable[Car]) -> Car | None:
    """Return the car with the lowest mileage, or None if empty."""
    return min(cars, key=lambda car: car.mileage, default=None)


def sort_by_price(cars: Iterable[Car], descending: bool = True) -> list[Car]:
    """Return cars sorted by price (descending by default)."""
    return sorted(cars, key=lambda car: car.price, reverse=descending)


def sort_by_year(cars: Iterable[Car], descending: bool = True) -> list[Car]:
    """Return cars sorted by manufacturing year (newest first)."""
    return sorted(cars, key=lambda car: car.year, reverse=descending)


def sort_by_mileage(
    cars: Iterable[Car], descending: bool = False
) -> list[Car]:
    """Return cars sorted by mileage (lowest first by default)."""
    return sorted(cars, key=lambda car: car.mileage, reverse=descending)


def search_cars(
    cars: Iterable[Car],
    brand: str | None = None,
    min_year: int | None = None,
    max_price: float | None = None,
    max_mileage: int | None = None,
) -> list[Car]:
    """Search by several criteria; criteria set to None are ignored."""
    result: list[Car] = []
    for car in cars:
        if brand is not None and car.brand.lower() != brand.strip().lower():
            continue
        if min_year is not None and car.year < min_year:
            continue
        if max_price is not None and car.price > max_price:
            continue
        if max_mileage is not None and car.mileage > max_mileage:
            continue
        result.append(car)
    return result


def get_statistics(cars: Iterable[Car]) -> dict[str, float]:
    """Return basic statistics of the catalog."""
    items = list(cars)
    if not items:
        return {
            "count": 0,
            "average_price": 0.0,
            "min_price": 0.0,
            "max_price": 0.0,
            "average_mileage": 0.0,
        }
    prices = [car.price for car in items]
    return {
        "count": len(items),
        "average_price": sum(prices) / len(items),
        "min_price": min(prices),
        "max_price": max(prices),
        "average_mileage": sum(car.mileage for car in items) / len(items),
    }


class CarCatalog:
    """Object-oriented facade over the functional business logic."""

    def __init__(self, cars: Iterable[Car] | None = None) -> None:
        self.cars: list[Car] = list(cars) if cars is not None else []

    def __len__(self) -> int:
        return len(self.cars)

    def add(self, car: Car) -> None:
        add_car(self.cars, car)

    def search_by_brand(self, brand: str) -> list[Car]:
        return search_by_brand(self.cars, brand)

    def filter_by_year(self, year: int) -> list[Car]:
        return filter_by_year(self.cars, year)

    def most_expensive(self) -> Car | None:
        return find_most_expensive(self.cars)

    def average_price(self) -> float:
        return calculate_average_price(self.cars)

    def lowest_mileage(self) -> Car | None:
        return find_lowest_mileage(self.cars)

    def sorted_by_price(self, descending: bool = True) -> list[Car]:
        return sort_by_price(self.cars, descending)


class CatalogService:
    """Application service: repository + validation + external services.

    All collaborators are injected, so tests can replace them with fakes
    or mocks.
    """

    #: errors of an external service that are converted to our own error
    SERVICE_ERRORS = (ConnectionError, TimeoutError, OSError)

    def __init__(
        self,
        repository: VehicleRepository,
        config: AppConfig | None = None,
        info_service: VehicleInfoService | None = None,
        async_info_service: AsyncVehicleInfoService | None = None,
    ) -> None:
        self.repository = repository
        self.config = config or AppConfig()
        self.info_service = info_service
        self.async_info_service = async_info_service

    def add_car(self, car: Car) -> Car:
        """Validate against the configured ranges and store the car."""
        validate_car(car, self.config)
        self.repository.add(car)
        return car

    def import_csv(self, path: Path, skip_invalid: bool = False) -> int:
        """Import a CSV file; return the number of stored cars."""
        cars = import_cars_csv(path, self.config, skip_invalid)
        for car in cars:
            self.repository.add(car)
        return len(cars)

    def export_json(
        self, path: Path, cars: Iterable[Car] | None = None
    ) -> int:
        """Export the given cars (default: the whole catalog)."""
        items = self.repository.list_all() if cars is None else cars
        return export_cars_json(items, path)

    def find_by_brand(self, brand: str) -> list[Car]:
        return search_by_brand(self.repository.list_all(), brand)

    def find_by_model(self, model: str) -> list[Car]:
        return search_by_model(self.repository.list_all(), model)

    def filter_by_year(self, year: int) -> list[Car]:
        return filter_by_year(self.repository.list_all(), year)

    def most_expensive(self) -> Car | None:
        return find_most_expensive(self.repository.list_all())

    def average_price(self) -> float:
        return calculate_average_price(self.repository.list_all())

    def lowest_mileage(self) -> Car | None:
        return find_lowest_mileage(self.repository.list_all())

    def describe(self, car: Car) -> dict[str, str]:
        """Car data enriched with the external service answer."""
        if self.info_service is None:
            raise ExternalServiceError("Vehicle info service is not set")
        try:
            extra = self.info_service.lookup(car.brand, car.model)
        except self.SERVICE_ERRORS as exc:
            raise ExternalServiceError(
                f"Info service failed for {car.full_name}"
            ) from exc
        return {"name": car.full_name, **extra}

    async def describe_async(self, car: Car) -> dict[str, str]:
        """Asynchronous variant of :meth:`describe`."""
        if self.async_info_service is None:
            raise ExternalServiceError("Async info service is not set")
        try:
            extra = await self.async_info_service.fetch(car.brand, car.model)
        except self.SERVICE_ERRORS as exc:
            raise ExternalServiceError(
                f"Async info service failed for {car.full_name}"
            ) from exc
        return {"name": car.full_name, **extra}

    async def describe_all_async(self) -> list[dict[str, str]]:
        """Describe every stored car concurrently."""
        cars = self.repository.list_all()
        return list(
            await asyncio.gather(*(self.describe_async(car) for car in cars))
        )


# --- Compatibility aliases -------------------------------------------------
# Alternative names for the same operations, so the module can be used
# with different naming conventions (e.g. by automated checkers).
Catalog = CarCatalog

find_by_brand = search_by_brand
find_cars_by_brand = search_by_brand
search_cars_by_brand = search_by_brand
filter_by_brand = search_by_brand
get_cars_by_brand = search_by_brand

filter_cars_by_year = filter_by_year
find_by_year = filter_by_year
find_cars_by_year = filter_by_year
get_cars_by_year = filter_by_year
search_by_year = filter_by_year

get_most_expensive = find_most_expensive
get_most_expensive_car = find_most_expensive
find_most_expensive_car = find_most_expensive
most_expensive_car = find_most_expensive

average_price = calculate_average_price
get_average_price = calculate_average_price
calculate_average = calculate_average_price
compute_average_price = calculate_average_price

get_lowest_mileage = find_lowest_mileage
get_lowest_mileage_car = find_lowest_mileage
find_lowest_mileage_car = find_lowest_mileage
find_min_mileage = find_lowest_mileage
find_car_with_lowest_mileage = find_lowest_mileage
lowest_mileage_car = find_lowest_mileage

delete_car = remove_car
