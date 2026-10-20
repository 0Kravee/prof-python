"""Lazy pipeline: source -> parse -> validate -> filter -> transform."""

import csv
import logging
from collections import Counter
from collections.abc import Generator, Iterable, Iterator
from dataclasses import astuple
from itertools import chain
from pathlib import Path
from typing import Any, TypeVar

from stream_processor.config import CSV_HEADER
from stream_processor.filters import (
    filter_by_brand,
    filter_by_min_year,
    filter_by_year,
    validate_cars,
)
from stream_processor.models import CarRecord
from stream_processor.parsers import parse_csv_rows
from stream_processor.readers import clean_lines, read_lines
from stream_processor.transformations import normalize_cars

logger = logging.getLogger(__name__)
T = TypeVar("T")


def trace_stage(
    name: str, items: Iterable[T], counters: Counter[str]
) -> Generator[T, None, None]:
    """Pass-through generator counting items that leave a stage."""
    for item in items:
        counters[name] += 1
        yield item
    logger.debug("stage %s finished: %s items", name, counters[name])


def build_pipeline(
    path: Path,
    brand: str | None = None,
    year: int | None = None,
    min_year: int | None = None,
    stats: Counter[str] | None = None,
    counters: Counter[str] | None = None,
) -> Generator[CarRecord, None, None]:
    """Assemble lazy stages; nothing is read until the result is consumed."""
    counters = counters if counters is not None else Counter()

    lines = read_lines(path)
    cleaned = clean_lines(lines)
    rows = trace_stage("rows", parse_csv_rows(cleaned), counters)
    valid = trace_stage("valid", validate_cars(rows, stats), counters)
    normalized = normalize_cars(valid)

    result: Iterator[CarRecord] = normalized
    if brand is not None:
        result = filter_by_brand(result, brand)
    if year is not None:
        result = filter_by_year(result, year)
    if min_year is not None:
        result = filter_by_min_year(result, min_year)
    return trace_stage("output", result, counters)


def build_multi_pipeline(
    paths: Iterable[Path], **options: Any
) -> Iterator[CarRecord]:
    """Pipeline over several files: itertools.chain joins the lazy streams."""
    return chain.from_iterable(
        build_pipeline(path, **options) for path in paths
    )


def export_cars(cars: Iterable[CarRecord], path: Path) -> int:
    """Sink stage: stream records into a new CSV file, return the row count."""
    count = 0
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(CSV_HEADER)
        for car in cars:
            writer.writerow(astuple(car))
            count += 1
    return count


def read_all_cars(path: Path, **options: Any) -> list[CarRecord]:
    """Eager reader: materialise the whole pipeline result in a list."""
    return list(build_pipeline(path, **options))


def read_cars_lazy(path: Path, **options: Any) -> Iterator[CarRecord]:
    """Lazy reader: nothing is read until the stream is consumed."""
    return build_pipeline(path, **options)
