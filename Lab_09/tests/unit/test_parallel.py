"""Unit tests of threads, processes and synchronization."""

import time
from pathlib import Path

import pytest

from car_catalog import analytics as an
from car_catalog import parallel as par
from car_catalog.datagen import generate_cars, generate_csv_files
from car_catalog.exceptions import CarImportError


@pytest.fixture(scope="module")
def cars():
    return generate_cars(1200, seed=21)


@pytest.fixture(scope="module")
def reference(cars):
    return an.manufacturer_statistics_python(cars)


# --- splitting work ------------------------------------------------------


@pytest.mark.parametrize(
    ("total", "parts", "expected"),
    [
        (10, 2, [(0, 5), (5, 10)]),
        (10, 3, [(0, 4), (4, 7), (7, 10)]),
        (3, 8, [(0, 1), (1, 2), (2, 3)]),
        (0, 4, []),
        (7, 1, [(0, 7)]),
    ],
)
def test_split_slices(total, parts, expected) -> None:
    assert par.split_slices(total, parts) == expected


def test_slices_cover_everything_without_overlap() -> None:
    slices = par.split_slices(1001, 7)
    assert slices[0][0] == 0 and slices[-1][1] == 1001
    assert all(a[1] == b[0] for a, b in zip(slices, slices[1:]))
    assert max(b - a for a, b in slices) - min(b - a for a, b in slices) <= 1


def test_split_slices_rejects_zero_parts() -> None:
    with pytest.raises(ValueError):
        par.split_slices(10, 0)


def test_default_workers_is_positive() -> None:
    assert par.default_workers() >= 1


