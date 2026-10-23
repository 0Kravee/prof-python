"""Tests for the VehicleCatalog collection."""

import pytest

from domain_app.criteria import BrandCriteria
from domain_app.exceptions import DuplicateEntityError, EntityNotFoundError
from domain_app.models import Car, ElectricCar, Vehicle, VehicleCatalog
from domain_app.value_objects import Money


def test_collection_protocol(vehicles: list[Vehicle]) -> None:
    catalog = VehicleCatalog(vehicles)
    assert len(catalog) == 5
    assert [v.vehicle_id for v in catalog] == [1, 2, 3, 4, 5]
    assert catalog[0].vehicle_id == 1 and catalog[-1].vehicle_id == 5
    assert [v.vehicle_id for v in catalog[1:3]] == [2, 3]
    assert vehicles[0] in catalog and 3 in catalog
    assert 99 not in catalog and "text" not in catalog
    assert repr(catalog) == "VehicleCatalog(5 vehicles)"


def test_add_get_remove(vehicles: list[Vehicle]) -> None:
    catalog = VehicleCatalog(vehicles[:2])
    catalog.add(vehicles[2])
    catalog.extend([vehicles[3]])
    assert len(catalog) == 4
    with pytest.raises(DuplicateEntityError):
        catalog.add(vehicles[0])
    assert catalog.get(2) is vehicles[1]
    assert catalog.remove(2) is vehicles[1] and 2 not in catalog
    with pytest.raises(EntityNotFoundError):
        catalog.get(2)
    with pytest.raises(LookupError):
        catalog.remove(2)


def test_domain_queries(vehicles: list[Vehicle]) -> None:
    catalog = VehicleCatalog(vehicles)
    expensive = catalog.most_expensive()
    lowest = catalog.lowest_mileage()
    assert expensive is not None and expensive.model == "X5"
    assert lowest is not None and lowest.model == "Corolla"
    assert catalog.total_value() == Money.of(153500)
    assert catalog.average_price() == Money.of(30700)
    prices = [v.price for v in catalog.sorted_by_price()]
    assert prices == sorted(prices, reverse=True)
    ascending = [v.price for v in catalog.sorted_by_price(False)]
    assert ascending == sorted(ascending)


def test_empty_catalog() -> None:
    catalog = VehicleCatalog()
    assert not len(catalog)
    assert catalog.most_expensive() is None
    assert catalog.lowest_mileage() is None
    assert catalog.average_price() == Money.zero()
    assert catalog.total_value() == Money.zero()


def test_filter_returns_new_catalog(vehicles: list[Vehicle]) -> None:
    catalog = VehicleCatalog(vehicles)
    toyotas = catalog.filter(BrandCriteria("toyota"))
    assert isinstance(toyotas, VehicleCatalog) and len(toyotas) == 2
    assert len(catalog) == 5


def test_of_type_preserves_exact_type(vehicles: list[Vehicle]) -> None:
    catalog = VehicleCatalog(vehicles)
    electric: list[ElectricCar] = catalog.of_type(ElectricCar)
    assert [car.battery_kwh for car in electric] == [75]
    assert len(catalog.of_type(Car)) == 5  # ElectricCar is-a Car
