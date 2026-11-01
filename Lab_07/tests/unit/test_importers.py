"""Unit tests of the CSV import (files are created with tmp_path)."""

import logging
from pathlib import Path

import pytest

from car_catalog.config import AppConfig
from car_catalog.exceptions import CarImportError
from car_catalog.importers import import_cars_csv, parse_car_row


def test_valid_file_is_imported(csv_file: Path) -> None:
    cars = import_cars_csv(csv_file)
    assert len(cars) == 5
    assert cars[1].full_name == "BMW X5"
    assert cars[1].price == pytest.approx(48200.0)


def test_header_only_file_gives_empty_list(write_csv) -> None:
    assert import_cars_csv(write_csv("")) == []


def test_file_with_utf8_bom_is_supported(tmp_path: Path) -> None:
    path = tmp_path / "excel.csv"
    path.write_bytes(
        b"\xef\xbb\xbfbrand,model,year,price,mileage\nKia,Rio,2020,9000,100\n"
    )
    assert import_cars_csv(path)[0].brand == "Kia"


@pytest.mark.parametrize(
    ("body", "line", "reason"),
    [
        ("Kia,Rio,abcd,9000,100\n", 2, "invalid literal"),
        ("Kia,Rio,2020,cheap,100\n", 2, "could not convert"),
        ("Kia,Rio,2020,9000,1.5\n", 2, "invalid literal"),
        (",Rio,2020,9000,100\n", 2, "Brand and model"),
        ("Kia,Rio,1800,9000,100\n", 2, "Year"),
        ("Kia,Rio,2020,-5,100\n", 2, "negative"),
        ("Kia,Rio,2020\n", 2, "could not convert"),
        ("Kia,Rio,2020,9000,100,extra\n", 2, "too many fields"),
        ("Kia,Rio,2020,9000,100\nBMW,X5,oops,1,1\n", 3, "invalid literal"),
    ],
)
def test_malformed_record_raises_import_error_with_line_number(
    write_csv, body, line, reason
) -> None:
    with pytest.raises(CarImportError, match=reason) as excinfo:
        import_cars_csv(write_csv(body))
    assert excinfo.value.line_number == line
    assert f"Line {line}" in str(excinfo.value)


def test_import_error_keeps_the_original_cause(write_csv) -> None:
    with pytest.raises(CarImportError) as excinfo:
        import_cars_csv(write_csv("Kia,Rio,abcd,9000,100\n"))
    assert isinstance(excinfo.value.__cause__, ValueError)


def test_skip_invalid_keeps_good_records_and_logs_bad_ones(
    write_csv, caplog: pytest.LogCaptureFixture
) -> None:
    path = write_csv(
        "Kia,Rio,2020,9000,100\n"
        "Bad,Row,xxxx,1,1\n"
        "BMW,X5,2021,48200,18000\n"
    )
    with caplog.at_level(logging.WARNING, logger="car_catalog.importers"):
        cars = import_cars_csv(path, skip_invalid=True)
    assert [car.brand for car in cars] == ["Kia", "BMW"]
    assert "Skipped line 3" in caplog.text


def test_config_range_is_applied_during_import(write_csv) -> None:
    path = write_csv("Kia,Rio,2005,9000,100\n")
    with pytest.raises(CarImportError, match="outside 2010"):
        import_cars_csv(path, AppConfig(min_year=2010))


def test_missing_columns(tmp_path: Path) -> None:
    path = tmp_path / "bad.csv"
    path.write_text("brand,model\nKia,Rio\n", encoding="utf-8")
    with pytest.raises(CarImportError, match="mileage, price, year") as err:
        import_cars_csv(path)
    assert err.value.line_number == 1


def test_completely_empty_file(tmp_path: Path) -> None:
    path = tmp_path / "empty.csv"
    path.write_text("", encoding="utf-8")
    with pytest.raises(CarImportError, match="Missing columns"):
        import_cars_csv(path)


def test_missing_file(tmp_path: Path) -> None:
    with pytest.raises(CarImportError, match="Cannot read file"):
        import_cars_csv(tmp_path / "absent.csv")


def test_binary_file_is_reported_as_import_error(tmp_path: Path) -> None:
    path = tmp_path / "binary.csv"
    path.write_bytes(b"\xff\xfe\x00\x81\x82" * 20)
    with pytest.raises(CarImportError):
        import_cars_csv(path)


def test_parse_car_row_treats_none_as_empty() -> None:
    row = {"brand": None, "model": "X", "year": "2020",
           "price": "1", "mileage": "1"}
    with pytest.raises(ValueError):
        parse_car_row(row)
