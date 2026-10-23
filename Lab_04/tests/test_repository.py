"""Tests for the generic repository and its protocols."""

from dataclasses import dataclass

import pytest

from domain_app.criteria import BrandCriteria
from domain_app.exceptions import DuplicateEntityError, EntityNotFoundError
from domain_app.models import Vehicle
from domain_app.protocols import ReadableRepository, Repository
from domain_app.repositories import InMemoryRepository, VehicleRepository


def test_add_get_remove_and_dunders(vehicles: list[Vehicle]) -> None:
    repo: VehicleRepository = InMemoryRepository(vehicles)
    assert len(repo) == 5 and 3 in repo and 99 not in repo
    assert repo.get(2) is vehicles[1]
    assert list(repo) == vehicles
    repo.remove(2)
    assert 2 not in repo and len(repo) == 4


def test_errors(vehicles: list[Vehicle]) -> None:
    repo = InMemoryRepository[Vehicle](vehicles)
    with pytest.raises(DuplicateEntityError):
        repo.add(vehicles[0])
    with pytest.raises(EntityNotFoundError):
        repo.get(99)
    with pytest.raises(EntityNotFoundError):
        repo.remove(99)


def test_find_with_matcher(vehicles: list[Vehicle]) -> None:
    repo = InMemoryRepository[Vehicle](vehicles)
    assert [v.vehicle_id for v in repo.find(BrandCriteria("Toyota"))] == [1, 3]


@dataclass
class Dealer:
    id: int
    name: str


def test_generic_repository_works_for_other_entities() -> None:
    repo = InMemoryRepository[Dealer]([Dealer(1, "A")])
    repo.add(Dealer(2, "B"))
    assert [d.name for d in repo.list_all()] == ["A", "B"]


def test_segregated_protocols(vehicles: list[Vehicle]) -> None:
    repo = InMemoryRepository[Vehicle](vehicles)
    full: Repository[Vehicle] = repo
    read_only: ReadableRepository[Vehicle] = repo
    assert full.get(1) is read_only.get(1)
    assert len(read_only.list_all()) == 5
