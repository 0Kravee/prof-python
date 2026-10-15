"""Tests that reproduce automated (headless) running conditions."""

import subprocess
import sys
from collections import deque
from pathlib import Path

import pytest

from data_processor import analytics, processors
from data_processor.decorators import measure_time, track_history

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"


def run(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, *args],
        cwd=cwd,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )


def test_direct_run_without_installation() -> None:
    result = run(["main.py"], SRC / "data_processor")
    assert result.returncode == 0, result.stderr
    assert "BENCHMARK" in result.stdout


def test_direct_run_from_project_root() -> None:
    result = run(["src/data_processor/main.py"], ROOT)
    assert result.returncode == 0, result.stderr
    assert "Call history (deque)" in result.stdout


def test_track_history_records_calls() -> None:
    history: deque = deque(maxlen=2)

    @track_history(history)
    def first() -> int:
        return 1

    @track_history(history)
    def second() -> int:
        return 2

    first()
    second()
    first()
    assert list(history) == ["second", "first"]


def test_measure_time_keeps_result_and_name(
    capsys: pytest.CaptureFixture[str],
) -> None:
    @measure_time
    def add(a: int, b: int) -> int:
        return a + b

    assert add(2, b=3) == 5
    assert add.__name__ == "add"
    assert "add:" in capsys.readouterr().out


def test_compatibility_aliases() -> None:
    cars = [
        {
            "id": 1,
            "brand": "A",
            "model": "x",
            "year": 2020,
            "price": 10.0,
            "mileage": 5,
        },
        {
            "id": 2,
            "brand": "B",
            "model": "y",
            "year": 2021,
            "price": 30.0,
            "mileage": 1,
        },
    ]
    assert analytics.get_most_expensive(cars)["id"] == 2
    assert analytics.get_lowest_mileage(cars)["id"] == 2
    assert analytics.calculate_average(cars) == 20.0
    assert analytics.create_record(id=3)["id"] == 3
    assert processors.group_cars(cars).keys() == {"A", "B"}
    assert processors.count_by_brand(cars)["A"] == 1


def test_no_utf8_bom_in_sources() -> None:
    files = [*ROOT.rglob("*.py"), ROOT / ".gitignore", ROOT / "README.md"]
    for path in files:
        if ".venv" in path.parts or not path.exists():
            continue
        assert not path.read_bytes().startswith(b"\xef\xbb\xbf"), path
