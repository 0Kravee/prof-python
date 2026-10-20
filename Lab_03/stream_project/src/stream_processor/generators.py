"""Generator function examples: yield, yield from, infinite generators."""

from collections.abc import Iterable, Iterator
from typing import Any


def generate_numbers(start: int, stop: int) -> Iterator[int]:
    """Generator function: yield pauses it and keeps local state."""
    current = start
    while current < stop:
        yield current
        current += 1


def even_numbers(limit: int) -> Iterator[int]:
    for number in range(limit):
        if number % 2 == 0:
            yield number


def natural_numbers() -> Iterator[int]:
    """Infinite generator: must always be limited, e.g. with islice."""
    value = 1
    while True:
        yield value
        value += 1


def flatten(values: list[Any]) -> Iterator[Any]:
    """Recursive generator based on `yield from`."""
    for value in values:
        if isinstance(value, list):
            yield from flatten(value)
        else:
            yield value


def traced_generator(log: list[str]) -> Iterator[int]:
    """Shows that the body runs only on next() and resumes after yield."""
    log.append("start")
    yield 1
    log.append("continue")
    yield 2
    log.append("finish")


def parse_numbers(lines: Iterable[str]) -> Iterator[float]:
    """Lazy parser: text lines -> numbers (invalid lines are skipped)."""
    for line in lines:
        try:
            yield float(line)
        except ValueError:
            continue


def positive_only(numbers: Iterable[float]) -> Iterator[float]:
    """Lazy filter: keep positive numbers only."""
    return (number for number in numbers if number > 0)
