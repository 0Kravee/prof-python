"""Integration: database constraints (UNIQUE, CHECK, FOREIGN KEY)."""

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from car_catalog.exceptions import DuplicateRecordError, RecordNotFoundError

pytestmark = pytest.mark.integration

INSERT_CAR = text(
    "INSERT INTO cars (manufacturer_id, model, year, price, mileage, vin) "
    "VALUES (:manufacturer_id, 'Test', :year, :price, :mileage, :vin)"
)


def raw_car(**overrides):
    values = {
        "manufacturer_id": 1,
        "year": 2020,
        "price": 1000.0,
        "mileage": 10,
        "vin": None,
    }
    values.update(overrides)
    return values


def test_duplicate_vin_is_rejected_by_the_repository(seeded) -> None:
    with pytest.raises(DuplicateRecordError, match="VIN"):
        seeded.add_car("Audi", "A6", 2020, 1000.0, 1, "5UXKR0C58J0000003")
    assert seeded.cars.count() == 5


def test_duplicate_vin_is_case_insensitive(seeded) -> None:
    with pytest.raises(DuplicateRecordError):
        seeded.add_car("Audi", "A6", 2020, 1000.0, 1, "5uxkr0c58j0000003")


def test_database_itself_enforces_unique_vin(seeded) -> None:
    with pytest.raises(IntegrityError, match="UNIQUE"):
        seeded.session.execute(INSERT_CAR, raw_car(vin="5UXKR0C58J0000003"))
    seeded.session.rollback()


def test_session_stays_usable_after_a_duplicate(seeded) -> None:
    with pytest.raises(DuplicateRecordError):
        seeded.add_car("Audi", "A6", 2020, 1000.0, 1, "5UXKR0C58J0000003")
    seeded.add_car("Audi", "A6", 2020, 1000.0, 1, "WAUZZZ8K9DA000099")
    assert seeded.cars.count() == 6


def test_set_vin_cannot_reuse_an_existing_vin(seeded) -> None:
    car = seeded.cars.find_by_model("A4")[0]
    with pytest.raises(DuplicateRecordError):
        seeded.cars.set_vin(car.id, "5UXKR0C58J0000003")


def test_many_cars_may_have_no_vin(service) -> None:
    service.add_manufacturer("Kia")
    service.add_car("Kia", "Rio", 2020, 9000.0, 100)
    service.add_car("Kia", "Ceed", 2021, 12000.0, 100)
    assert service.cars.count() == 2  # NULL does not violate UNIQUE


def test_manufacturer_name_is_unique_in_the_database(seeded) -> None:
    with pytest.raises(IntegrityError, match="UNIQUE"):
        seeded.session.execute(
            text("INSERT INTO manufacturers (name) VALUES ('BMW')")
        )
    seeded.session.rollback()


@pytest.mark.parametrize(
    ("overrides", "constraint"),
    [
        ({"year": 1500}, "ck_cars_year_range"),
        ({"year": 2200}, "ck_cars_year_range"),
        ({"price": -1.0}, "ck_cars_price_not_negative"),
        ({"mileage": -1}, "ck_cars_mileage_not_negative"),
    ],
)
def test_check_constraints_work_below_the_python_validation(
    seeded, overrides, constraint
) -> None:
    with pytest.raises(IntegrityError, match=constraint):
        seeded.session.execute(INSERT_CAR, raw_car(**overrides))
    seeded.session.rollback()


def test_foreign_key_is_enforced(seeded) -> None:
    with pytest.raises(IntegrityError, match="FOREIGN KEY"):
        seeded.session.execute(INSERT_CAR, raw_car(manufacturer_id=999))
    seeded.session.rollback()


def test_adding_a_car_for_a_missing_manufacturer_is_rejected(seeded) -> None:
    with pytest.raises(RecordNotFoundError, match="Tesla"):
        seeded.add_car("Tesla", "S", 2022, 80000.0, 10)


def test_database_cascade_removes_cars_of_a_deleted_manufacturer(
    seeded,
) -> None:
    seeded.session.execute(
        text("DELETE FROM manufacturers WHERE name = 'Toyota'")
    )
    seeded.session.commit()
    assert seeded.cars.count() == 3
    assert seeded.cars.find_by_brand("Toyota") == []


def test_check_violation_is_translated_to_a_domain_error(seeded) -> None:
    """A row that passes Python but not the CHECK is still reported."""
    from car_catalog.exceptions import InvalidCarDataError
    from car_catalog.orm_models import CarEntity
    from car_catalog.repositories import _flush_new

    bad = CarEntity(
        manufacturer_id=1, model="Old", year=1500, price=1.0, mileage=1
    )
    with pytest.raises(InvalidCarDataError, match="ck_cars_year_range"):
        _flush_new(seeded.session, bad, "duplicate")
    assert seeded.cars.count() == 5  # the savepoint was rolled back


def test_car_of_an_unsaved_manufacturer_is_rejected_by_the_foreign_key(
    car_repo,
) -> None:
    from car_catalog.orm_models import Manufacturer

    ghost = Manufacturer(id=999, name="Ghost")  # never saved
    with pytest.raises(RecordNotFoundError, match="does not exist"):
        car_repo.add(ghost, "X", 2020, 1.0, 1)
    assert car_repo.count() == 0
