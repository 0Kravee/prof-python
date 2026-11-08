"""Integration: import -> filter -> export JSON -> read the file back."""

import json
from pathlib import Path

import pytest

from car_catalog.exceptions import ExportError
from car_catalog.importers import import_cars_csv
from car_catalog.models import Car
from car_catalog.repositories import InMemoryVehicleRepository
from car_catalog.services import CatalogService, search_cars

pytestmark = pytest.mark.integration


def test_import_filter_export_roundtrip(
    csv_file: Path, export_dir: Path
) -> None:
    cars = import_cars_csv(csv_file)
    selected = search_cars(cars, brand="bmw", min_year=2021)
    target = export_dir / "bmw.json"
    service = CatalogService(InMemoryVehicleRepository(cars))

    assert service.export_json(target, selected) == 1
    restored = [Car(**item) for item in json.loads(target.read_text("utf-8"))]
    assert restored == selected


def test_export_of_whole_catalog_after_adding_a_car(
    csv_file: Path, export_dir: Path, car_factory
) -> None:
    service = CatalogService(InMemoryVehicleRepository())
    service.import_csv(csv_file)
    service.add_car(car_factory(brand="Kia", model="Rio"))
    target = export_dir / "all.json"
    assert service.export_json(target) == 6
    data = json.loads(target.read_text(encoding="utf-8"))
    assert data[-1]["brand"] == "Kia"


def test_failed_export_does_not_destroy_previous_result(
    csv_file: Path, export_dir: Path
) -> None:
    service = CatalogService(InMemoryVehicleRepository())
    service.import_csv(csv_file)
    target = export_dir / "cars.json"
    service.export_json(target)
    before = target.read_text(encoding="utf-8")

    with pytest.raises(ExportError):
        service.export_json(export_dir / "missing" / "cars.json")
    assert target.read_text(encoding="utf-8") == before
