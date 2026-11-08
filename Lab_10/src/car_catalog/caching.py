"""Cached brand statistics with invalidation after data changes."""

import threading
from collections.abc import Iterable
from functools import lru_cache

from car_catalog.analytics import BrandStats, estimated_value
from car_catalog.exceptions import CarNotFoundError
from car_catalog.models import Car


class CatalogAnalytics:
    """A mutable catalog whose brand statistics are cached.

    Statistics are computed by a full scan of the catalog (O(n)). The
    result is stored in an ``lru_cache``; every change of the data
    clears it, so a stale value can never be returned.
    """

    def __init__(
        self, cars: Iterable[Car] = (), max_cache_size: int = 256
    ) -> None:
        self._cars: list[Car] = list(cars)
        self._lock = threading.RLock()
        self._version = 0
        self._cached = lru_cache(maxsize=max_cache_size)(self._compute)

    # --- reading -------------------------------------------------------

    def __len__(self) -> int:
        return len(self._cars)

    @property
    def version(self) -> int:
        """Increases with every change of the data."""
        return self._version

    def brand_statistics(self, brand: str) -> BrandStats:
        """Cached statistics of one brand (case-insensitive)."""
        with self._lock:
            return self._cached(brand.strip().lower(), self._version)

    def cache_info(self) -> tuple[int, int, int]:
        """(hits, misses, current size)."""
        info = self._cached.cache_info()
        return info.hits, info.misses, info.currsize

    def _compute(self, brand_key: str, version: int) -> BrandStats:
        # ``version`` is part of the cache key: an old entry can never match
        count = 0
        price_sum = 0.0
        mileage_sum = 0.0
        value_sum = 0.0
        name = brand_key
        for car in self._cars:
            if car.brand.lower() != brand_key:
                continue
            name = car.brand
            count += 1
            price_sum += car.price
            mileage_sum += car.mileage
            value_sum += estimated_value(car.year, car.price, car.mileage)
        if count == 0:
            return BrandStats(name, 0, 0.0, 0.0, 0.0)
        return BrandStats(
            name, count, price_sum / count, mileage_sum / count, value_sum
        )

    # --- changing the data (always invalidates) ------------------------

    def invalidate(self) -> None:
        with self._lock:
            self._version += 1
            self._cached.cache_clear()

    def add_car(self, car: Car) -> None:
        with self._lock:
            self._cars.append(car)
            self.invalidate()

    def remove_car(self, brand: str, model: str) -> Car:
        with self._lock:
            for index, car in enumerate(self._cars):
                if (
                    car.brand.lower() == brand.strip().lower()
                    and car.model.lower() == model.strip().lower()
                ):
                    removed = self._cars.pop(index)
                    self.invalidate()
                    return removed
        raise CarNotFoundError(f"Car {brand} {model} was not found")

    def update_price(self, brand: str, model: str, price: float) -> Car:
        """Replace the car by a validated copy with a new price."""
        with self._lock:
            for index, car in enumerate(self._cars):
                if (
                    car.brand.lower() == brand.strip().lower()
                    and car.model.lower() == model.strip().lower()
                ):
                    updated = Car(
                        car.brand, car.model, car.year, price, car.mileage
                    )
                    self._cars[index] = updated
                    self.invalidate()
                    return updated
        raise CarNotFoundError(f"Car {brand} {model} was not found")

    def replace_cars(self, cars: Iterable[Car]) -> None:
        with self._lock:
            self._cars = list(cars)
            self.invalidate()
