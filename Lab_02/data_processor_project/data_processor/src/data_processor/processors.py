"""Search, filtering and grouping functions for the car catalog."""

from collections import Counter, defaultdict
from collections.abc import Callable


def get_unique_brands(cars: list[dict]) -> set[str]:
    """set comprehension: unique brands present in the catalog."""
    return {car["brand"] for car in cars}


def get_unique_brand_model_pairs(cars: list[dict]) -> set[tuple[str, str]]:
    """set of tuple: unique (brand, model) combinations."""
    return {(car["brand"], car["model"]) for car in cars}


def create_car_index(cars: list[dict]) -> dict[int, dict]:
    """dict comprehension: build an id -> car index for O(1) average search."""
    return {car["id"]: car for car in cars}


def filter_by_year(cars: list[dict], year: int) -> list[dict]:
    """list comprehension: cars manufactured in the given year."""
    return [car for car in cars if car["year"] == year]


def filter_items(items: list[dict], predicate: Callable[[dict], bool]) -> list[dict]:
    """Universal higher-order filter: works with any predicate function."""
    return [item for item in items if predicate(item)]


def group_by_brand(cars: list[dict]) -> dict[str, list[dict]]:
    """Group cars by brand using collections.defaultdict."""
    grouped: defaultdict[str, list[dict]] = defaultdict(list)
    for car in cars:
        grouped[car["brand"]].append(car)
    return dict(grouped)


def group_by_brand_and_year(cars: list[dict]) -> dict[str, dict[int, list[dict]]]:
    """Nested grouping: brand -> year -> list of cars."""
    grouped: defaultdict[str, defaultdict[int, list[dict]]] = defaultdict(lambda: defaultdict(list))
    for car in cars:
        grouped[car["brand"]][car["year"]].append(car)
    return {brand: dict(years) for brand, years in grouped.items()}


def count_cars_by_brand(cars: list[dict]) -> Counter:
    """Aggregate the number of cars per brand with collections.Counter."""
    return Counter(car["brand"] for car in cars)
