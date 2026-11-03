"""Unit tests of the cached statistics and cache invalidation."""

import threading

import pytest

from car_catalog import analytics as an
from car_catalog.caching import CatalogAnalytics
from car_catalog.datagen import generate_cars
from car_catalog.exceptions import CarNotFoundError, InvalidCarDataError


@pytest.fixture
def catalog() -> CatalogAnalytics:
    return CatalogAnalytics(generate_cars(2000, seed=5))


def test_values_match_the_reference_computation(catalog) -> None:
    reference = an.manufacturer_statistics_python(catalog._cars)
    for brand, expected in reference.items():
        got = catalog.brand_statistics(brand)
        assert got.count == expected.count
        assert got.average_price == pytest.approx(expected.average_price)
        assert got.total_value == pytest.approx(expected.total_value)


def test_first_call_is_a_miss_and_next_calls_are_hits(catalog) -> None:
    catalog.brand_statistics("BMW")
    catalog.brand_statistics("BMW")
    catalog.brand_statistics("BMW")
    assert catalog.cache_info() == (2, 1, 1)


def test_brand_name_is_case_and_space_insensitive(catalog) -> None:
    first = catalog.brand_statistics("BMW")
    second = catalog.brand_statistics("  bmw ")
    assert first == second
    assert catalog.cache_info()[0] == 1  # the second call was a hit


def test_unknown_brand_gives_empty_statistics(catalog) -> None:
    stats = catalog.brand_statistics("Tesla")
    assert (stats.count, stats.average_price, stats.total_value) == (
        0, 0.0, 0.0,
    )


def test_cached_value_is_immutable(catalog) -> None:
    stats = catalog.brand_statistics("BMW")
    with pytest.raises(AttributeError):
        stats.count = 0  # type: ignore[misc]


def test_cache_size_is_limited() -> None:
    catalog = CatalogAnalytics(generate_cars(500), max_cache_size=2)
    for brand in ("BMW", "Audi", "Kia", "Opel"):
        catalog.brand_statistics(brand)
    assert catalog.cache_info()[2] == 2


# --- invalidation: a stale value must never be returned ---------------


def test_add_car_invalidates_the_cache(catalog, car_factory) -> None:
    before = catalog.brand_statistics("BMW")
    catalog.add_car(car_factory(brand="BMW", model="M3", year=2026,
                                price=99_999.0, mileage=0))
    after = catalog.brand_statistics("BMW")
    assert after.count == before.count + 1
    assert after.total_value > before.total_value


def test_update_price_invalidates_the_cache(catalog) -> None:
    model = next(c.model for c in catalog._cars if c.brand == "BMW")
    before = catalog.brand_statistics("BMW")
    catalog.update_price("BMW", model, 1.0)
    after = catalog.brand_statistics("BMW")
    assert after.average_price != before.average_price
    reference = an.manufacturer_statistics_python(catalog._cars)["BMW"]
    assert after.average_price == pytest.approx(reference.average_price)


def test_remove_car_invalidates_the_cache(catalog) -> None:
    car = next(c for c in catalog._cars if c.brand == "Audi")
    before = catalog.brand_statistics("Audi")
    catalog.remove_car("audi", car.model)
    assert catalog.brand_statistics("Audi").count == before.count - 1


def test_replace_cars_invalidates_the_cache(catalog) -> None:
    catalog.brand_statistics("BMW")
    catalog.replace_cars([])
    assert catalog.brand_statistics("BMW").count == 0
    assert len(catalog) == 0


def test_other_brands_are_recomputed_correctly_after_a_change(
    catalog, car_factory
) -> None:
    audi_before = catalog.brand_statistics("Audi")
    catalog.add_car(car_factory(brand="BMW", model="M3", year=2026,
                                price=1.0, mileage=0))
    assert catalog.brand_statistics("Audi") == audi_before  # same data


def test_every_change_increases_the_version(catalog, car_factory) -> None:
    version = catalog.version
    catalog.add_car(car_factory())
    assert catalog.version == version + 1
    catalog.invalidate()
    assert catalog.version == version + 2


def test_failed_update_does_not_change_data_or_invalidate(catalog) -> None:
    model = next(c.model for c in catalog._cars if c.brand == "BMW")
    before = catalog.brand_statistics("BMW")
    version = catalog.version
    with pytest.raises(InvalidCarDataError):
        catalog.update_price("BMW", model, -5.0)
    assert catalog.version == version
    assert catalog.brand_statistics("BMW") == before


@pytest.mark.parametrize("action", ["remove", "update"])
def test_missing_car_is_reported(catalog, action) -> None:
    with pytest.raises(CarNotFoundError):
        if action == "remove":
            catalog.remove_car("Tesla", "S")
        else:
            catalog.update_price("Tesla", "S", 1.0)


# --- threads ------------------------------------------------------------


def test_cache_is_safe_when_threads_read_and_write(
    catalog, car_factory
) -> None:
    errors: list[BaseException] = []

    def reader() -> None:
        try:
            for _ in range(200):
                assert catalog.brand_statistics("BMW").count >= 0
        except BaseException as exc:  # reported below
            errors.append(exc)

    def writer() -> None:
        try:
            for index in range(20):
                catalog.add_car(car_factory(brand="BMW", model=f"T{index}"))
        except BaseException as exc:
            errors.append(exc)

    threads = [threading.Thread(target=reader) for _ in range(4)]
    threads.append(threading.Thread(target=writer))
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert errors == []
    reference = an.manufacturer_statistics_python(catalog._cars)["BMW"]
    assert catalog.brand_statistics("BMW").count == reference.count
