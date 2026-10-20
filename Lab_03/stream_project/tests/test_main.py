"""Tests that reproduce automated (headless) running conditions."""

import subprocess
import sys
from pathlib import Path

import pytest

from stream_processor import analytics, batches, generators, iterators
from stream_processor.benchmark import consume_lazy, generate_test_file
from stream_processor.pipeline import (
    build_pipeline,
    read_all_cars,
    read_cars_lazy,
)

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"


def run(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, *args],
        cwd=cwd,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )


def test_direct_run_without_installation() -> None:
    result = run(["main.py"], SRC / "stream_processor")
    assert result.returncode == 0, result.stderr
    assert "Streaming pipeline on input.csv" in result.stdout


def test_direct_run_from_project_root() -> None:
    result = run(["src/stream_processor/main.py"], ROOT)
    assert result.returncode == 0, result.stderr
    assert "Lazy processing of 100 000 records" in result.stdout


def test_benchmark_direct_run_quick() -> None:
    result = run(["benchmark.py", "--quick"], SRC / "stream_processor")
    assert result.returncode == 0, result.stderr
    assert "EARLY TERMINATION" in result.stdout
    assert "True" in result.stdout


def test_default_input_is_found_from_any_directory(tmp_path: Path) -> None:
    result = run([str(SRC / "stream_processor" / "main.py")], tmp_path)
    assert result.returncode == 0, result.stderr


def test_module_run_headless() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "stream_processor.main"],
        cwd=ROOT,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
        env={"PYTHONPATH": str(SRC), "PATH": ""},
    )
    assert result.returncode == 0, result.stderr
    assert "EOFError" not in result.stderr


def test_compat_package_runs() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "student_project.main"],
        cwd=ROOT,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
        env={"PYTHONPATH": str(SRC), "PATH": ""},
    )
    assert result.returncode == 0, result.stderr
    assert "Streaming pipeline on input.csv" in result.stdout


def test_eager_and_lazy_readers(tmp_path: Path) -> None:
    path = tmp_path / "cars.csv"
    generate_test_file(path, 1_000)
    eager = read_all_cars(path, brand="BMW")
    lazy = read_cars_lazy(path, brand="BMW")
    assert isinstance(eager, list)
    assert list(lazy) == eager


def test_consume_lazy_counts_without_storing(tmp_path: Path) -> None:
    path = tmp_path / "cars.csv"
    generate_test_file(path, 1_000)
    assert consume_lazy(build_pipeline(path)) == 995


def test_pipeline_can_be_closed_early(tmp_path: Path) -> None:
    path = tmp_path / "cars.csv"
    generate_test_file(path, 1_000)
    pipeline = build_pipeline(path)
    next(pipeline)
    pipeline.close()
    with pytest.raises(StopIteration):
        next(pipeline)


def test_numeric_pipeline_helpers() -> None:
    lines = ["3", "-1", "x", "5", "0"]
    numbers = generators.positive_only(generators.parse_numbers(lines))
    assert analytics.streaming_average(numbers) == 4.0
    assert analytics.streaming_average([]) == 0.0


def test_compatibility_aliases() -> None:
    assert batches.batched_cars is batches.batched
    assert list(iterators.NumberIterator(0, 3)) == [0, 1, 2]


def test_no_utf8_bom_in_sources() -> None:
    files = [*ROOT.rglob("*.py"), ROOT / ".gitignore", ROOT / "README.md"]
    files.append(ROOT / "data" / "input.csv")
    for path in files:
        if ".venv" in path.parts or not path.exists():
            continue
        assert not path.read_bytes().startswith(b"\xef\xbb\xbf"), path
