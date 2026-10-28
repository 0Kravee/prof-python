"""Streaming import service, summary, error report and the pipeline."""

import csv
import json
import logging
from pathlib import Path

import pytest

from conftest import make_config
from reliable_importer.config import load_config
from reliable_importer.exceptions import RecordValidationError
from reliable_importer.importers import CsvImporter
from reliable_importer.logging_config import close_logging, configure_logging
from reliable_importer.models import ValidationRules, Vehicle
from reliable_importer.services import (
    ErrorCsvReport,
    ImportStatistics,
    SummaryAccumulator,
    import_vehicles,
    run_import,
    track,
)


def run(
    path: Path, rules: ValidationRules, *, skip: bool
) -> tuple[list[Vehicle], ImportStatistics, list[int]]:
    stats = ImportStatistics()
    rejected: list[int] = []

    class Sink:
        def write(self, error: RecordValidationError, data: object) -> None:
            assert error.line_number is not None
            rejected.append(error.line_number)

    vehicles: list[Vehicle] = []
    try:
        for vehicle in import_vehicles(
            CsvImporter(),
            path,
            skip_invalid=skip,
            rules=rules,
            statistics=stats,
            error_sink=Sink(),
        ):
            vehicles.append(vehicle)
    except RecordValidationError:
        pass
    return vehicles, stats, rejected


def test_tolerant_mode_skips_invalid_records(
    csv_file: Path, rules: ValidationRules
) -> None:
    vehicles, stats, rejected = run(csv_file, rules, skip=True)
    assert [v.vehicle_id for v in vehicles] == [1, 2, 3]
    assert (stats.total, stats.valid, stats.invalid) == (6, 3, 3)
    assert rejected == [5, 6, 7]


def test_strict_mode_aborts_on_the_first_invalid_record(
    csv_file: Path, rules: ValidationRules
) -> None:
    vehicles, stats, rejected = run(csv_file, rules, skip=False)
    assert [v.vehicle_id for v in vehicles] == [1, 2, 3]
    assert (stats.total, stats.valid, stats.invalid) == (4, 3, 1)
    assert rejected == [5]


def test_invalid_records_are_logged_with_the_line_number(
    csv_file: Path, rules: ValidationRules, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.WARNING)
    run(csv_file, rules, skip=True)
    assert "Invalid record at line 5: Vehicle brand is empty" in caplog.text
    assert "line 6: Year must be between 1990 and 2026" in caplog.text


def test_summary_is_computed_in_one_pass() -> None:
    cars = [
        Vehicle(1, "A", "a", 2020, 100.0, 50),
        Vehicle(2, "B", "b", 2021, 300.0, 10),
        Vehicle(3, "C", "c", 2022, 200.0, 70),
    ]
    summary = SummaryAccumulator()
    consumed = list(track(iter(cars), summary))
    assert consumed == cars and summary.count == 3
    assert summary.average_price == 200.0
    assert summary.most_expensive == cars[1]
    assert summary.lowest_mileage == cars[1]
    assert SummaryAccumulator().average_price == 0.0


def test_error_csv_report(tmp_path: Path) -> None:
    path = tmp_path / "errors.csv"
    error = RecordValidationError("bad price", line_number=9, field="price")
    with ErrorCsvReport(path) as report:
        report.write(error, {"vehicle_id": "1", "price": "x"})
    with path.open(encoding="utf-8", newline="") as file:
        rows = list(csv.reader(file))
    assert rows[0] == ["line_number", "field", "message", "raw_record"]
    assert rows[1][:3] == ["9", "price", "bad price"]
    assert json.loads(rows[1][3]) == {"vehicle_id": "1", "price": "x"}


def test_error_report_is_committed_even_when_processing_aborts(
    tmp_path: Path,
) -> None:
    path = tmp_path / "errors.csv"
    with pytest.raises(RuntimeError):
        with ErrorCsvReport(path) as report:
            report.write(RecordValidationError("x", line_number=1), {})
            raise RuntimeError("abort")
    assert path.exists() and "line_number" in path.read_text(encoding="utf-8")
    assert not list(tmp_path.glob("*.tmp"))


