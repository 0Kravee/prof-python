"""Business logic for the car catalog laboratory project."""

from car_catalog.models import Car


def search_by_brand(cars: list[Car], brand: str) -> list[Car]:
    """Return all cars matching the given brand (case-insensitive)."""
    return [car for car in cars if car.brand.lower() == brand.lower()]


def filter_by_year(cars: list[Car], year: int) -> list[Car]:
    """Return all cars manufactured in the given year."""
    return [car for car in cars if car.year == year]


def find_most_expensive(cars: list[Car]) -> Car | None:
    """Return the car with the highest price, or None if the list is empty."""
    return max(cars, key=lambda car: car.price, default=None)


def calculate_average_price(cars: list[Car]) -> float:
    """Return the average price of the given cars, or 0.0 if the list is empty."""
    if not cars:
        return 0.0
    return sum(car.price for car in cars) / len(cars)


def find_lowest_mileage(cars: list[Car]) -> Car | None:
    """Return the car with the lowest mileage, or None if the list is empty."""
    return min(cars, key=lambda car: car.mileage, default=None)


def sort_by_price(cars: list[Car], descending: bool = True) -> list[Car]:
    """Return cars sorted by price (descending by default)."""
    return sorted(cars, key=lambda car: car.price, reverse=descending)
