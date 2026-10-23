"""Tests for immutable value objects and the constrained TypeVar helper."""

from dataclasses import FrozenInstanceError
from decimal import Decimal

import pytest

from domain_app.exceptions import ValidationError
from domain_app.generics import clamp
from domain_app.value_objects import Mileage, Money, VehicleSpecification


def test_money_arithmetic_and_rounding() -> None:
    price = Money.of("10.005")
    assert price.amount == Decimal("10.01")
    assert (Money.of(10) + Money.of(5)).amount == Decimal("15.00")
    assert (Money.of(10) * 3).amount == Decimal("30.00")
    assert (Money.of(10) / 4).amount == Decimal("2.50")


def test_money_total_ordering() -> None:
    low, high = Money.of(10), Money.of(20)
    assert low < high and low <= high and high > low and high >= low
    assert low == Money.of(10) and low != high
    assert max(low, high) is high


def test_money_rejects_invalid_values() -> None:
    with pytest.raises(ValidationError):
        Money.of(-1)
    with pytest.raises(ValidationError):
        Money.of("abc")
    with pytest.raises(ValidationError):
        Money.of(1) / 0
    with pytest.raises(ValidationError):
        Money.of(1, "USD") + Money.of(1, "EUR")
    with pytest.raises(ValueError):
        Money.of(-5)


def test_money_is_immutable() -> None:
    money = Money.of(5)
    with pytest.raises(FrozenInstanceError):
        money.amount = Decimal(1)  # type: ignore[misc]


def test_money_helpers() -> None:
    assert Money.total([]) == Money.zero()
    assert Money.total([Money.of(1), Money.of(2)]) == Money.of(3)
    assert Money.of(200).discounted(25) == Money.of(150)
    assert Money.of(200).discounted(500) == Money.zero()
    assert str(Money.of(5)) == "5.00 USD"
    assert Money.of(Money.of(7)) == Money.of(7)


def test_money_add_with_foreign_type_is_not_supported() -> None:
    with pytest.raises(TypeError):
        Money.of(1) + 1  # type: ignore[operator]


def test_mileage() -> None:
    assert Mileage(5) + Mileage(7) == Mileage(12)
    assert Mileage(1) < Mileage(2)
    assert Mileage.of(3) == Mileage(3)
    assert str(Mileage(10)) == "10 km"
    with pytest.raises(ValidationError):
        Mileage(-1)
    with pytest.raises(FrozenInstanceError):
        Mileage(1).kilometers = 2  # type: ignore[misc]


def test_specification_validation_and_title() -> None:
    spec = VehicleSpecification("  BMW ", " X5", 2021)
    assert spec.brand == "BMW" and spec.model == "X5"
    assert spec.title == "BMW X5 (2021)"
    with pytest.raises(ValidationError):
        VehicleSpecification("", "X5", 2021)
    with pytest.raises(ValidationError):
        VehicleSpecification("BMW", "X5", 1800)
    with pytest.raises(FrozenInstanceError):
        spec.year = 2000  # type: ignore[misc]


def test_clamp_keeps_the_type() -> None:
    assert clamp(150, 0, 100) == 100 and isinstance(clamp(5, 0, 10), int)
    assert clamp(-2.5, 0.0, 1.0) == 0.0
    assert isinstance(clamp(0.5, 0.0, 1.0), float)
