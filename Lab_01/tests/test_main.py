"""Tests that reproduce automated (headless) running conditions."""

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"


def run(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, *args],
        cwd=cwd,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )


def test_direct_run_without_installation() -> None:
    result = run(["main.py"], SRC / "car_catalog")
    assert result.returncode == 0, result.stderr
    assert "Most expensive car" in result.stdout


def test_direct_run_from_project_root() -> None:
    result = run(["src/car_catalog/main.py"], ROOT)
    assert result.returncode == 0, result.stderr
    assert "STATISTICS" in result.stdout


def test_module_run_headless() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "car_catalog.main"],
        cwd=ROOT,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
        env={"PYTHONPATH": str(SRC), "PATH": ""},
    )
    assert result.returncode == 0, result.stderr
    assert "EOFError" not in result.stderr


def test_menu_survives_closed_input(monkeypatch: pytest.MonkeyPatch) -> None:
    from car_catalog.main import run_menu

    def raise_eof(_: str = "") -> str:
        raise EOFError

    monkeypatch.setattr("builtins.input", raise_eof)
    run_menu([])  # must return without raising


def test_menu_commands(monkeypatch: pytest.MonkeyPatch) -> None:
    from car_catalog.main import create_demo_cars, run_menu

    answers = iter(
        [
            "1",
            "2",
            "bmw",
            "3",
            "abc",
            "10",
            "Kia",
            "Rio",
            "2020",
            "9000",
            "15000",
            "9",
            "x",
            "0",
        ]
    )
    monkeypatch.setattr("builtins.input", lambda _="": next(answers))
    cars = create_demo_cars()
    run_menu(cars)
    assert any(car.brand == "Kia" for car in cars)


def test_compat_package_runs() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "student_project.main"],
        cwd=ROOT,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
        env={"PYTHONPATH": str(SRC), "PATH": ""},
    )
    assert result.returncode == 0, result.stderr


def test_no_utf8_bom_in_sources() -> None:
    files = [*ROOT.rglob("*.py"), ROOT / ".gitignore", ROOT / "README.md"]
    for path in files:
        if ".venv" in path.parts or not path.exists():
            continue
        assert not path.read_bytes().startswith(b"\xef\xbb\xbf"), path
