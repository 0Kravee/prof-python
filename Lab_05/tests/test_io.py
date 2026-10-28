"""Streaming readers, importers, exporters, atomic output, context managers."""

import json
import logging
from collections.abc import Iterator
from pathlib import Path

import pytest

from conftest import BAD_ROWS, GOOD_ROWS, HEADER
from reliable_importer.exceptions import DataExportError, DataImportError
from reliable_importer.exporters import (
    JsonExporter,
    JsonLinesExporter,
    select_exporter,
)
from reliable_importer.importers import (
    CsvImporter,
    JsonImporter,
    JsonLinesImporter,
    YamlImporter,
    select_importer,
)
from reliable_importer.models import Vehicle
from reliable_importer.readers import (
    read_csv_rows,
    read_json_rows,
    read_jsonl_rows,
    read_yaml_rows,
)
from reliable_importer.utils import atomic_output, logged_operation

CARS = [
    Vehicle(1, "Toyota", "Camry", 2019, 21500.0, 45000),
    Vehicle(2, "Škoda", "Octavia", 2023, 26500.5, 1200),
]


# -------------------------------------------------------------- CSV reader
def test_csv_reader_streams_with_physical_line_numbers(csv_file: Path) -> None:
    rows = read_csv_rows(csv_file)
    assert isinstance(rows, Iterator)
    first = next(rows)
    assert first.line_number == 2 and first.data["brand"] == "Toyota"
    assert [r.line_number for r in rows] == [3, 4, 5, 6, 7]


def test_csv_reader_is_lazy(tmp_path: Path) -> None:
    """The error appears only when the generator is consumed."""
    rows = read_csv_rows(tmp_path / "missing.csv")  # no exception yet
    with pytest.raises(DataImportError) as info:
        next(rows)
    assert isinstance(info.value.__cause__, FileNotFoundError)


def test_csv_missing_columns(tmp_path: Path) -> None:
    path = tmp_path / "x.csv"
    path.write_text("vehicle_id,brand\n1,A\n", encoding="utf-8")
    with pytest.raises(DataImportError, match="Missing columns"):
        list(read_csv_rows(path))


def test_csv_empty_file(tmp_path: Path) -> None:
    path = tmp_path / "x.csv"
    path.write_text("", encoding="utf-8")
    with pytest.raises(DataImportError, match="empty"):
        list(read_csv_rows(path))


def test_csv_bad_encoding(tmp_path: Path) -> None:
    path = tmp_path / "x.csv"
    path.write_bytes(HEADER.encode() + b"1,\xff\xfe,M,2020,1,1\n")
    with pytest.raises(DataImportError) as info:
        list(read_csv_rows(path))
    assert isinstance(info.value.__cause__, UnicodeDecodeError)


def test_csv_row_with_extra_and_missing_fields(tmp_path: Path) -> None:
    path = tmp_path / "x.csv"
    path.write_text(HEADER + "1,A,B,2020,5,1,EXTRA\n2,A,B\n", encoding="utf-8")
    rows = list(read_csv_rows(path))
    assert None in rows[0].data  # surplus values are kept under key None
    assert rows[1].data["price"] is None


# ------------------------------------------------- other input formats
def test_jsonl_reader_skips_blank_lines(tmp_path: Path) -> None:
    path = tmp_path / "x.jsonl"
    path.write_text('{"a": 1}\n\n{"a": 2}\n', encoding="utf-8")
    assert [(r.line_number, r.data["a"]) for r in read_jsonl_rows(path)] == [
        (1, 1),
        (3, 2),
    ]


def test_jsonl_errors(tmp_path: Path) -> None:
    path = tmp_path / "x.jsonl"
    path.write_text('{"a": 1}\n{broken\n', encoding="utf-8")
    with pytest.raises(DataImportError, match="line 2") as info:
        list(read_jsonl_rows(path))
    assert isinstance(info.value.__cause__, json.JSONDecodeError)
    path.write_text("[1, 2]\n", encoding="utf-8")
    with pytest.raises(DataImportError, match="not a JSON object"):
        list(read_jsonl_rows(path))


def test_json_reader(tmp_path: Path) -> None:
    path = tmp_path / "x.json"
    path.write_text('[{"a": 1}, {"a": 2}]', encoding="utf-8")
    assert [r.data["a"] for r in read_json_rows(path)] == [1, 2]
    path.write_text('{"vehicles": [{"a": 3}]}', encoding="utf-8")
    assert [r.data["a"] for r in read_json_rows(path)] == [3]


@pytest.mark.parametrize(
    ("content", "message"),
    [
        ("{broken", "Invalid JSON"),
        ('{"x": 1}', "list of records"),
        ("[1, 2]", "not an object"),
    ],
)
def test_json_reader_errors(
    tmp_path: Path, content: str, message: str
) -> None:
    path = tmp_path / "x.json"
    path.write_text(content, encoding="utf-8")
    with pytest.raises(DataImportError, match=message):
        list(read_json_rows(path))


def test_yaml_reader(tmp_path: Path) -> None:
    path = tmp_path / "x.yaml"
    path.write_text("- a: 1\n- a: 2\n", encoding="utf-8")
    assert [r.data["a"] for r in read_yaml_rows(path)] == [1, 2]
    path.write_text("a: [unclosed", encoding="utf-8")
    with pytest.raises(DataImportError, match="Invalid YAML"):
        list(read_yaml_rows(path))


