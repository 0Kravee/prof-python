"""Integration: CSV -> validation -> domain objects -> repository -> search."""

import logging
from pathlib import Path

import pytest

from car_catalog.config import AppConfig
from car_catalog.exceptions import CarImportError
from car_catalog.repositories import InMemoryVehicleRepository
from car_catalog.services import CatalogService

pytestmark = pytest.mark.integration


def test_import_then_search_and_filter(csv_file: Path) -> None:
    service = CatalogService(InMemoryVehicleRepository())
    assert service.import_csv(csv_file) == 5
    assert len(service.find_by_brand("toyota")) == 2
    assert [c.model for c in service.find_by_model("x5")] == ["X5"]
    assert service.filter_by_year(2022)[0].model == "Corolla"
    best = service.most_expensive()
    assert best is not None
    assert best.full_name == "BMW X5"
    assert service.average_price() == pytest.approx(28700.0)


def test_import_with_narrow_configuration_stops_on_first_bad_car(
    csv_file: Path,
) -> None:
    config = AppConfig(min_year=2020)
    repository = InMemoryVehicleRepository()
    service = CatalogService(repository, config)
    with pytest.raises(CarImportError, match="Line 2"):
        service.import_csv(csv_file)
    assert len(repository) == 0  # nothing half-imported


def test_lenient_import_keeps_only_cars_inside_the_range(
    csv_file: Path, caplog: pytest.LogCaptureFixture
) -> None:
    service = CatalogService(
        InMemoryVehicleRepository(), AppConfig(min_year=2020)
    )
    with caplog.at_level(logging.WARNING):
        stored = service.import_csv(csv_file, skip_invalid=True)
    assert stored == 3
    assert caplog.text.count("Skipped line") == 2
    assert all(car.year >= 2020 for car in service.repository.list_all())


def test_importing_two_files_accumulates_cars(
    csv_file: Path, write_csv
) -> None:
    second = write_csv("Kia,Rio,2020,9000,15000\n", name="second.csv")
    service = CatalogService(InMemoryVehicleRepository())
    service.import_csv(csv_file)
    service.import_csv(second)
    assert len(service.repository.list_all()) == 6
    assert service.find_by_brand("kia")[0].model == "Rio"
