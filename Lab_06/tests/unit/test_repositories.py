"""Unit tests of the in-memory repository."""

import pytest

from car_catalog.exceptions import CarNotFoundError
from car_catalog.repositories import InMemoryVehicleRepository


def test_new_repository_is_empty() -> None:
    repo = InMemoryVehicleRepository()
    assert len(repo) == 0
    assert repo.list_all() == []


def test_add_and_list(car_factory) -> None:
    repo = InMemoryVehicleRepository()
    car = car_factory()
    repo.add(car)
    assert repo.list_all() == [car]


def test_list_all_returns_a_copy(repository) -> None:
    snapshot = repository.list_all()
    snapshot.clear()
    assert len(repository) == 5


def test_remove_returns_the_removed_car(repository) -> None:
    removed = repository.remove(" bmw ", "X5")
    assert removed.full_name == "BMW X5"
    assert len(repository) == 4


def test_removing_missing_car_raises(repository) -> None:
    with pytest.raises(CarNotFoundError):
        repository.remove("Tesla", "S")
