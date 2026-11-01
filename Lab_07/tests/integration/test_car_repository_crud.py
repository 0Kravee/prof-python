"""Integration: CRUD of CarRepository (Create, Read, Update, Delete)."""

import pytest
from sqlalchemy.orm import Session, sessionmaker

from car_catalog.exceptions import InvalidCarDataError, RecordNotFoundError
from car_catalog.repositories import CarRepository

pytestmark = pytest.mark.integration


@pytest.fixture
def bmw(manufacturer_repo):
    return manufacturer_repo.add("BMW", "Germany")


# --- Create -----------------------------------------------------------


def test_create_car_stores_all_fields(car_repo, bmw) -> None:
    car = car_repo.add(bmw, "X5", 2021, 48200.0, 18000, "5UXKR0C58J0000003")
    assert car.id is not None
    assert (car.model, car.year, car.price, car.mileage) == (
        "X5", 2021, 48200.0, 18000,
    )
    assert car.vin == "5UXKR0C58J0000003"


def test_created_car_is_linked_to_its_manufacturer(car_repo, bmw) -> None:
    car = car_repo.add(bmw, "X5", 2021, 48200.0, 18000)
    assert car.manufacturer is bmw
    assert car.manufacturer_id == bmw.id
    assert bmw.cars == [car]


def test_vin_is_normalized_to_upper_case(car_repo, bmw) -> None:
    car = car_repo.add(bmw, "X5", 2021, 1.0, 1, " 5uxkr0c58j0000003 ")
    assert car.vin == "5UXKR0C58J0000003"


@pytest.mark.parametrize(
    "kwargs",
    [
        {"year": 1800},
        {"price": -1.0},
        {"mileage": -5},
        {"model": "  "},
        {"vin": "SHORT"},
        {"vin": "5UXKR0C58J000000I"},  # letter I is not allowed in a VIN
    ],
)
def test_invalid_values_are_not_stored(car_repo, bmw, kwargs) -> None:
    values = {"model": "X5", "year": 2021, "price": 1.0, "mileage": 1}
    values.update(kwargs)
    with pytest.raises(InvalidCarDataError):
        car_repo.add(bmw, **values)
    assert car_repo.count() == 0


# --- Read -------------------------------------------------------------


def test_read_car_in_another_session(
    session: Session, session_factory: sessionmaker[Session], car_repo, bmw
) -> None:
    car = car_repo.add(bmw, "X5", 2021, 48200.0, 18000)
    session.commit()
    with session_factory() as other:
        loaded = CarRepository(other).get(car.id)
        assert loaded.model == "X5"
        assert loaded.manufacturer.name == "BMW"


def test_uncommitted_car_is_invisible_to_other_sessions(
    session_factory: sessionmaker[Session], car_repo, bmw
) -> None:
    car_repo.add(bmw, "X5", 2021, 48200.0, 18000)  # no commit
    with session_factory() as other:
        assert CarRepository(other).count() == 0


def test_get_missing_car_raises(car_repo) -> None:
    with pytest.raises(RecordNotFoundError, match="Car 77"):
        car_repo.get(77)


def test_list_all_is_ordered_by_id(seeded) -> None:
    ids = [car.id for car in seeded.cars.list_all()]
    assert ids == sorted(ids)
    assert len(ids) == 5


# --- Update -----------------------------------------------------------


def test_update_price_and_mileage_are_persisted(
    seeded, session_factory: sessionmaker[Session]
) -> None:
    car = seeded.cars.find_by_model("Camry")[0]
    seeded.update_price(car.id, 19999.99)
    seeded.update_mileage(car.id, 46000)
    with session_factory() as other:
        reloaded = CarRepository(other).get(car.id)
        assert reloaded.price == pytest.approx(19999.99)
        assert reloaded.mileage == 46000


def test_invalid_update_keeps_old_value(seeded) -> None:
    car = seeded.cars.find_by_model("Camry")[0]
    with pytest.raises(InvalidCarDataError):
        seeded.update_price(car.id, -10.0)
    with pytest.raises(InvalidCarDataError):
        seeded.update_mileage(car.id, -1)
    assert seeded.get_car(car.id).price == 21500.0
    assert seeded.get_car(car.id).mileage == 45000


def test_update_missing_car_raises(seeded) -> None:
    with pytest.raises(RecordNotFoundError):
        seeded.update_price(999, 100.0)


def test_set_vin_for_a_car_without_one(car_repo, bmw) -> None:
    car = car_repo.add(bmw, "X5", 2021, 48200.0, 18000)
    car_repo.set_vin(car.id, "5uxkr0c58j0000003")
    assert car_repo.find_by_vin("5UXKR0C58J0000003").id == car.id


# --- Delete -----------------------------------------------------------


def test_delete_car(seeded) -> None:
    car = seeded.cars.find_by_model("A4")[0]
    seeded.delete_car(car.id)
    assert seeded.cars.count() == 4
    with pytest.raises(RecordNotFoundError):
        seeded.get_car(car.id)


def test_deleting_twice_fails_the_second_time(seeded) -> None:
    car = seeded.cars.find_by_model("A4")[0]
    seeded.delete_car(car.id)
    with pytest.raises(RecordNotFoundError):
        seeded.delete_car(car.id)


def test_deleting_a_car_keeps_the_manufacturer(seeded) -> None:
    car = seeded.cars.find_by_model("A4")[0]
    seeded.delete_car(car.id)
    assert seeded.manufacturers.get_by_name("Audi") is not None
