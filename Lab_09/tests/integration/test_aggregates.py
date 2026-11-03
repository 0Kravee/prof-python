"""Integration: COUNT, SUM, AVG, MIN, MAX, JOIN and GROUP BY."""

import pytest

pytestmark = pytest.mark.integration


def test_most_expensive_car(seeded) -> None:
    car = seeded.most_expensive()
    assert (car.manufacturer.name, car.model) == ("BMW", "X5")


def test_lowest_mileage_car(seeded) -> None:
    assert seeded.lowest_mileage().model == "Corolla"


def test_average_price(seeded) -> None:
    assert seeded.average_price() == pytest.approx(28700.0)


def test_statistics_use_count_sum_avg_min_max(seeded) -> None:
    stats = seeded.cars.statistics()
    assert stats == {
        "count": 5,
        "total_price": pytest.approx(143500.0),
        "average_price": pytest.approx(28700.0),
        "min_price": 19800.0,
        "max_price": 48200.0,
    }


def test_empty_database_gives_neutral_aggregates(service) -> None:
    assert service.most_expensive() is None
    assert service.lowest_mileage() is None
    assert service.average_price() == 0.0
    assert service.cars.statistics()["count"] == 0
    assert service.cars.stats_by_manufacturer() == []


def test_group_by_manufacturer(seeded) -> None:
    rows = seeded.cars.stats_by_manufacturer()
    assert [(name, count) for name, count, _ in rows] == [
        ("Audi", 1),
        ("BMW", 2),
        ("Toyota", 2),
    ]
    averages = {name: average for name, _, average in rows}
    assert averages["BMW"] == pytest.approx(39600.0)
    assert averages["Toyota"] == pytest.approx(20650.0)


def test_manufacturer_without_cars_is_not_in_group_by_join(seeded) -> None:
    seeded.add_manufacturer("Tesla", "USA")
    names = [row[0] for row in seeded.cars.stats_by_manufacturer()]
    assert "Tesla" not in names  # inner JOIN: only manufacturers with cars


def test_ties_are_resolved_by_the_lowest_id(seeded) -> None:
    first = seeded.add_car("Audi", "A6", 2020, 48200.0, 100)
    assert seeded.most_expensive().model == "X5"  # same price, lower id
    assert first.id > seeded.most_expensive().id
