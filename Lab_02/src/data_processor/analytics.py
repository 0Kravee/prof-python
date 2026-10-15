"""Aggregation and higher-order analytics functions for the car catalog."""

from collections.abc import Callable
from typing import Any

from data_processor.decorators import measure_time


@measure_time
def calculate_average_price(cars: list[dict]) -> float:
    """Average price via a generator expression (no intermediate list)."""
    if not cars:
        return 0.0
    return sum(car["price"] for car in cars) / len(cars)


def find_most_expensive(cars: list[dict]) -> dict | None:
    """lambda used as the sorting/selection key."""
    return max(cars, key=lambda car: car["price"], default=None)


def find_lowest_mileage(cars: list[dict]) -> dict | None:
    return min(cars, key=lambda car: car["mileage"], default=None)


def sort_by_price(cars: list[dict], reverse: bool = True) -> list[dict]:
    return sorted(cars, key=lambda car: car["price"], reverse=reverse)


def sort_items(
    items: list[dict], key: Callable[[dict], Any], reverse: bool = False
) -> list[dict]:
    """Universal sorting helper: works with any key function."""
    return sorted(items, key=key, reverse=reverse)


def calculate_average_values(*values: float) -> float:
    """*args: accepts any number of positional numeric values."""
    if not values:
        return 0.0
    return sum(values) / len(values)


def create_car_record(**fields) -> dict:
    """**kwargs: build a car record from arbitrary keyword arguments."""
    return dict(fields)


def create_year_filter(min_year: int) -> Callable[[dict], bool]:
    """Closure: `predicate` keeps access to `min_year` after the call."""

    def predicate(car: dict) -> bool:
        return car["year"] >= min_year

    return predicate


def find_linear(cars: list[dict], car_id: int) -> dict | None:
    """Linear search used as a baseline for the benchmark section."""
    for car in cars:
        if car["id"] == car_id:
            return car
    return None


# --- Compatibility aliases (alternative names for the same operations) ----
calculate_average = calculate_average_price
get_average_price = calculate_average_price
get_most_expensive = find_most_expensive
find_most_expensive_car = find_most_expensive
get_lowest_mileage = find_lowest_mileage
find_lowest_mileage_car = find_lowest_mileage
create_record = create_car_record
create_filter = create_year_filter
