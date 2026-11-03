"""Threads and processes for the catalog analytics and file loading.

* ``ThreadPoolExecutor`` helps when the work waits for I/O (files, network);
  CPU-bound Python code is limited by the GIL and does not get faster.
* ``ProcessPoolExecutor`` uses several interpreters, so CPU-bound code can
  use several cores, but the data must be serialized (pickled) and sent to
  the workers, and starting processes costs time.
"""

import multiprocessing
import os
import threading
import time
from collections.abc import Iterable, Sequence
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from pathlib import Path

from car_catalog.analytics import (
    BrandStats,
    Partial,
    estimated_value,
    finalize_statistics,
    merge_partials,
    partial_manufacturer_statistics,
)
from car_catalog.importers import import_cars_csv
from car_catalog.models import Car

Columns = tuple[list[str], list[int], list[float], list[int]]

#: "spawn" starts clean interpreters on every OS (it is the only method on
#: Windows). "fork" is faster on Linux but unsafe in multi-threaded programs.
PROCESS_START_METHOD = "spawn"


def default_workers() -> int:
    """Number of CPUs this process may use (at least 1)."""
    try:
        return max(1, len(os.sched_getaffinity(0)))
    except AttributeError:  # Windows, macOS
        return max(1, os.cpu_count() or 1)


def split_slices(total: int, parts: int) -> list[tuple[int, int]]:
    """Split ``range(total)`` into at most ``parts`` balanced slices."""
    if parts < 1:
        raise ValueError("parts must be positive")
    parts = min(parts, max(total, 1))
    base, extra = divmod(total, parts)
    slices = []
    start = 0
    for index in range(parts):
        stop = start + base + (1 if index < extra else 0)
        slices.append((start, stop))
        start = stop
    return [(a, b) for a, b in slices if b > a]


def _check_workers(workers: int) -> None:
    if workers < 1:
        raise ValueError("workers must be positive")


# --- CPU-bound analytics: threads ----------------------------------------


def manufacturer_statistics_threads(
    cars: Sequence[Car], workers: int = 4
) -> dict[str, BrandStats]:
    """Same result as the sequential version; threads share the objects."""
    _check_workers(workers)
    chunks = [cars[a:b] for a, b in split_slices(len(cars), workers)]
    with ThreadPoolExecutor(max_workers=workers) as executor:
        parts = executor.map(partial_manufacturer_statistics, chunks)
        return finalize_statistics(merge_partials(parts))


# --- CPU-bound analytics: processes --------------------------------------


def _columns_chunk(cars: Sequence[Car], start: int, stop: int) -> Columns:
    """Compact picklable form of a slice (lists of primitives)."""
    part = cars[start:stop]
    return (
        [car.brand for car in part],
        [car.year for car in part],
        [car.price for car in part],
        [car.mileage for car in part],
    )


def partial_from_columns(columns: Columns) -> Partial:
    """Worker function: must be a module level function (picklable)."""
    brands, years, prices, mileages = columns
    partial: Partial = {}
    for brand, year, price, mileage in zip(brands, years, prices, mileages):
        entry = partial.get(brand)
        if entry is None:
            entry = partial[brand] = [0.0, 0.0, 0.0, 0.0]
        entry[0] += 1
        entry[1] += price
        entry[2] += mileage
        entry[3] += estimated_value(year, price, mileage)
    return partial


def manufacturer_statistics_processes(
    cars: Sequence[Car],
    workers: int = 4,
    chunks_per_worker: int = 1,
    start_method: str = PROCESS_START_METHOD,
) -> dict[str, BrandStats]:
    """Several processes; ``chunks_per_worker`` controls the task size."""
    _check_workers(workers)
    if chunks_per_worker < 1:
        raise ValueError("chunks_per_worker must be positive")
    slices = split_slices(len(cars), workers * chunks_per_worker)
    chunks = [_columns_chunk(cars, a, b) for a, b in slices]
    context = multiprocessing.get_context(start_method)
    with ProcessPoolExecutor(
        max_workers=workers, mp_context=context
    ) as executor:
        parts = executor.map(partial_from_columns, chunks)
        return finalize_statistics(merge_partials(parts))


# --- I/O-bound: loading several catalog files ----------------------------


def read_catalog_file(
    path: Path, delay: float = 0.0, skip_invalid: bool = False
) -> list[Car]:
    """Read one CSV catalog.

    ``delay`` simulates a slow (remote) storage: ``time.sleep`` releases
    the GIL, exactly like a real network or disk wait.
    """
    if delay > 0:
        time.sleep(delay)
    return import_cars_csv(Path(path), skip_invalid=skip_invalid)


def load_catalogs_sequential(
    paths: Iterable[Path], delay: float = 0.0
) -> list[Car]:
    cars: list[Car] = []
    for path in paths:
        cars.extend(read_catalog_file(path, delay))
    return cars


def load_catalogs_threads(
    paths: Iterable[Path], workers: int = 4, delay: float = 0.0
) -> list[Car]:
    """``ThreadPoolExecutor``; ``map`` keeps the order of the files."""
    _check_workers(workers)
    files = list(paths)
    if not files:
        return []
    with ThreadPoolExecutor(max_workers=workers) as executor:
        results = executor.map(
            lambda path: read_catalog_file(path, delay), files
        )
        return [car for part in results for car in part]


def load_catalogs_manual_threads(
    paths: Iterable[Path], delay: float = 0.0
) -> list[Car]:
    """The same with raw ``threading.Thread`` and a ``Lock``.

    The dictionary is shared mutable state, so writes are synchronized.
    """
    files = list(paths)
    results: dict[int, list[Car]] = {}
    errors: list[BaseException] = []
    lock = threading.Lock()

    def worker(index: int, path: Path) -> None:
        try:
            part = read_catalog_file(path, delay)
        except BaseException as exc:  # reported in the main thread
            with lock:
                errors.append(exc)
            return
        with lock:
            results[index] = part

    threads = [
        threading.Thread(target=worker, args=(index, path))
        for index, path in enumerate(files)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    if errors:
        raise errors[0]
    return [car for index in sorted(results) for car in results[index]]


# --- synchronization: race condition and Lock ---------------------------


class UnsafeCounter:
    """Read-modify-write without protection: updates can be lost."""

    def __init__(self) -> None:
        self.value = 0

    def increment(self) -> None:
        current = self.value
        time.sleep(0)  # give another thread a chance to run
        self.value = current + 1


class SafeCounter:
    """The critical section is protected by a ``Lock``."""

    def __init__(self) -> None:
        self.value = 0
        self._lock = threading.Lock()

    def increment(self) -> None:
        with self._lock:
            current = self.value
            time.sleep(0)
            self.value = current + 1


def run_counter(
    counter: UnsafeCounter | SafeCounter, threads: int, increments: int
) -> int:
    """Increment from several threads; return the final value."""

    def work() -> None:
        for _ in range(increments):
            counter.increment()

    pool = [threading.Thread(target=work) for _ in range(threads)]
    for thread in pool:
        thread.start()
    for thread in pool:
        thread.join()
    return counter.value
