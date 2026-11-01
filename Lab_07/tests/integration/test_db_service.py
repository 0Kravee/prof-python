"""Integration: CarDatabaseService (service layer + repositories + DB)."""

import pytest
from sqlalchemy.orm import Session, sessionmaker

from car_catalog.config import AppConfig
from car_catalog.db_services import CarDatabaseService
from car_catalog.exceptions import (
    DuplicateRecordError,
    InvalidCarDataError,
    RecordNotFoundError,
)

pytestmark = pytest.mark.integration


def test_full_crud_scenario_through_the_service(service) -> None:
    service.add_manufacturer("Skoda", "Czechia")
    created = service.add_car("skoda", "Octavia", 2020, 17000.0, 30000)
    assert service.get_car(created.id).manufacturer.name == "Skoda"

    service.update_price(created.id, 16500.0)
    service.update_mileage(created.id, 31000)
    updated = service.get_car(created.id)
    assert (updated.price, updated.mileage) == (16500.0, 31000)

    service.delete_car(created.id)
    with pytest.raises(RecordNotFoundError):
        service.get_car(created.id)


def test_every_service_call_is_committed(
    service, session_factory: sessionmaker[Session]
) -> None:
    service.add_manufacturer("Skoda")
    service.add_car("Skoda", "Octavia", 2020, 17000.0, 30000)
    with session_factory() as other:
        assert CarDatabaseService(other).cars.count() == 1


def test_configured_year_range_is_applied(
    session: Session, seeded
) -> None:
    modern = CarDatabaseService(session, AppConfig(min_year=2019))
    with pytest.raises(InvalidCarDataError, match="outside 2019"):
        modern.add_car("Audi", "Old", 2010, 1000.0, 1)
    assert modern.cars.count() == 5


def test_configured_price_range_is_applied_to_updates(
    session: Session, seeded
) -> None:
    cheap = CarDatabaseService(session, AppConfig(max_price=30000.0))
    car = cheap.cars.find_by_model("Camry")[0]
    with pytest.raises(InvalidCarDataError, match="Price"):
        cheap.update_price(car.id, 30000.5)
    assert cheap.get_car(car.id).price == 21500.0


def test_add_car_for_unknown_manufacturer(service) -> None:
    with pytest.raises(RecordNotFoundError):
        service.add_car("Ghost", "X", 2020, 1.0, 1)


def test_duplicate_manufacturer_through_the_service(service) -> None:
    service.add_manufacturer("BMW")
    with pytest.raises(DuplicateRecordError):
        service.add_manufacturer("bmw")


def test_delete_unknown_manufacturer(service) -> None:
    with pytest.raises(RecordNotFoundError):
        service.delete_manufacturer("Ghost")


def test_domain_cars_are_lab01_dataclasses(seeded) -> None:
    cars = seeded.domain_cars()
    assert len(cars) == 5
    assert cars[0].full_name == "Toyota Corolla"
    assert cars[0].price == 19800.0