def test_error_report_without_a_path_is_a_noop() -> None:
    with ErrorCsvReport(None) as report:
        report.write(RecordValidationError("x"), {})


def test_run_import_end_to_end(tmp_path: Path, csv_file: Path) -> None:
    config = load_config(make_config(tmp_path), environ={})
    result = run_import(config)
    assert (result.statistics.total, result.statistics.valid) == (6, 3)
    assert (result.statistics.invalid, result.statistics.exported) == (3, 3)
    data = json.loads((tmp_path / "out" / "result.json").read_text("utf-8"))
    assert [item["vehicle_id"] for item in data] == [1, 2, 3]
    assert result.summary.most_expensive is not None
    assert result.summary.most_expensive.model == "X5"
    assert result.summary.average_price == pytest.approx(30900.0)
    errors = (tmp_path / "errors.csv").read_text(encoding="utf-8")
    assert errors.count("\n") == 4


def test_run_import_strict_keeps_statistics_and_old_output(
    tmp_path: Path, csv_file: Path
) -> None:
    out = tmp_path / "out" / "result.json"
    out.parent.mkdir()
    out.write_text("[]", encoding="utf-8")
    config = load_config(make_config(tmp_path, skip=False), environ={})
    stats = ImportStatistics()
    with pytest.raises(RecordValidationError):
        run_import(config, stats)
    assert (stats.total, stats.valid, stats.invalid) == (4, 3, 1)
    assert out.read_text(encoding="utf-8") == "[]"


def test_jsonl_pipeline(tmp_path: Path, csv_file: Path) -> None:
    config = load_config(
        make_config(tmp_path, output_name="out.jsonl"), environ={}
    )
    run_import(config)
    lines = (tmp_path / "out.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 3 and json.loads(lines[0])["brand"] == "Toyota"


def test_json_input_pipeline(tmp_path: Path) -> None:
    (tmp_path / "in.json").write_text(
        json.dumps(
            [
                {
                    "vehicle_id": 1,
                    "brand": "A",
                    "model": "B",
                    "year": 2020,
                    "price": 10,
                    "mileage": 1,
                },
                {
                    "vehicle_id": 2,
                    "brand": "",
                    "model": "B",
                    "year": 2020,
                    "price": 10,
                    "mileage": 1,
                },
            ]
        ),
        encoding="utf-8",
    )
    config = load_config(
        make_config(tmp_path, input_name="in.json"), environ={}
    )
    result = run_import(config)
    assert (result.statistics.valid, result.statistics.invalid) == (1, 1)


# ----------------------------------------------------------------- logging
def test_configure_logging_creates_directory_and_file(tmp_path: Path) -> None:
    path = tmp_path / "logs" / "app.log"
    configure_logging("DEBUG", path, max_bytes=500, backup_count=2)
    logging.getLogger("demo").debug("hello debug")
    close_logging()
    assert "hello debug" in path.read_text(encoding="utf-8")


def test_log_rotation(tmp_path: Path) -> None:
    path = tmp_path / "app.log"
    configure_logging("INFO", path, max_bytes=300, backup_count=2)
    for index in range(40):
        logging.getLogger("demo").info("line %s %s", index, "x" * 30)
    close_logging()
    assert (tmp_path / "app.log.1").exists()
    assert not (tmp_path / "app.log.3").exists()


def test_log_level_is_respected(tmp_path: Path) -> None:
    path = tmp_path / "app.log"
    configure_logging("WARNING", path)
    logging.getLogger("demo").info("quiet")
    logging.getLogger("demo").warning("loud")
    close_logging()
    text = path.read_text(encoding="utf-8")
    assert "loud" in text and "quiet" not in text


def test_close_logging_removes_handlers(tmp_path: Path) -> None:
    configure_logging("INFO", tmp_path / "a.log")
    assert logging.getLogger().handlers
    close_logging()
    assert not logging.getLogger().handlers
