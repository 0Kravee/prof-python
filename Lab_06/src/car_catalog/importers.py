"""CSV import of cars."""

import csv
import logging
from pathlib import Path

from car_catalog.config import AppConfig
from car_catalog.exceptions import (
    CarCatalogError,
    CarImportError,
)
from car_catalog.models import Car
from car_catalog.validators import validate_car

logger = logging.getLogger(__name__)

REQUIRED_COLUMNS: tuple[str, ...] = (
    "brand",
    "model",
    "year",
    "price",
    "mileage",
)


def parse_car_row(row: dict[str, str | None]) -> Car:
    """Convert one CSV row to a Car (raises ValueError-like errors)."""
    return Car(
        brand=row["brand"] or "",
        model=row["model"] or "",
        year=int(row["year"] or ""),
        price=float(row["price"] or ""),
        mileage=int(row["mileage"] or ""),
    )


def import_cars_csv(
    path: Path,
    config: AppConfig | None = None,
    skip_invalid: bool = False,
) -> list[Car]:
    """Read cars from a CSV file with a header line.

    With ``skip_invalid=False`` (default) the first malformed record
    raises :class:`CarImportError`; otherwise it is logged and skipped.
    """
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as file:
            reader = csv.DictReader(file)
            missing = set(REQUIRED_COLUMNS) - set(reader.fieldnames or [])
            if missing:
                raise CarImportError(
                    f"Missing columns: {', '.join(sorted(missing))}", 1
                )
            return _read_rows(reader, config, skip_invalid)
    except (OSError, UnicodeDecodeError, csv.Error) as exc:
        raise CarImportError(f"Cannot read file {path}: {exc}") from exc


def _read_rows(
    reader: csv.DictReader[str],
    config: AppConfig | None,
    skip_invalid: bool,
) -> list[Car]:
    cars: list[Car] = []
    for row in reader:
        line = reader.line_num
        try:
            if None in row:
                raise ValueError("too many fields")
            cars.append(validate_car(parse_car_row(row), config))
        except (CarCatalogError, ValueError) as exc:
            if skip_invalid:
                logger.warning("Skipped line %d: %s", line, exc)
                continue
            raise CarImportError(f"Line {line}: {exc}", line) from exc
    return cars
