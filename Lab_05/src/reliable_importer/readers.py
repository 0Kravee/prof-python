"""Streaming readers: CSV, JSON, JSON Lines and YAML."""

import csv
import json
from collections.abc import Iterator, Sequence
from pathlib import Path

from reliable_importer.exceptions import DataImportError
from reliable_importer.models import RawRow
from reliable_importer.yaml_loader import load_pyyaml

REQUIRED_COLUMNS = (
    "vehicle_id",
    "brand",
    "model",
    "year",
    "price",
    "mileage",
)


def _check_columns(fieldnames: Sequence[str] | None, path: Path) -> None:
    if fieldnames is None:
        raise DataImportError(f"Input file is empty: {path}")
    missing = [name for name in REQUIRED_COLUMNS if name not in fieldnames]
    if missing:
        raise DataImportError(
            f"Missing columns in {path.name}: {', '.join(missing)}"
        )


def read_csv_rows(path: Path) -> Iterator[RawRow]:
    """Stream CSV records one by one (the file is never loaded fully)."""
    try:
        with path.open("r", encoding="utf-8", newline="") as file:
            reader = csv.DictReader(file)
            _check_columns(reader.fieldnames, path)
            for row in reader:
                yield RawRow(reader.line_num, row)
    except (OSError, UnicodeDecodeError, csv.Error) as error:
        raise DataImportError(f"Cannot read input file: {path}") from error


def read_jsonl_rows(path: Path) -> Iterator[RawRow]:
    """Stream JSON Lines: one JSON object per line."""
    try:
        with path.open("r", encoding="utf-8") as file:
            for line_number, line in enumerate(file, start=1):
                if not line.strip():
                    continue
                try:
                    item: object = json.loads(line)
                except json.JSONDecodeError as error:
                    raise DataImportError(
                        f"Invalid JSON at line {line_number}"
                    ) from error
                if not isinstance(item, dict):
                    raise DataImportError(
                        f"Line {line_number} is not a JSON object"
                    )
                yield RawRow(line_number, item)
    except (OSError, UnicodeDecodeError) as error:
        raise DataImportError(f"Cannot read input file: {path}") from error


def _items(payload: object, path: Path) -> list[object]:
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict) and isinstance(payload.get("vehicles"), list):
        items: list[object] = payload["vehicles"]
        return items
    raise DataImportError(
        f"{path.name} must contain a list of records "
        f"or an object with a 'vehicles' list"
    )


def _rows_from_items(items: list[object]) -> Iterator[RawRow]:
    for index, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            raise DataImportError(f"Record {index} is not an object")
        yield RawRow(index, item)


def read_json_rows(path: Path) -> Iterator[RawRow]:
    """Read a JSON document (a list of objects). Not streaming by nature."""
    try:
        with path.open("r", encoding="utf-8") as file:
            payload: object = json.load(file)
    except json.JSONDecodeError as error:
        raise DataImportError(f"Invalid JSON document: {path.name}") from error
    except (OSError, UnicodeDecodeError) as error:
        raise DataImportError(f"Cannot read input file: {path}") from error
    yield from _rows_from_items(_items(payload, path))


def read_yaml_rows(path: Path) -> Iterator[RawRow]:
    """Read a YAML document (a list of objects); requires PyYAML."""
    yaml_module = load_pyyaml()
    if yaml_module is None:
        raise DataImportError("YAML input requires the PyYAML package")
    try:
        text = path.read_text(encoding="utf-8")
        payload: object = yaml_module.safe_load(text)
    except yaml_module.YAMLError as error:
        raise DataImportError(f"Invalid YAML document: {path.name}") from error
    except (OSError, UnicodeDecodeError) as error:
        raise DataImportError(f"Cannot read input file: {path}") from error
    yield from _rows_from_items(_items(payload, path))
