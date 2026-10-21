"""Validation and filtering stages."""

from collections import Counter
from collections.abc import Callable, Iterable, Iterator

from stream_processor.models import CarRecord

MIN_YEAR = 1900
MAX_YEAR = 2030


def validate_row(row: dict[str, str]) -> CarRecord | None:
    """Validate a single CSV row; return None when the row is invalid."""
    try:
        car_id = int(row["id"])
        brand = row["brand"].strip()
        model = row["model"].strip()
        year = int(row["year"])
        price = float(row["price"])
        mileage = int(row["mileage"])
    except (ValueError, TypeError, KeyError, AttributeError):
        return None

    if car_id <= 0 or not brand or not model:
        return None
    if not MIN_YEAR <= year <= MAX_YEAR:
        return None
    if price <= 0 or mileage < 0:
        return None
    return CarRecord(car_id, brand, model, year, price, mileage)


def validate_cars(
    rows: Iterable[dict[str, str]],
    stats: Counter | None = None,
) -> Iterator[CarRecord]:
    """Validation stage (generator).

    Invalid rows are skipped; when `stats` is given, valid/invalid
    records are counted on the fly.
    """
    for row in rows:
        record = validate_row(row)
        if record is None:
            if stats is not None:
                stats["invalid"] += 1
            continue
        if stats is not None:
            stats["valid"] += 1
        yield record


def filter_by_brand(
    cars: Iterable[CarRecord], brand: str
) -> Iterator[CarRecord]:
    """Lazy filter by brand (case-insensitive)."""
    wanted = brand.lower()
    for car in cars:
        if car.brand.lower() == wanted:
            yield car


def filter_by_year(
    cars: Iterable[CarRecord], year: int
) -> Iterator[CarRecord]:
    """Lazy filter by exact manufacturing year."""
    for car in cars:
        if car.year == year:
            yield car


def filter_by_min_year(
    cars: Iterable[CarRecord], min_year: int
) -> Iterator[CarRecord]:
    """Lazy filter: cars not older than `min_year`."""
    for car in cars:
        if car.year >= min_year:
            yield car


def filter_cars(
    cars: Iterable[CarRecord],
    predicate: Callable[[CarRecord], bool],
) -> Iterator[CarRecord]:
    """Universal lazy filter built on a generator expression."""
    return (car for car in cars if predicate(car))
