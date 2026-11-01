"""Integration: ManufacturerRepository + SQLAlchemy + SQLite."""

import pytest
from sqlalchemy.orm import Session, sessionmaker

from car_catalog.exceptions import (
    DuplicateRecordError,
    InvalidCarDataError,
    RecordNotFoundError,
)
from car_catalog.repositories import ManufacturerRepository

pytestmark = pytest.mark.integration


def test_create_and_read_manufacturer(manufacturer_repo) -> None:
    created = manufacturer_repo.add("Skoda", "Czechia")
    assert created.id is not None
    found = manufacturer_repo.get(created.id)
    assert (found.name, found.country) == ("Skoda", "Czechia")


def test_country_is_optional(manufacturer_repo) -> None:
    assert manufacturer_repo.add("Tesla").country is None


def test_name_is_stripped(manufacturer_repo) -> None:
    assert manufacturer_repo.add("  Kia ").name == "Kia"


@pytest.mark.parametrize("name", ["", "   ", None])
def test_empty_name_is_rejected(manufacturer_repo, name) -> None:
    with pytest.raises(InvalidCarDataError):
        manufacturer_repo.add(name)


def test_duplicate_name_is_rejected_ignoring_case(manufacturer_repo) -> None:
    manufacturer_repo.add("BMW")
    with pytest.raises(DuplicateRecordError, match="already exists"):
        manufacturer_repo.add("bmw")


def test_get_by_name_is_case_insensitive(manufacturer_repo) -> None:
    manufacturer_repo.add("BMW")
    assert manufacturer_repo.get_by_name(" bmw ").name == "BMW"
    assert manufacturer_repo.get_by_name("Opel") is None


def test_require_by_name_raises_for_missing(manufacturer_repo) -> None:
    with pytest.raises(RecordNotFoundError, match="Opel"):
        manufacturer_repo.require_by_name("Opel")


def test_get_missing_id_raises(manufacturer_repo) -> None:
    with pytest.raises(RecordNotFoundError):
        manufacturer_repo.get(999)


def test_list_is_sorted_by_name(manufacturer_repo) -> None:
    for name in ("Toyota", "Audi", "BMW"):
        manufacturer_repo.add(name)
    assert [m.name for m in manufacturer_repo.list_all()] == [
        "Audi",
        "BMW",
        "Toyota",
    ]


def test_update_country_is_persisted(
    session: Session, session_factory: sessionmaker[Session], manufacturer_repo
) -> None:
    manufacturer = manufacturer_repo.add("Honda", "Japan")
    manufacturer_repo.update_country(manufacturer.id, "Japan (Tokyo)")
    session.commit()
    with session_factory() as other:
        assert ManufacturerRepository(other).get(manufacturer.id).country == (
            "Japan (Tokyo)"
        )


def test_delete_manufacturer(manufacturer_repo) -> None:
    manufacturer = manufacturer_repo.add("Opel")
    manufacturer_repo.delete(manufacturer.id)
    assert manufacturer_repo.get_by_name("Opel") is None


def test_delete_missing_manufacturer_raises(manufacturer_repo) -> None:
    with pytest.raises(RecordNotFoundError):
        manufacturer_repo.delete(42)


def test_deleting_a_manufacturer_deletes_its_cars(seeded) -> None:
    bmw = seeded.manufacturers.require_by_name("BMW")
    seeded.delete_manufacturer("BMW")
    assert seeded.cars.count() == 3
    assert seeded.cars.find_by_brand("BMW") == []
    assert seeded.manufacturers.get_by_name("BMW") is None
    assert bmw.id is not None


def test_count_cars_of_manufacturer(seeded) -> None:
    toyota = seeded.manufacturers.require_by_name("Toyota")
    assert seeded.manufacturers.count_cars(toyota.id) == 2
