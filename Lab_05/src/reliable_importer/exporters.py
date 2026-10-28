"""Exporter Protocol, JSON and JSON Lines exporters (atomic, streaming)."""

import json
import textwrap
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Protocol

from reliable_importer.exceptions import DataExportError
from reliable_importer.models import Vehicle
from reliable_importer.utils import atomic_output


class Exporter(Protocol):
    """Anything that can write vehicles to a file and report the count."""

    def export(self, vehicles: Iterable[Vehicle], path: Path) -> int: ...


class JsonExporter:
    """JSON array written record by record through a temporary file."""

    def __init__(self, *, backup: bool = False) -> None:
        self._backup = backup

    def export(self, vehicles: Iterable[Vehicle], path: Path) -> int:
        count = 0
        try:
            with atomic_output(path, backup=self._backup) as file:
                file.write("[\n")
                for vehicle in vehicles:
                    if count:
                        file.write(",\n")
                    body = json.dumps(
                        vehicle.to_dict(), ensure_ascii=False, indent=2
                    )
                    file.write(textwrap.indent(body, "  "))
                    count += 1
                file.write("\n]\n" if count else "]\n")
        except (OSError, TypeError, ValueError) as error:
            raise DataExportError(f"Cannot export data to {path}") from error
        return count


class JsonLinesExporter:
    """JSON Lines: one object per line, ideal for very large outputs."""

    def __init__(self, *, backup: bool = False) -> None:
        self._backup = backup

    def export(self, vehicles: Iterable[Vehicle], path: Path) -> int:
        count = 0
        try:
            with atomic_output(path, backup=self._backup) as file:
                for vehicle in vehicles:
                    line = json.dumps(vehicle.to_dict(), ensure_ascii=False)
                    file.write(line + "\n")
                    count += 1
        except (OSError, TypeError, ValueError) as error:
            raise DataExportError(f"Cannot export data to {path}") from error
        return count


_FACTORIES: dict[str, Callable[[bool], Exporter]] = {
    "json": lambda backup: JsonExporter(backup=backup),
    "jsonl": lambda backup: JsonLinesExporter(backup=backup),
}
_EXTENSIONS = {".json": "json", ".jsonl": "jsonl", ".ndjson": "jsonl"}


def select_exporter(
    path: Path, fmt: str = "auto", *, backup: bool = False
) -> Exporter:
    """Choose an exporter by the configured format or by the extension."""
    name = (
        _EXTENSIONS.get(path.suffix.lower(), "json") if fmt == "auto" else fmt
    )
    factory = _FACTORIES.get(name)
    if factory is None:
        raise DataExportError(f"Unknown output format: {fmt}")
    return factory(backup)
