"""Analytics of a large car catalog: pure Python and NumPy versions.

The "manufacturer statistics" operation computes, for every brand, the
number of cars, average price, average mileage and the total estimated
market value. The value of one car is its price depreciated for every
year of age and reduced for high mileage (see :func:`estimated_value`).
"""

from collections.abc import Iterable
from dataclasses import dataclass
from math import sqrt
from typing import Any

import numpy as np
from numpy.typing import NDArray

from car_catalog.models import Car
from car_catalog.services import (
    calculate_average_price,
    filter_by_year,
    find_most_expensive,
    search_by_brand,
)

CURRENT_YEAR = 2026
DEPRECIATION_RATE = 0.12  # lost every year, compounded monthly
MONTHS_PER_YEAR = 12
MILEAGE_PENALTY_PER_KM = 1e-6
MIN_MILEAGE_FACTOR = 0.5


@dataclass(frozen=True, slots=True)
class BrandStats:
    """Statistics of one manufacturer."""

    brand: str
    count: int
    average_price: float
    average_mileage: float
    total_value: float


@dataclass(frozen=True, slots=True)
class MileageStats:
    count: int
    minimum: int
    maximum: int
    mean: float
    std: float


# --- the CPU-bound part -------------------------------------------------


def estimated_value(
    year: int, price: float, mileage: int, current_year: int = CURRENT_YEAR
) -> float:
    """Price after monthly depreciation and a mileage discount.

    A deliberately CPU-bound loop: one multiplication per month of age.
    """
    value = price
    monthly = 1.0 - DEPRECIATION_RATE / MONTHS_PER_YEAR
    for _ in range(max(current_year - year, 0) * MONTHS_PER_YEAR):
        value *= monthly
    factor = 1.0 - mileage * MILEAGE_PENALTY_PER_KM
    return value * max(MIN_MILEAGE_FACTOR, factor)


# --- pure Python (baseline) --------------------------------------------

# Partial results are lists [count, price_sum, mileage_sum, value_sum] so
# that chunks processed by different threads/processes can be merged.
Partial = dict[str, list[float]]


def partial_manufacturer_statistics(cars: Iterable[Car]) -> Partial:
    """Aggregate one chunk of cars (the unit of work for parallel code)."""
    partial: Partial = {}
    for car in cars:
        entry = partial.get(car.brand)
        if entry is None:
            entry = partial[car.brand] = [0.0, 0.0, 0.0, 0.0]
        entry[0] += 1
        entry[1] += car.price
        entry[2] += car.mileage
        entry[3] += estimated_value(car.year, car.price, car.mileage)
    return partial


def merge_partials(parts: Iterable[Partial]) -> Partial:
    merged: Partial = {}
    for part in parts:
        for brand, values in part.items():
            entry = merged.setdefault(brand, [0.0, 0.0, 0.0, 0.0])
            for index, value in enumerate(values):
                entry[index] += value
    return merged


def finalize_statistics(partial: Partial) -> dict[str, BrandStats]:
    return {
        brand: BrandStats(
            brand=brand,
            count=int(count),
            average_price=price_sum / count,
            average_mileage=mileage_sum / count,
            total_value=value_sum,
        )
        for brand, (count, price_sum, mileage_sum, value_sum) in sorted(
            partial.items()
        )
    }


def manufacturer_statistics_python(
    cars: Iterable[Car],
) -> dict[str, BrandStats]:
    return finalize_statistics(partial_manufacturer_statistics(cars))


def mileage_statistics_python(cars: list[Car]) -> MileageStats:
    """Count, min, max, mean and (population) standard deviation."""
    if not cars:
        return MileageStats(0, 0, 0, 0.0, 0.0)
    total = 0
    lowest = highest = cars[0].mileage
    for car in cars:
        mileage = car.mileage
        total += mileage
        if mileage < lowest:
            lowest = mileage
        if mileage > highest:
            highest = mileage
    mean = total / len(cars)
    squares = 0.0
    for car in cars:
        squares += (car.mileage - mean) ** 2
    return MileageStats(
        len(cars), lowest, highest, mean, sqrt(squares / len(cars))
    )


# The simple Lab_01 operations stay the baseline for their NumPy versions.
search_by_brand_python = search_by_brand
filter_by_year_python = filter_by_year
average_price_python = calculate_average_price
most_expensive_python = find_most_expensive


# --- NumPy (vectorized) ------------------------------------------------


