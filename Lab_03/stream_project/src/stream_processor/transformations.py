"""Transformation stages."""

from collections.abc import Iterable, Iterator
from dataclasses import replace

from stream_processor.models import CarRecord

ACRONYM_BRANDS = {"bmw": "BMW", "kia": "KIA", "gmc": "GMC"}


def normalize_brand(brand: str) -> str:
    """Capitalise a brand but keep known acronyms (`bmw` -> `BMW`)."""
    lowered = brand.lower()
    if lowered in ACRONYM_BRANDS:
        return ACRONYM_BRANDS[lowered]
    return brand.title() if brand.islower() else brand


def normalize_cars(cars: Iterable[CarRecord]) -> Iterator[CarRecord]:
    """Transformation stage: normalise brand spelling."""
    for car in cars:
        yield replace(car, brand=normalize_brand(car.brand))


def describe_cars(cars: Iterable[CarRecord]) -> Iterator[str]:
    """Lazy transformation to a short human-readable representation."""
    for car in cars:
        yield (
            f"#{car.car_id} {car.brand} {car.model} ({car.year}) - "
            f"{car.price:.2f}$, {car.mileage} km"
        )