def test_default_workers_without_affinity_uses_cpu_count(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Windows and macOS have no os.sched_getaffinity."""
    monkeypatch.delattr(par.os, "sched_getaffinity", raising=False)
    monkeypatch.setattr(par.os, "cpu_count", lambda: 6)
    assert par.default_workers() == 6
    monkeypatch.setattr(par.os, "cpu_count", lambda: None)
    assert par.default_workers() == 1


# --- the code that runs inside worker processes -------------------------
# Child processes are not measured by coverage, so the worker function and
# the chunk builder are also tested directly in this process.


def test_columns_chunk_contains_the_requested_slice(cars) -> None:
    brands, years, prices, mileages = par._columns_chunk(cars, 10, 15)
    assert brands == [c.brand for c in cars[10:15]]
    assert years == [c.year for c in cars[10:15]]
    assert prices == [c.price for c in cars[10:15]]
    assert mileages == [c.mileage for c in cars[10:15]]


def test_worker_function_aggregates_a_chunk(cars, reference) -> None:
    chunk = par._columns_chunk(cars, 0, len(cars))
    result = an.finalize_statistics(par.partial_from_columns(chunk))
    assert an.statistics_close(reference, result)


def test_worker_function_results_can_be_merged(cars, reference) -> None:
    half = len(cars) // 2
    parts = [
        par.partial_from_columns(par._columns_chunk(cars, 0, half)),
        par.partial_from_columns(par._columns_chunk(cars, half, len(cars))),
    ]
    merged = an.finalize_statistics(an.merge_partials(parts))
    assert an.statistics_close(reference, merged)


def test_worker_function_of_an_empty_chunk() -> None:
    assert par.partial_from_columns(([], [], [], [])) == {}


# --- CPU-bound analytics: threads and processes ---------------------------


@pytest.mark.parametrize("workers", [1, 2, 4])
def test_threads_give_the_same_result(cars, reference, workers) -> None:
    result = par.manufacturer_statistics_threads(cars, workers)
    assert an.statistics_close(reference, result)


@pytest.mark.parametrize("workers", [1, 2])
def test_processes_give_the_same_result(cars, reference, workers) -> None:
    result = par.manufacturer_statistics_processes(cars, workers)
    assert an.statistics_close(reference, result)


@pytest.mark.parametrize("chunks", [1, 3])
def test_process_chunking_does_not_change_the_result(
    cars, reference, chunks
) -> None:
    result = par.manufacturer_statistics_processes(
        cars, workers=2, chunks_per_worker=chunks
    )
    assert an.statistics_close(reference, result)


def test_more_workers_than_cars_is_fine(car_factory) -> None:
    cars = [car_factory(), car_factory(brand="BMW")]
    expected = an.manufacturer_statistics_python(cars)
    assert an.statistics_close(
        expected, par.manufacturer_statistics_threads(cars, 8)
    )
    assert an.statistics_close(
        expected, par.manufacturer_statistics_processes(cars, 4)
    )


def test_empty_catalog_in_parallel_versions() -> None:
    assert par.manufacturer_statistics_threads([], 2) == {}
    assert par.manufacturer_statistics_processes([], 2) == {}


@pytest.mark.parametrize(
    "call",
    [
        lambda: par.manufacturer_statistics_threads([], 0),
        lambda: par.manufacturer_statistics_processes([], 0),
        lambda: par.manufacturer_statistics_processes([], 2, 0),
        lambda: par.load_catalogs_threads([], 0),
    ],
)
def test_invalid_worker_numbers_are_rejected(call) -> None:
    with pytest.raises(ValueError):
        call()


def test_parallel_result_equals_numpy_result(cars) -> None:
    numpy_result = an.manufacturer_statistics_numpy(an.to_columns(cars))
    assert an.statistics_close(
        numpy_result, par.manufacturer_statistics_processes(cars, 2)
    )


# --- I/O-bound: loading files ------------------------------------------


@pytest.fixture
def files(tmp_path: Path) -> list[Path]:
    return generate_csv_files(tmp_path / "catalogs", files=4,
                              rows_per_file=300, seed=9)


def test_all_loaders_return_the_same_cars_in_the_same_order(files) -> None:
    sequential = par.load_catalogs_sequential(files)
    assert len(sequential) == 1200
    assert par.load_catalogs_threads(files, workers=3) == sequential
    assert par.load_catalogs_manual_threads(files) == sequential


def test_no_files_gives_no_cars() -> None:
    assert par.load_catalogs_sequential([]) == []
    assert par.load_catalogs_threads([], 2) == []
    assert par.load_catalogs_manual_threads([]) == []


def test_broken_file_error_reaches_the_caller(files, tmp_path) -> None:
    bad = tmp_path / "bad.csv"
    bad.write_text("brand,model,year,price,mileage\nKia,Rio,xxxx,1,1\n",
                   encoding="utf-8")
    with pytest.raises(CarImportError):
        par.load_catalogs_threads([*files, bad], workers=2)
    with pytest.raises(CarImportError):
        par.load_catalogs_manual_threads([*files, bad])


def test_missing_file_is_reported(tmp_path) -> None:
    with pytest.raises(CarImportError):
        par.load_catalogs_threads([tmp_path / "absent.csv"], workers=2)


def test_threads_overlap_waiting_time(files) -> None:
    """Sleeping releases the GIL, so four 0.1 s waits overlap."""
    started = time.perf_counter()
    par.load_catalogs_sequential(files, delay=0.1)
    sequential = time.perf_counter() - started
    started = time.perf_counter()
    par.load_catalogs_threads(files, workers=4, delay=0.1)
    threaded = time.perf_counter() - started
    assert sequential >= 0.4
    assert threaded < sequential * 0.7


# --- synchronization -----------------------------------------------------


def test_counter_with_lock_never_loses_updates() -> None:
    value = par.run_counter(par.SafeCounter(), threads=4, increments=300)
    assert value == 1200


def test_counter_without_lock_loses_updates() -> None:
    value = par.run_counter(par.UnsafeCounter(), threads=8, increments=1000)
    assert value <= 8000
    assert value < 8000  # forced thread switches make the race visible


def test_single_thread_does_not_need_a_lock() -> None:
    value = par.run_counter(par.UnsafeCounter(), threads=1, increments=500)
    assert value == 500