def test_yaml_reader_without_pyyaml(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from reliable_importer import readers

    monkeypatch.setattr(readers, "load_pyyaml", lambda: None)
    path = tmp_path / "x.yaml"
    path.write_text("- a: 1\n", encoding="utf-8")
    with pytest.raises(DataImportError, match="PyYAML"):
        list(read_yaml_rows(path))


def test_importer_selection(tmp_path: Path) -> None:
    assert isinstance(select_importer(Path("a.CSV")), CsvImporter)
    assert isinstance(select_importer(Path("a.json")), JsonImporter)
    assert isinstance(select_importer(Path("a.jsonl")), JsonLinesImporter)
    assert isinstance(select_importer(Path("a.ndjson")), JsonLinesImporter)
    assert isinstance(select_importer(Path("a.yml")), YamlImporter)
    assert isinstance(select_importer(Path("a.txt"), "csv"), CsvImporter)
    with pytest.raises(DataImportError, match="detect"):
        select_importer(Path("a.txt"))
    with pytest.raises(DataImportError):
        select_importer(Path("a.csv"), "xml")


# --------------------------------------------------------------- exporters
def test_json_exporter_writes_valid_json(tmp_path: Path) -> None:
    path = tmp_path / "deep" / "out.json"
    assert JsonExporter().export(CARS, path) == 2
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data[0] == CARS[0].to_dict() and data[1]["brand"] == "Škoda"
    assert path.read_text(encoding="utf-8").startswith("[\n  {\n    ")


def test_json_exporter_empty_input(tmp_path: Path) -> None:
    path = tmp_path / "out.json"
    assert JsonExporter().export([], path) == 0
    assert json.loads(path.read_text(encoding="utf-8")) == []


def test_jsonl_exporter(tmp_path: Path) -> None:
    path = tmp_path / "out.jsonl"
    assert JsonLinesExporter().export(CARS, path) == 2
    lines = path.read_text(encoding="utf-8").splitlines()
    assert [json.loads(line)["vehicle_id"] for line in lines] == [1, 2]


def test_exporter_selection() -> None:
    assert isinstance(select_exporter(Path("a.json")), JsonExporter)
    assert isinstance(select_exporter(Path("a.jsonl")), JsonLinesExporter)
    assert isinstance(select_exporter(Path("a.out")), JsonExporter)
    assert isinstance(
        select_exporter(Path("a.out"), "jsonl"), JsonLinesExporter
    )
    with pytest.raises(DataExportError):
        select_exporter(Path("a.json"), "xml")


# ----------------------------------------------------------- atomic output
def failing(after: int) -> Iterator[Vehicle]:
    yield from CARS[:after]
    raise OSError("disk full")


def test_failed_export_keeps_the_previous_output(tmp_path: Path) -> None:
    path = tmp_path / "out.json"
    JsonExporter().export(CARS, path)
    before = path.read_bytes()
    with pytest.raises(DataExportError) as info:
        JsonExporter().export(failing(2), path)
    assert isinstance(info.value.__cause__, OSError)
    assert path.read_bytes() == before
    assert not list(tmp_path.glob("*.tmp"))


def test_failed_first_export_leaves_no_file(tmp_path: Path) -> None:
    path = tmp_path / "out.json"
    with pytest.raises(DataExportError):
        JsonExporter().export(failing(1), path)
    assert not path.exists() and not list(tmp_path.glob("*.tmp"))


def test_unserialisable_value_is_a_export_error(tmp_path: Path) -> None:
    bad = Vehicle(1, "A", "B", 2020, 1.0, 1)
    object.__setattr__(bad, "brand", object())
    with pytest.raises(DataExportError):
        JsonExporter().export([bad], tmp_path / "out.json")
    assert not list(tmp_path.iterdir())


def test_backup_of_the_existing_output(tmp_path: Path) -> None:
    path = tmp_path / "out.json"
    JsonExporter().export(CARS[:1], path)
    old = path.read_bytes()
    JsonExporter(backup=True).export(CARS, path)
    assert (tmp_path / "out.json.bak").read_bytes() == old
    assert path.read_bytes() != old


def test_atomic_output_context_manager_directly(tmp_path: Path) -> None:
    path = tmp_path / "f.txt"
    with atomic_output(path) as file:
        file.write("hello")
        assert (tmp_path / "f.txt.tmp").exists() and not path.exists()
    assert path.read_text(encoding="utf-8") == "hello"
    with pytest.raises(RuntimeError):
        with atomic_output(path) as file:
            file.write("lost")
            raise RuntimeError("boom")
    assert path.read_text(encoding="utf-8") == "hello"
    assert not (tmp_path / "f.txt.tmp").exists()


def test_atomic_output_cleans_up_on_keyboard_interrupt(tmp_path: Path) -> None:
    path = tmp_path / "f.txt"
    with pytest.raises(KeyboardInterrupt):
        with atomic_output(path) as file:
            file.write("x")
            raise KeyboardInterrupt
    assert not path.exists() and not list(tmp_path.glob("*.tmp"))


# ------------------------------------------------------- logged_operation
def test_logged_operation_success(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO)
    with logged_operation("Demo"):
        pass
    assert "Demo started" in caplog.text and "Demo finished in" in caplog.text


def test_logged_operation_logs_and_reraises(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO)
    with pytest.raises(ValueError):
        with logged_operation("Demo"):
            raise ValueError("bad")
    assert "Demo failed" in caplog.text and "Traceback" in caplog.text
    assert "finished" not in caplog.text


def test_dataset_constants_are_consistent() -> None:
    assert GOOD_ROWS.count("\n") == 3 and BAD_ROWS.count("\n") == 3
