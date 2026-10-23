"""Generic helpers built on a constrained TypeVar."""

from typing import TypeVar

# constrained TypeVar: exactly int or float, and the result keeps the type
Number = TypeVar("Number", int, float)


def clamp(value: Number, low: Number, high: Number) -> Number:
    """Limit `value` to the closed interval [low, high]."""
    return max(low, min(value, high))
