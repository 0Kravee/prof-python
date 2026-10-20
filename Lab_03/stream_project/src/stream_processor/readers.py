"""Source and cleaning stages: lazy line reading."""

from collections.abc import Iterable, Iterator
from pathlib import Path


def read_lines(path: Path) -> Iterator[str]:
    """Stream a text file line by line (the file is never loaded fully).

    `yield from` delegates the iteration to the file object.
    """
    with path.open("r", encoding="utf-8", newline="") as file:
        yield from file


def clean_lines(lines: Iterable[str]) -> Iterator[str]:
    """Cleaning stage: strip whitespace and drop empty lines."""
    for line in lines:
        value = line.strip()
        if value:
            yield value
