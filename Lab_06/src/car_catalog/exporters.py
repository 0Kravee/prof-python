"""JSON export of cars."""

import json
import os
import tempfile
from collections.abc import Iterable
from dataclasses import asdict
from pathlib import Path
from typing import Any

from car_catalog.exceptions import ExportError
from car_catalog.models import Car


def cars_to_dicts(cars: Iterable[Car]) -> list[dict[str, Any]]:
    """Plain dictionaries, ready for json.dumps."""
    return [asdict(car) for car in cars]


def export_cars_json(cars: Iterable[Car], path: Path) -> int:
    """Write cars to ``path`` atomically and return how many were written.

    The data goes to a temporary file in the same directory first, so a
    failure never leaves a half written target file behind.
    """
    records = cars_to_dicts(cars)
    temp_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=path.parent,
            suffix=".tmp",
            delete=False,
        ) as temp:
            temp_name = temp.name
            json.dump(records, temp, indent=2, ensure_ascii=False)
        os.replace(temp_name, path)
    except (OSError, TypeError, ValueError) as exc:
        if temp_name is not None and os.path.exists(temp_name):
            os.unlink(temp_name)
        raise ExportError(f"Cannot export to {path}: {exc}") from exc
    return len(records)
