"""Integration: the database demo (db_main) works end to end."""

import sqlite3
from pathlib import Path

import pytest

from car_catalog import db_main

pytestmark = pytest.mark.integration


def test_demo_in_memory_prints_all_sections(capsys) -> None:
    assert db_main.main([]) == 0
    out = capsys.readouterr().out
    assert "CARS IN DATABASE" in out
    assert "LAB 1 FUNCTIONS (SQL)" in out
    assert "GROUP BY" in out
    assert "Rolled back:" in out
    assert "Prices unchanged: True" in out


def test_demo_with_a_file_keeps_the_data(tmp_path: Path, capsys) -> None:
    path = tmp_path / "demo.db"
    assert db_main.main(["--database", str(path)]) == 0
    capsys.readouterr()
    with sqlite3.connect(path) as connection:
        count = connection.execute("SELECT COUNT(*) FROM cars").fetchone()
    connection.close()
    assert count == (5,)


def test_second_run_does_not_seed_twice(tmp_path: Path, capsys) -> None:
    path = tmp_path / "demo.db"
    db_main.main(["--database", str(path)])
    db_main.main(["--database", str(path)])
    capsys.readouterr()
    with sqlite3.connect(path) as connection:
        count = connection.execute("SELECT COUNT(*) FROM cars").fetchone()
    connection.close()
    assert count == (5,)  # prices were changed, rows were not duplicated


def test_describe_handles_a_missing_car() -> None:
    assert db_main.describe(None) == "(none)"


def test_module_can_be_run_as_a_script(
    monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    import runpy
    import sys

    monkeypatch.setattr(sys, "argv", ["db_main"])
    monkeypatch.delitem(sys.modules, "car_catalog.db_main")
    with pytest.raises(SystemExit) as excinfo:
        runpy.run_module("car_catalog.db_main", run_name="__main__")
    assert excinfo.value.code == 0
    assert "CARS IN DATABASE" in capsys.readouterr().out
