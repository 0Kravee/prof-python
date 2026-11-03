"""Tools for measuring time, profiling and tracking memory."""

import cProfile
import csv
import io
import pstats
import time
import tracemalloc
from collections.abc import Callable, Iterable
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from statistics import mean, stdev
from typing import Any, TypeVar

T = TypeVar("T")


# --- time ------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Timing:
    """Several runs of one measured function (seconds)."""

    runs: tuple[float, ...]

    @property
    def mean(self) -> float:
        return mean(self.runs)

    @property
    def minimum(self) -> float:
        return min(self.runs)

    @property
    def stdev(self) -> float:
        return stdev(self.runs) if len(self.runs) > 1 else 0.0


def measure(
    func: Callable[[], object], repeats: int = 5, warmup: int = 0
) -> Timing:
    """Run ``func`` several times with ``time.perf_counter``."""
    if repeats < 1:
        raise ValueError("repeats must be positive")
    for _ in range(warmup):
        func()
    runs = []
    for _ in range(repeats):
        started = time.perf_counter()
        func()
        runs.append(time.perf_counter() - started)
    return Timing(tuple(runs))


def speedup(baseline: float, other: float) -> float:
    """``baseline / other``: above 1 is faster, below 1 is slower."""
    if other <= 0:
        raise ValueError("time must be positive")
    return baseline / other


# --- cProfile ----------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ProfileRow:
    function: str
    ncalls: int
    tottime: float
    cumtime: float


@dataclass(frozen=True, slots=True)
class ProfileReport:
    total_time: float
    rows: tuple[ProfileRow, ...]
    text: str


def profile_call(
    func: Callable[[], object], top: int = 10, sort: str = "cumulative"
) -> ProfileReport:
    """Profile one call with cProfile and return the most expensive rows."""
    profiler = cProfile.Profile()
    profiler.enable()
    try:
        func()
    finally:
        profiler.disable()
    stats = pstats.Stats(profiler)
    stats.sort_stats(sort)
    buffer = io.StringIO()
    printer = pstats.Stats(profiler, stream=buffer)
    printer.strip_dirs().sort_stats(sort).print_stats(top)
    rows = []
    # raw table: (file, line, name) -> (cc, nc, tottime, cumtime, callers)
    raw: dict[Any, Any] = stats.stats  # type: ignore[attr-defined]
    key = 3 if sort == "cumulative" else 2
    for (filename, line, name), values in sorted(
        raw.items(), key=lambda item: item[1][key], reverse=True
    )[:top]:
        label = f"{Path(filename).name}:{line}({name})"
        rows.append(ProfileRow(label, values[1], values[2], values[3]))
    return ProfileReport(
        total_time=float(stats.total_tt),  # type: ignore[attr-defined]
        rows=tuple(rows),
        text=buffer.getvalue(),
    )


# --- tracemalloc ---------------------------------------------------------


@dataclass(frozen=True, slots=True)
class MemoryReport:
    current_bytes: int
    peak_bytes: int

    @property
    def peak_mb(self) -> float:
        return self.peak_bytes / (1024 * 1024)


def trace_memory(func: Callable[[], T]) -> tuple[T, MemoryReport]:
    """Run ``func`` under tracemalloc; return its result and peak memory.

    tracemalloc slows the code down, so never use it together with timing.
    """
    already_tracing = tracemalloc.is_tracing()
    if not already_tracing:
        tracemalloc.start()
    tracemalloc.reset_peak()
    baseline, _ = tracemalloc.get_traced_memory()
    try:
        result = func()
        current, peak = tracemalloc.get_traced_memory()
    finally:
        if not already_tracing:
            tracemalloc.stop()
    return result, MemoryReport(
        max(current - baseline, 0), max(peak - baseline, 0)
    )


def top_allocations(func: Callable[[], object], limit: int = 5) -> list[str]:
    """Source lines that allocated the most memory during ``func``."""
    tracemalloc.start()
    try:
        keep = func()
        snapshot = tracemalloc.take_snapshot()
    finally:
        tracemalloc.stop()
    del keep
    return [
        str(stat)
        for stat in snapshot.filter_traces(
            (tracemalloc.Filter(False, tracemalloc.__file__),)
        ).statistics("lineno")[:limit]
    ]


# --- benchmark records ---------------------------------------------------


@dataclass(slots=True)
class BenchmarkRecord:
    """One row of the experiment table."""

    experiment: str
    method: str
    data_size: int
    workers: int
    runs: tuple[float, ...]
    mean_time: float
    stdev_time: float
    peak_memory_mb: float
    speedup: float
    correct: bool


def save_records_csv(
    records: Iterable[BenchmarkRecord], path: Path
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    names = [f.name for f in fields(BenchmarkRecord)]
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=names)
        writer.writeheader()
        for record in records:
            row = asdict(record)
            row["runs"] = " ".join(f"{value:.6f}" for value in record.runs)
            writer.writerow(row)
    return path


def load_records_csv(path: Path) -> list[BenchmarkRecord]:
    with path.open("r", encoding="utf-8", newline="") as file:
        return [
            BenchmarkRecord(
                experiment=row["experiment"],
                method=row["method"],
                data_size=int(row["data_size"]),
                workers=int(row["workers"]),
                runs=tuple(float(v) for v in row["runs"].split()),
                mean_time=float(row["mean_time"]),
                stdev_time=float(row["stdev_time"]),
                peak_memory_mb=float(row["peak_memory_mb"]),
                speedup=float(row["speedup"]),
                correct=row["correct"] == "True",
            )
            for row in csv.DictReader(file)
        ]


def format_records_table(records: Iterable[BenchmarkRecord]) -> str:
    """Plain text table: experiment, size, workers, time, memory, speedup."""
    header = (
        f"{'Experiment':<30}{'Data size':>11}{'Workers':>9}"
        f"{'Mean, s':>12}{'Peak MB':>10}{'Speedup':>11}  OK"
    )
    lines = [header, "-" * len(header)]
    for r in records:
        workers = str(r.workers) if r.workers else "-"
        lines.append(
            f"{r.method:<30}{r.data_size:>11}{workers:>9}"
            f"{r.mean_time:>12.6f}{r.peak_memory_mb:>10.1f}"
            f"{r.speedup:>11.2f}  {'yes' if r.correct else 'NO'}"
        )
    return "\n".join(lines)
