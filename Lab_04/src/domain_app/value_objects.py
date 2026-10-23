"""Immutable value objects of the vehicle catalog."""

from collections.abc import Iterable
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from functools import total_ordering
from typing import TypeAlias

from domain_app.config import CURRENCY, MAX_YEAR, MIN_YEAR
from domain_app.exceptions import ValidationError
from domain_app.generics import clamp

_CENT = Decimal("0.01")


@total_ordering
@dataclass(frozen=True)
class Money:
    """Non-negative amount of money in a currency (immutable)."""

    amount: Decimal
    currency: str = CURRENCY

    def __post_init__(self) -> None:
        if self.amount < 0:
            raise ValidationError("Money cannot be negative")
        rounded = self.amount.quantize(_CENT, rounding=ROUND_HALF_UP)
        object.__setattr__(self, "amount", rounded)

    @classmethod
    def of(cls, value: "MoneyLike", currency: str = CURRENCY) -> "Money":
        """Build Money from Money, int, float, str or Decimal."""
        if isinstance(value, Money):
            return value
        try:
            amount = (
                value if isinstance(value, Decimal) else Decimal(str(value))
            )
        except InvalidOperation as error:
            raise ValidationError(
                f"Invalid money amount: {value!r}"
            ) from error
        return cls(amount, currency)

    @classmethod
    def zero(cls, currency: str = CURRENCY) -> "Money":
        return cls(Decimal(0), currency)

    @staticmethod
    def total(values: Iterable["Money"]) -> "Money":
        """Sum of several amounts (zero for an empty iterable)."""
        result: Money | None = None
        for value in values:
            result = value if result is None else result + value
        return result if result is not None else Money.zero()

    def _ensure_same_currency(self, other: "Money") -> None:
        if self.currency != other.currency:
            raise ValidationError(
                f"Currency mismatch: {self.currency} and {other.currency}"
            )

    def __add__(self, other: "Money") -> "Money":
        if not isinstance(other, Money):
            return NotImplemented
        self._ensure_same_currency(other)
        return Money(self.amount + other.amount, self.currency)

    def __mul__(self, factor: int | Decimal) -> "Money":
        return Money(self.amount * Decimal(factor), self.currency)

    def __truediv__(self, divisor: int) -> "Money":
        if divisor <= 0:
            raise ValidationError("Divisor must be positive")
        return Money(self.amount / Decimal(divisor), self.currency)

    def __lt__(self, other: "Money") -> bool:
        if not isinstance(other, Money):
            return NotImplemented
        self._ensure_same_currency(other)
        return self.amount < other.amount

    def discounted(self, percent: float) -> "Money":
        """Price reduced by `percent` (limited to 0..100)."""
        share = Decimal(str(clamp(percent, 0.0, 100.0)))
        factor = (Decimal(100) - share) / Decimal(100)
        return Money(self.amount * factor, self.currency)

    def __str__(self) -> str:
        return f"{self.amount:.2f} {self.currency}"


@total_ordering
@dataclass(frozen=True)
class Mileage:
    """Non-negative distance driven, in kilometres (immutable)."""

    kilometers: int

    def __post_init__(self) -> None:
        if self.kilometers < 0:
            raise ValidationError("Mileage cannot be negative")

    @classmethod
    def of(cls, value: "MileageLike") -> "Mileage":
        return value if isinstance(value, Mileage) else cls(value)

    def __add__(self, other: "Mileage") -> "Mileage":
        if not isinstance(other, Mileage):
            return NotImplemented
        return Mileage(self.kilometers + other.kilometers)

    def __lt__(self, other: "Mileage") -> bool:
        if not isinstance(other, Mileage):
            return NotImplemented
        return self.kilometers < other.kilometers

    def __str__(self) -> str:
        return f"{self.kilometers} km"


@dataclass(frozen=True)
class VehicleSpecification:
    """Brand, model and production year of a vehicle (immutable)."""

    brand: str
    model: str
    year: int

    def __post_init__(self) -> None:
        brand = self.brand.strip()
        model = self.model.strip()
        if not brand or not model:
            raise ValidationError("Brand and model must not be empty")
        if not MIN_YEAR <= self.year <= MAX_YEAR:
            raise ValidationError(
                f"Year must be between {MIN_YEAR} and {MAX_YEAR}"
            )
        object.__setattr__(self, "brand", brand)
        object.__setattr__(self, "model", model)

    @property
    def title(self) -> str:
        """Human-readable name, e.g. 'Toyota Camry (2019)'."""
        return f"{self.brand} {self.model} ({self.year})"


MoneyLike: TypeAlias = Money | int | float | str | Decimal
MileageLike: TypeAlias = Mileage | int
