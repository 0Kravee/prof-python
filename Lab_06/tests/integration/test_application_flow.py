"""Integration: whole application flow, configuration and entry points."""

import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import AsyncMock, Mock

import pytest

from car_catalog.config import load_config
from car_catalog.exceptions import ExternalServiceError, InvalidCarDataError
from car_catalog.repositories import InMemoryVehicleRepository
from car_catalog.services import CatalogService

pytestmark = pytest.mark.integration

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"


def build_service(config=None, **services) -> CatalogService:
    return CatalogService(InMemoryVehicleRepository(), config, **services)


def test_configuration_from_environment_drives_the_whole_flow(
    monkeypatch: pytest.MonkeyPatch,
    csv_file: Path,
    export_dir: Path,
) -> None:
    monkeypatch.setenv("CAR_CATALOG_MIN_YEAR", "2019")
    monkeypatch.setenv("CAR_CATALOG_MAX_PRICE", "40000")
    service = build_service(load_config())

    stored = service.import_csv(csv_file, skip_invalid=True)

    assert stored == 3  # 2018 Audi and the 48200 BMW X5 are rejected
    target = export_dir / "filtered.json"
    service.export_json(target)
    models = {item["model"] for item in json.loads(target.read_text("utf-8"))}
    assert models == {"Camry", "Corolla", "3 Series"}


def test_configuration_file_and_environment_are_combined(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, car_factory
) -> None:
    path = tmp_path / "settings.json"
    path.write_text('{"min_year": 2015, "max_year": 2020}', encoding="utf-8")
    monkeypatch.setenv("CAR_CATALOG_MAX_YEAR", "2022")
    service = build_service(load_config(path))

    service.add_car(car_factory(year=2022))  # allowed by the environment
    with pytest.raises(InvalidCarDataError):
        service.add_car(car_factory(year=2014))  # forbidden by the file
    assert len(service.repository.list_all()) == 1


def test_operation_flow_with_external_service_failure(
    csv_file: Path,
) -> None:
    info = Mock()
    info.lookup.side_effect = [
        {"body": "sedan"},
        ConnectionError("service is down"),
    ]
    service = build_service(info_service=info)
    service.import_csv(csv_file)
    first, second = service.repository.list_all()[:2]

    assert service.describe(first) == {"name": "Toyota Camry", "body": "sedan"}
    with pytest.raises(ExternalServiceError):
        service.describe(second)
    assert len(service.repository.list_all()) == 5  # catalog is unchanged


@pytest.mark.asyncio
async def test_async_enrichment_of_imported_catalog(csv_file: Path) -> None:
    info = AsyncMock()
    info.fetch.return_value = {"warranty": "2 years"}
    service = build_service(async_info_service=info)
    service.import_csv(csv_file)

    result = await service.describe_all_async()

    assert len(result) == 5
    assert all(item["warranty"] == "2 years" for item in result)
    assert info.fetch.await_count == 5


def run_python(
    args: list[str], cwd: Path, env=None
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, *args],
        cwd=cwd,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
        env=env,
    )


def test_entry_point_runs_without_installation_and_without_input() -> None:
    result = run_python(["src/car_catalog/main.py"], ROOT)
    assert result.returncode == 0, result.stderr
    assert "STATISTICS" in result.stdout
    assert "EOFError" not in result.stderr


def test_compatibility_package_runs_headless() -> None:
    result = run_python(
        ["-m", "student_project.main"],
        ROOT,
        env={"PYTHONPATH": str(SRC), "PATH": ""},
    )
    assert result.returncode == 0, result.stderr
    assert "Most expensive car" in result.stdout
