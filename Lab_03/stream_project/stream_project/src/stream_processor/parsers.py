"""Parsing stage: CSV lines -> dictionaries."""

import csv
from collections.abc import Iterable, Iterator


def parse_csv_rows(lines: Iterable[str]) -> Iterator[dict[str, str]]:
    """Turn lazily supplied CSV lines into dict rows (first line is header)."""
    reader = csv.DictReader(lines)
    yield from reader
