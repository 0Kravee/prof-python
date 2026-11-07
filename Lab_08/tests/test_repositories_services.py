"""Repository layer (SQL) and service layer (business rules)."""

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from car_catalog.exceptions import (
    ConflictError,
    DuplicateEntityError,
    EntityNotFoundError,
)
from car_catalog.models import Car, Manufacturer
from car_catalog.repositories import (
    CarFilter,
    CarRepository,
    ManufacturerRepository,
)
from car_catalog.schemas import (
    CarCreate,
    CarUpdate,
    ManufacturerCreate,
)
from car_catalog.services import CatalogService

from conftest import CARS


@pytest.fixture
def service(session: Session) -> CatalogService:
    svc = CatalogService(session)
    for payload in CARS:
        svc.create_car(CarCreate.model_validate(payload))
    return svc


# ------------------------------------------------------------- repositories
def test_filtering(service: CatalogService) -> None:
    repo = service.cars
    assert [c.model for c in repo.get_all(CarFilter(brand="bmw"))] == [
        "X5",
        "3 Series",
    ]
    assert [c.model for c in repo.get_all(CarFilter(model="OR"))] == [
        "Corolla"
    ]
    assert len(repo.get_all(CarFilter(year=2022))) == 1
    assert len(repo.get_all(CarFilter(min_year=2020, max_year=2021))) == 2
    assert len(repo.get_all(CarFilter(min_price=30000))) == 2
    assert len(repo.get_all(CarFilter(max_price=21500))) == 2
    assert len(repo.get_all(CarFilter(max_mileage=18000))) == 2
    combined = CarFilter(brand="Toyota", min_year=2020)
    assert [c.model for c in repo.get_all(combined)] == ["Corolla"]
    assert repo.get_all(CarFilter(brand="Ford")) == []


def test_sorting_pagination_and_count(service: CatalogService) -> None:
    repo = service.cars
    prices = [c.price for c in repo.get_all(sort="price", descending=True)]
    assert prices == sorted(prices, reverse=True)
    page = repo.get_all(sort="id", limit=2, offset=1)
    assert [c.id for c in page] == [2, 3]
    assert repo.count() == 5
    assert repo.count(CarFilter(brand="Toyota")) == 2
    assert repo.count(CarFilter(brand="Ford")) == 0
    assert [c.model for c in repo.get_all(sort="model")][:2] == [
        "3 Series",
        "A4",
    ]


def test_aggregates_and_extremes(service: CatalogService) -> None:
    totals = service.cars.aggregates()
    assert (totals.count, totals.min_price, totals.max_price) == (
        5,
        19800.0,
        48200.0,
    )
    assert totals.average_price == 28700.0 and totals.total_value == 143500.0
    expensive = service.cars.most_expensive()
    lowest = service.cars.lowest_mileage()
    assert expensive is not None and expensive.model == "X5"
    assert lowest is not None and lowest.model == "Corolla"


def test_empty_aggregates(session: Session) -> None:
    repo = CarRepository(session)
    totals = repo.aggregates()
    assert (totals.count, totals.average_price) == (0, 0.0)
    assert totals.min_price is None and repo.most_expensive() is None


def test_manufacturer_names_are_unique_ignoring_case(session: Session) -> None:
    repo = ManufacturerRepository(session)
    repo.add(Manufacturer(name="Audi"))
    with pytest.raises(DuplicateEntityError):
        repo.add(Manufacturer(name="AUDI"))
    assert repo.get_by_name("  audi ") is not None
    assert [m.name for m in repo.get_all()] == ["Audi"]  # session usable again


def test_database_constraints_protect_the_data(session: Session) -> None:
    maker = ManufacturerRepository(session).add(Manufacturer(name="X"))
    for bad in (
        Car(
            manufacturer_id=maker.id, model="m", year=1700, price=1, mileage=1
        ),
        Car(
            manufacturer_id=maker.id, model="m", year=2000, price=-1, mileage=1
        ),
        Car(
            manufacturer_id=maker.id, model="m", year=2000, price=1, mileage=-1
        ),
        Car(manufacturer_id=999, model="m", year=2000, price=1, mileage=1),
    ):
        session.add(bad)
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()


# ---------------------------------------------------------------- services
def test_brand_creates_the_manufacturer_once(service: CatalogService) -> None:
    names = [m.name for m in service.list_manufacturers()]
    assert names == ["Audi", "BMW", "Toyota"]
    again = service.create_car(
        CarCreate.model_validate({**CARS[0], "brand": "TOYOTA"})
    )
    assert again.brand == "Toyota" and len(service.list_manufacturers()) == 3


def test_create_with_manufacturer_id(service: CatalogService) -> None:
    payload = {k: v for k, v in CARS[0].items() if k != "brand"}
    car = service.create_car(
        CarCreate.model_validate({**payload, "manufacturer_id": 2})
    )
    assert car.brand == "BMW"
    with pytest.raises(EntityNotFoundError):
        service.create_car(
            CarCreate.model_validate({**payload, "manufacturer_id": 99})
        )


def test_partial_update(service: CatalogService) -> None:
    car = service.update_car(1, CarUpdate(price=20000.0, mileage=46000))
    assert (car.price, car.mileage, car.model) == (20000.0, 46000, "Camry")
    with pytest.raises(EntityNotFoundError):
        service.update_car(99, CarUpdate(price=1.0))


def test_delete_and_missing(service: CatalogService) -> None:
    service.delete_car(1)
    with pytest.raises(EntityNotFoundError):
        service.get_car(1)
    with pytest.raises(EntityNotFoundError):
        service.delete_car(1)


def test_manufacturer_rules(service: CatalogService) -> None:
    with pytest.raises(ConflictError):
        service.delete_manufacturer(1)  # Toyota still has cars
    assert [c.model for c in service.cars_of_manufacturer(2)] == [
        "X5",
        "3 Series",
    ]
    maker = service.create_manufacturer(
        ManufacturerCreate(name="Kia", country="Korea")
    )
    service.delete_manufacturer(maker.id)
    with pytest.raises(EntityNotFoundError):
        service.get_manufacturer(maker.id)
    with pytest.raises(EntityNotFoundError):
        service.cars_of_manufacturer(99)


def test_statistics_and_empty_catalog(
    service: CatalogService, session: Session
) -> None:
    stats = service.statistics()
    assert stats.count == 5 and stats.average_price == 28700.0
    assert stats.most_expensive is not None
    assert stats.most_expensive.model == "X5"
    empty = CatalogService.__new__(CatalogService)
    empty.__init__(session)  # type: ignore[misc]
    for car in list(empty.cars.get_all()):
        empty.cars.delete(car)
    assert empty.statistics().count == 0
    with pytest.raises(EntityNotFoundError):
        empty.most_expensive()
    with pytest.raises(EntityNotFoundError):
        empty.lowest_mileage()
