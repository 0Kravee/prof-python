"""Unit tests of the JSON export."""

import json
from pathlib import Path

import pytest

from car_catalog import exporters
from car_catalog.exceptions import ExportError
from car_catalog.exporters import cars_to_dicts, export_cars_json


def test_cars_to_dicts_contains_all_fields(car_factory) -> None:
    assert cars_to_dicts([car_factory()]) == [
        {
            "brand": "Toyota",
            "model": "Camry",
            "year": 2019,
            "price": 21500.0,
            "mileage": 45000,
        }
    ]


def test_export_writes_valid_json_and_returns_count(
    sample_cars, export_dir: Path
) -> None:
    target = export_dir / "cars.json"
    assert export_cars_json(sample_cars, target) == 5
    data = json.loads(target.read_text(encoding="utf-8"))
    assert len(data) == 5
    assert data[1]["model"] == "X5"


def test_export_of_empty_catalog_is_an_empty_json_list(
    export_dir: Path,
) -> None:
    target = export_dir / "empty.json"
    assert export_cars_json([], target) == 0
    assert json.loads(target.read_text(encoding="utf-8")) == []


def test_non_ascii_text_is_kept_readable(
    car_factory, export_dir: Path
) -> None:
    target = export_dir / "ua.json"
    export_cars_json([car_factory(brand="Škoda", model="Фабія")], target)
    assert "Фабія" in target.read_text(encoding="utf-8")


def test_export_into_missing_directory_raises_export_error(
    sample_cars, tmp_path: Path
) -> None:
    with pytest.raises(ExportError, match="Cannot export"):
        export_cars_json(sample_cars, tmp_path / "no" / "dir" / "cars.json")


def test_failed_export_keeps_old_file_and_removes_temp_file(
    sample_cars, export_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = export_dir / "cars.json"
    target.write_text('["old"]', encoding="utf-8")

    def broken_dump(*args: object, **kwargs: object) -> None:
        raise OSError("disk is full")

    monkeypatch.setattr(exporters.json, "dump", broken_dump)
    with pytest.raises(ExportError, match="disk is full") as excinfo:
        export_cars_json(sample_cars, target)
    assert isinstance(excinfo.value.__cause__, OSError)
    assert target.read_text(encoding="utf-8") == '["old"]'
    # the export_dir fixture teardown also checks that no *.tmp remains
    assert list(export_dir.glob("*.tmp")) == []


def test_second_export_replaces_the_first(
    sample_cars, export_dir: Path
) -> None:
    target = export_dir / "cars.json"
    export_cars_json(sample_cars, target)
    export_cars_json(sample_cars[:1], target)
    assert len(json.loads(target.read_text(encoding="utf-8"))) == 1
