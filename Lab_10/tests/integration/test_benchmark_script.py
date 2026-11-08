"""Integration: the benchmark script produces correct, complete results."""

import json
import subprocess
import sys
from pathlib import Path

import pytest
from benchmarks import benchmark

from car_catalog.profiling import load_records_csv

pytestmark = pytest.mark.integration

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def results(tmp_path_factory: pytest.TempPathFactory) -> Path:
    out = tmp_path_factory.mktemp("benchmark")
    assert benchmark.main(["--quick", "--output", str(out)]) == 0
    return out


def test_all_result_files_are_created(results: Path) -> None:
    expected = {
        "benchmark_results.csv",
        "worker_scaling.csv",
        "file_loading.csv",
        "caching.csv",
        "cache_info.json",
        "race.json",
        "hardware.json",
        "memory.json",
        "operations.txt",
        "profile_baseline.txt",
        "profile_numpy.txt",
        "summary_table.txt",
    }
    assert expected <= {p.name for p in results.iterdir()}


def test_every_optimized_result_is_correct(results: Path) -> None:
    for name in (
        "benchmark_results.csv",
        "worker_scaling.csv",
        "file_loading.csv",
        "caching.csv",
    ):
        records = load_records_csv(results / name)
        assert records
        assert all(r.correct for r in records), name


def test_methods_table_covers_every_method_and_size(results: Path) -> None:
    records = load_records_csv(results / "benchmark_results.csv")
    assert {r.data_size for r in records} == {2000, 5000}
    assert {r.method for r in records} == {
        "Sequential Python",
        "Threads",
        "Processes",
        "NumPy (with conversion)",
        "NumPy (arrays ready)",
    }
    baseline = [r for r in records if r.method == "Sequential Python"]
    assert all(r.speedup == pytest.approx(1.0) for r in baseline)
    assert all(len(r.runs) == 1 for r in records)  # --quick: 1 repeat


def test_numpy_is_faster_than_the_baseline(results: Path) -> None:
    records = load_records_csv(results / "benchmark_results.csv")
    numpy = [r for r in records if r.method == "NumPy (arrays ready)"]
    assert all(r.speedup > 3 for r in numpy)


def test_cache_report_shows_hits_and_correct_invalidation(
    results: Path,
) -> None:
    info = json.loads((results / "cache_info.json").read_text("utf-8"))
    assert info["hits"] > info["misses"]
    assert info["invalidation_changed_result"] is True
    assert info["after_update_matches_full_recompute"] is True


def test_race_report_shows_lost_updates_only_without_lock(
    results: Path,
) -> None:
    rows = json.loads((results / "race.json").read_text("utf-8"))
    assert all(r["lost"] == 0 for r in rows if r["variant"] == "Lock")
    assert any(r["lost"] > 0 for r in rows if r["variant"] == "Unsafe")


def test_charts_are_created(results: Path) -> None:
    pytest.importorskip("matplotlib")
    assert (results / "execution_time.png").stat().st_size > 1000
    assert (results / "speedup_workers.png").stat().st_size > 1000


def test_script_runs_directly_without_installation(tmp_path: Path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "benchmarks" / "benchmark.py"),
            "--quick",
            "--output",
            str(tmp_path),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "Sequential Python" in result.stdout
