"""Aggregation stages and single-pass analytics."""

from collections import Counter
from collections.abc import Callable, Iterable, Iterator
from itertools import accumulate, groupby, islice, pairwise

from stream_processor.models import CarRecord


def streaming_average_price(cars: Iterable[CarRecord]) -> float:
    """Average price in one pass: O(1) memory, no intermediate list."""
    total = 0.0
    count = 0
    for car in cars:
        total += car.price
        count += 1
    return total / count if count else 0.0


def find_most_expensive(cars: Iterable[CarRecord]) -> CarRecord | None:
    """Most expensive car, found without materialising the stream."""
    best: CarRecord | None = None
    for car in cars:
        if best is None or car.price > best.price:
            best = car
    return best


def find_lowest_mileage(cars: Iterable[CarRecord]) -> CarRecord | None:
    """Car with the lowest mileage, found in a single pass."""
    best: CarRecord | None = None
    for car in cars:
        if best is None or car.mileage < best.mileage:
            best = car
    return best


def calculate_statistics(cars: Iterable[CarRecord]) -> dict:
    """One-pass aggregation stage (count, average/min/max price, brands)."""
    count = 0
    total = 0.0
    min_price: float | None = None
    max_price: float | None = None
    brands: Counter = Counter()
    for car in cars:
        count += 1
        total += car.price
        brands[car.brand] += 1
        if min_price is None or car.price < min_price:
            min_price = car.price
        if max_price is None or car.price > max_price:
            max_price = car.price
    return {
        "count": count,
        "average_price": total / count if count else 0.0,
        "min_price": min_price,
        "max_price": max_price,
        "brands": dict(brands),
    }


def first_n_matching(
    cars: Iterable[CarRecord],
    predicate: Callable[[CarRecord], bool],
    n: int,
) -> list[CarRecord]:
    """First N records matching a condition (stream is cut by islice)."""
    return list(islice((car for car in cars if predicate(car)), n))


def find_first(
    records: Iterable[CarRecord],
    predicate: Callable[[CarRecord], bool],
) -> CarRecord | None:
    """Lazy search with early termination."""
    for record in records:
        if predicate(record):
            return record
    return None


def group_by_brand(
    cars: Iterable[CarRecord],
) -> Iterator[tuple[str, list[CarRecord]]]:
    """itertools.groupby by brand.

    groupby only groups *consecutive* items, therefore the stream is sorted
    by brand first (sorting needs the data in memory - a documented trade-off).
    """
    ordered = sorted(cars, key=lambda car: car.brand)
    for brand, members in groupby(ordered, key=lambda car: car.brand):
        yield brand, list(members)


def running_total_price(cars: Iterable[CarRecord]) -> Iterator[float]:
    """Cumulative price with itertools.accumulate."""
    return accumulate(car.price for car in cars)


def price_differences(cars: Iterable[CarRecord]) -> Iterator[float]:
    """Price change between consecutive cars with itertools.pairwise."""
    prices = (car.price for car in cars)
    return (current - previous for previous, current in pairwise(prices))


def streaming_average(values: Iterable[float]) -> float:
    """Generic one-pass average of any numeric stream."""
    total = 0.0
    count = 0
    for value in values:
        total += value
        count += 1
    return total / count if count else 0.0
