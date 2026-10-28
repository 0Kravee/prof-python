"""Shared fixtures."""

from collections.abc import Iterator
from pathlib import Path

import pytest

from reliable_importer.logging_config import close_logging
from reliable_importer.models import ValidationRules

HEADER = "vehicle_id,brand,model,year,price,mileage\n"

GOOD_ROWS = (
    "1,Toyota,Camry,2019,21500,45000\n"
    "2,BMW,X5,2021,48200,18000\n"
    "3,Audi,A4,2018,23000,62000\n"
)

BAD_ROWS = (
    "4,,Golf,2019,18000,40000\n"
    "5,Kia,Rio,1850,9000,5000\n"
    "abc,Ford,Focus,2018,100,1\n"
)


@pytest.fixture(autouse=True)
def clean_logging() -> Iterator[None]:
    """Never leak file handlers between tests."""
    yield
    close_logging()


@pytest.fixture
def rules() -> ValidationRules:
    return ValidationRules(1990, 2026, 0.0, 200000.0)


@pytest.fixture
def csv_file(tmp_path: Path) -> Path:
    path = tmp_path / "vehicles.csv"
    path.write_text(HEADER + GOOD_ROWS + BAD_ROWS, encoding="utf-8")
    return path


def make_config(
    folder: Path,
    *,
    skip: bool = True,
    input_name: str = "vehicles.csv",
    output_name: str = "out/result.json",
    extra_processing: str = "",
) -> Path:
    config = folder / "config.yaml"
    config.write_text(
        "schema_version: 1\n"
        f"input:\n  path: {input_name}\n"
        f"output:\n  path: {output_name}\n  errors_path: errors.csv\n"
        "processing:\n"
        f"  skip_invalid: {str(skip).lower()}\n"
        "  minimum_year: 1990\n  maximum_year: 2026\n"
        "  minimum_price: 0\n  maximum_price: 200000\n"
        f"{extra_processing}"
        "logging:\n  level: INFO\n  path: app.log\n",
        encoding="utf-8",
    )
    return config