@dataclass(slots=True)
class CarColumns:
    """Column-oriented copy of a catalog (one NumPy array per field)."""

    brand_names: tuple[str, ...]
    brands: NDArray[np.int32]
    years: NDArray[np.int32]
    prices: NDArray[np.float64]
    mileages: NDArray[np.int64]

    def __len__(self) -> int:
        return int(self.prices.shape[0])


def to_columns(cars: list[Car]) -> CarColumns:
    """Convert objects to arrays (this has a cost: it is benchmarked)."""
    names = tuple(sorted({car.brand for car in cars}))
    codes = {name: index for index, name in enumerate(names)}
    return CarColumns(
        brand_names=names,
        brands=np.fromiter(
            (codes[car.brand] for car in cars), np.int32, len(cars)
        ),
        years=np.fromiter((car.year for car in cars), np.int32, len(cars)),
        prices=np.fromiter((car.price for car in cars), np.float64, len(cars)),
        mileages=np.fromiter(
            (car.mileage for car in cars), np.int64, len(cars)
        ),
    )


def estimated_values_numpy(columns: CarColumns) -> NDArray[np.float64]:
    """Vectorized :func:`estimated_value` for the whole catalog."""
    months = np.maximum(CURRENT_YEAR - columns.years, 0) * MONTHS_PER_YEAR
    monthly = 1.0 - DEPRECIATION_RATE / MONTHS_PER_YEAR
    depreciated = columns.prices * monthly**months
    factor = np.maximum(
        MIN_MILEAGE_FACTOR, 1.0 - columns.mileages * MILEAGE_PENALTY_PER_KM
    )
    return np.asarray(depreciated * factor, dtype=np.float64)


def manufacturer_statistics_numpy(
    columns: CarColumns,
) -> dict[str, BrandStats]:
    size = len(columns.brand_names)
    counts = np.bincount(columns.brands, minlength=size)
    price_sums = np.bincount(columns.brands, columns.prices, size)
    mileage_sums = np.bincount(columns.brands, columns.mileages, size)
    value_sums = np.bincount(
        columns.brands, estimated_values_numpy(columns), size
    )
    return {
        name: BrandStats(
            brand=name,
            count=int(counts[code]),
            average_price=float(price_sums[code] / counts[code]),
            average_mileage=float(mileage_sums[code] / counts[code]),
            total_value=float(value_sums[code]),
        )
        for code, name in enumerate(columns.brand_names)
        if counts[code]
    }


def mileage_statistics_numpy(columns: CarColumns) -> MileageStats:
    if len(columns) == 0:
        return MileageStats(0, 0, 0, 0.0, 0.0)
    mileages = columns.mileages
    return MileageStats(
        len(columns),
        int(np.min(mileages)),
        int(np.max(mileages)),
        float(mileages.mean()),
        float(mileages.std()),
    )


def average_price_numpy(columns: CarColumns) -> float:
    return float(columns.prices.mean()) if len(columns) else 0.0


def most_expensive_index_numpy(columns: CarColumns) -> int | None:
    if len(columns) == 0:
        return None
    return int(np.argmax(columns.prices))


def filter_by_year_numpy(columns: CarColumns, year: int) -> NDArray[np.intp]:
    """Indexes of the cars of the given year."""
    return np.flatnonzero(columns.years == year)


def search_by_brand_numpy(columns: CarColumns, brand: str) -> NDArray[np.intp]:
    """Indexes of the cars of a brand (case-insensitive)."""
    wanted = brand.strip().lower()
    codes = [
        code
        for code, name in enumerate(columns.brand_names)
        if name.lower() == wanted
    ]
    if not codes:
        return np.empty(0, dtype=np.intp)
    return np.flatnonzero(np.isin(columns.brands, codes))


# --- comparing results --------------------------------------------------


def statistics_close(
    left: dict[str, BrandStats],
    right: dict[str, BrandStats],
    rel_tol: float = 1e-9,
) -> bool:
    """Floating point results are compared with a tolerance."""
    if left.keys() != right.keys():
        return False
    for brand, a in left.items():
        b = right[brand]
        if a.count != b.count:
            return False
        pairs: tuple[tuple[Any, Any], ...] = (
            (a.average_price, b.average_price),
            (a.average_mileage, b.average_mileage),
            (a.total_value, b.total_value),
        )
        if not all(
            abs(x - y) <= rel_tol * max(abs(x), abs(y), 1.0) for x, y in pairs
        ):
            return False
    return True
