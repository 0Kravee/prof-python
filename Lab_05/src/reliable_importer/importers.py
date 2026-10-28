"""Importer Protocol and format selection."""

from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Protocol

from reliable_importer.exceptions import DataImportError
from reliable_importer.models import RawRow
from reliable_importer.readers import (
    read_csv_rows,
    read_json_rows,
    read_jsonl_rows,
    read_yaml_rows,
)


class Importer(Protocol):
    """Anything that can stream raw records from a file."""

    def read(self, path: Path) -> Iterator[RawRow]: ...


class CsvImporter:
    def read(self, path: Path) -> Iterator[RawRow]:
        return read_csv_rows(path)


class JsonImporter:
    def read(self, path: Path) -> Iterator[RawRow]:
        return read_json_rows(path)


class JsonLinesImporter:
    def read(self, path: Path) -> Iterator[RawRow]:
        return read_jsonl_rows(path)


class YamlImporter:
    def read(self, path: Path) -> Iterator[RawRow]:
        return read_yaml_rows(path)


_BY_NAME: dict[str, Callable[[], Importer]] = {
    "csv": CsvImporter,
    "json": JsonImporter,
    "jsonl": JsonLinesImporter,
    "yaml": YamlImporter,
}
_BY_EXTENSION: dict[str, str] = {
    ".csv": "csv",
    ".json": "json",
    ".jsonl": "jsonl",
    ".ndjson": "jsonl",
    ".yaml": "yaml",
    ".yml": "yaml",
}


def select_importer(path: Path, fmt: str = "auto") -> Importer:
    """Choose an importer by the configured format or by the extension."""
    name = fmt
    if fmt == "auto":
        name = _BY_EXTENSION.get(path.suffix.lower(), "")
    factory = _BY_NAME.get(name)
    if factory is None:
        raise DataImportError(f"Cannot detect the input format of {path}")
    return factory()
