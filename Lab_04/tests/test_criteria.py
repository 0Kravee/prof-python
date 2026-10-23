"""Tests for search criteria (strategy pattern)."""

import pytest

from domain_app.criteria import (
    AndCriteria,
    BrandCriteria,
    BrandOrModelCriteria,
    ModelCriteria,
    NotCriteria,
    OrCriteria,
    SearchCriteria,
    YearCriteria,
    YearRangeCriteria,
)
from domain_app.models import Vehicle


def ids(vehicles: list[Vehicle], criteria: SearchCriteria) -> list[int]:
    return [v.vehicle_id for v in vehicles if criteria.matches(v)]


def test_abstract_criteria_cannot_be_created() -> None:
    with pytest.raises(TypeError):
        SearchCriteria()  # type: ignore[abstract]


def test_simple_criteria(vehicles: list[Vehicle]) -> None:
    assert ids(vehicles, BrandCriteria(" BMW ")) == [2]
    assert ids(vehicles, ModelCriteria("corolla")) == [3]
    assert ids(vehicles, YearCriteria(2022)) == [3, 5]
    assert ids(vehicles, BrandOrModelCriteria("model")) == [5]
    assert ids(vehicles, BrandOrModelCriteria("toy")) == [1, 3]


def test_year_range(vehicles: list[Vehicle]) -> None:
    assert ids(vehicles, YearRangeCriteria(2021)) == [2, 3, 5]
    assert ids(vehicles, YearRangeCriteria(None, 2019)) == [1, 4]
    assert ids(vehicles, YearRangeCriteria(2019, 2021)) == [1, 2]
    assert ids(vehicles, YearRangeCriteria()) == [1, 2, 3, 4, 5]


def test_combinators(vehicles: list[Vehicle]) -> None:
    toyota, recent = BrandCriteria("Toyota"), YearRangeCriteria(2020)
    combined_and = toyota & recent
    assert isinstance(combined_and, AndCriteria)
    assert ids(vehicles, combined_and) == [3]
    combined_or = toyota | BrandCriteria("Audi")
    assert isinstance(combined_or, OrCriteria)
    assert ids(vehicles, combined_or) == [1, 3, 4]
    negated = ~toyota
    assert isinstance(negated, NotCriteria)
    assert ids(vehicles, negated) == [2, 4, 5]


def test_criteria_is_callable(vehicles: list[Vehicle]) -> None:
    criteria = BrandCriteria("Audi")
    assert criteria(vehicles[3]) and not criteria(vehicles[0])
    assert [v.vehicle_id for v in filter(criteria, vehicles)] == [4]
