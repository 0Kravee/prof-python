"""Benchmarks of the car catalog analytics (laboratory work 9, variant 5).

Run from the project root:

    python benchmarks/benchmark.py                 # full experiment
    python benchmarks/benchmark.py --quick         # tiny sizes, a few seconds

The script generates the data itself and writes CSV files, text reports and
charts to ``benchmarks/results``.
"""

import argparse
import json
import os
import platform
import sys
import tempfile
from collections.abc import Callable, Sequence
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402

from car_catalog import analytics as an  # noqa: E402
from car_catalog import parallel as par  # noqa: E402
from car_catalog.caching import CatalogAnalytics  # noqa: E402
from car_catalog.datagen import generate_cars, generate_csv_files  # noqa: E402
from car_catalog.models import Car  # noqa: E402
from car_catalog.profiling import (  # noqa: E402
    BenchmarkRecord,
    format_records_table,
    load_records_csv,
    measure,
    profile_call,
    save_records_csv,
    speedup,
    trace_memory,
)

RESULTS = ROOT / "benchmarks" / "results"
SEED = 42
BRAND = "BMW"
YEAR = 2020


# --- helpers -------------------------------------------------------------


def make_record(
    experiment: str,
    method: str,
    size: int,
    workers: int,
    func: Callable[[], object],
    reference: object,
    equal: Callable[[object, object], bool],
    baseline_time: float | None,
    repeats: int,
) -> tuple[BenchmarkRecord, float]:
    """Time ``func`` (several runs), check the result, measure memory."""
    func()  # warm-up: imports, pool start-up caches, allocator
    timing = measure(func, repeats)
    result, memory = trace_memory(func)  # separate run: tracemalloc is slow
    base = baseline_time if baseline_time is not None else timing.mean
    record = BenchmarkRecord(
        experiment=experiment,
        method=method,
        data_size=size,
        workers=workers,
        runs=timing.runs,
        mean_time=timing.mean,
        stdev_time=timing.stdev,
        peak_memory_mb=memory.peak_mb,
        speedup=speedup(base, timing.mean),
        correct=equal(reference, result),
    )
    return record, timing.mean


def stats_equal(left: object, right: object) -> bool:
    return an.statistics_close(left, right)  # type: ignore[arg-type]


def hardware_info() -> dict[str, object]:
    return {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "processor": platform.processor() or platform.machine(),
        "cpu_count": os.cpu_count(),
        "usable_cpus": par.default_workers(),
        "numpy": np.__version__,
    }


# --- experiment 1: methods x data sizes ---------------------------------


def run_methods(
    sizes: Sequence[int], workers: int, repeats: int
) -> list[BenchmarkRecord]:
    records: list[BenchmarkRecord] = []
    for size in sizes:
        cars = generate_cars(size, SEED)
        reference = an.manufacturer_statistics_python(cars)
        columns = an.to_columns(cars)
        runs = repeats if size <= 200_000 else max(3, repeats - 2)
        specs: list[tuple[str, int, Callable[[], object]]] = [
            ("Sequential Python", 1,
             lambda: an.manufacturer_statistics_python(cars)),
            ("Threads", workers,
             lambda: par.manufacturer_statistics_threads(cars, workers)),
            ("Processes", workers,
             lambda: par.manufacturer_statistics_processes(cars, workers)),
            ("NumPy (with conversion)", 0,
             lambda: an.manufacturer_statistics_numpy(an.to_columns(cars))),
            ("NumPy (arrays ready)", 0,
             lambda: an.manufacturer_statistics_numpy(columns)),
        ]
        baseline_time: float | None = None
        for method, w, func in specs:
            print(f"  size={size:>9,} {method:<26} workers={w}", flush=True)
            record, mean_time = make_record(
                "methods", method, size, w, func, reference, stats_equal,
                baseline_time, runs,
            )
            if baseline_time is None:
                baseline_time = mean_time
                record.speedup = 1.0
            records.append(record)
    return records


# --- experiment 2: number of workers ------------------------------------


def run_scaling(
    size: int, worker_counts: Sequence[int], repeats: int
) -> list[BenchmarkRecord]:
    cars = generate_cars(size, SEED)
    reference = an.manufacturer_statistics_python(cars)
    base = measure(lambda: an.manufacturer_statistics_python(cars), repeats)
    records: list[BenchmarkRecord] = []
    for kind, function in (
        ("Threads", par.manufacturer_statistics_threads),
        ("Processes", par.manufacturer_statistics_processes),
    ):
        for workers in worker_counts:
            print(f"  scaling {kind} workers={workers}", flush=True)
            record, _ = make_record(
                "scaling", kind, size, workers,
                lambda f=function, w=workers: f(cars, w),  # type: ignore
                reference, stats_equal, base.mean, repeats,
            )
            records.append(record)
    return records


def run_chunking(
    size: int, workers: int, chunk_factors: Sequence[int], repeats: int
) -> list[BenchmarkRecord]:
    """Smaller tasks (more chunks per worker) for the process pool."""
    cars = generate_cars(size, SEED)
    reference = an.manufacturer_statistics_python(cars)
    base = measure(lambda: an.manufacturer_statistics_python(cars), repeats)
    records = []
    for factor in chunk_factors:
        print(f"  chunking chunks_per_worker={factor}", flush=True)
        record, _ = make_record(
            "chunking", f"Processes, {factor} chunk(s)/worker", size, workers,
            lambda k=factor: par.manufacturer_statistics_processes(
                cars, workers, k
            ),
            reference, stats_equal, base.mean, repeats,
        )
        records.append(record)
    return records


def run_start_methods(
    size: int, workers: int, repeats: int
) -> list[BenchmarkRecord]:
    """Cost of starting processes: spawn (Windows, macOS) versus fork."""
    import multiprocessing
    import warnings

    # Python warns about fork() in a program that has used threads; this
    # experiment measures it on purpose.
    warnings.filterwarnings("ignore", category=DeprecationWarning,
                            module="multiprocessing")
    cars = generate_cars(size, SEED)
    reference = an.manufacturer_statistics_python(cars)
    base = measure(lambda: an.manufacturer_statistics_python(cars), repeats)
    records = []
    for method in ("spawn", "fork"):
        if method not in multiprocessing.get_all_start_methods():
            continue
        print(f"  start method {method}", flush=True)
        record, _ = make_record(
            "start_method", f"Processes, {method}", size, workers,
            lambda m=method: par.manufacturer_statistics_processes(
                cars, workers, start_method=m
            ),
            reference, stats_equal, base.mean, repeats,
        )
        records.append(record)
    return records


# --- experiment 3: loading catalog files --------------------------------


def run_file_loading(
    files: int, rows: int, worker_counts: Sequence[int], repeats: int,
    delay: float,
) -> list[BenchmarkRecord]:
    records: list[BenchmarkRecord] = []
    with tempfile.TemporaryDirectory() as tmp:
        paths = generate_csv_files(Path(tmp), files, rows, SEED)
        reference = par.load_catalogs_sequential(paths)
        total = len(reference)

        def same(a: object, b: object) -> bool:
            return a == b

        scenarios = (("local disk", 0.0), ("simulated remote", delay))
        for label, latency in scenarios:
            base = measure(
                lambda d=latency: par.load_catalogs_sequential(paths, d),
                repeats,
            )
            record, _ = make_record(
                "files", f"Sequential, {label}", total, 1,
                lambda d=latency: par.load_catalogs_sequential(paths, d),
                reference, same, base.mean, repeats,
            )
            record.speedup = 1.0
            records.append(record)
            for workers in worker_counts:
                print(f"  files {label} threads={workers}", flush=True)
                record, _ = make_record(
                    "files", f"ThreadPool, {label}", total, workers,
                    lambda d=latency, w=workers: par.load_catalogs_threads(
                        paths, w, d
                    ),
                    reference, same, base.mean, repeats,
                )
                records.append(record)
            record, _ = make_record(
                "files", f"Thread objects, {label}", total, files,
                lambda d=latency: par.load_catalogs_manual_threads(paths, d),
                reference, same, base.mean, repeats,
            )
            records.append(record)
    return records


# --- experiment 4: caching ----------------------------------------------


def run_caching(size: int, repeats: int) -> tuple[list[BenchmarkRecord], dict]:
    cars = generate_cars(size, SEED)
    reference = an.manufacturer_statistics_python(cars)
    catalog = CatalogAnalytics(cars)

    def cold() -> object:
        catalog.invalidate()
        return catalog.brand_statistics(BRAND)

    catalog.brand_statistics(BRAND)  # fill the cache once
    calls = 2000

    def warm() -> object:
        result = None
        for _ in range(calls):
            result = catalog.brand_statistics(BRAND)
        return result

    cold_timing = measure(cold, repeats)
    warm_timing = measure(warm, repeats)
    warm_per_call = warm_timing.mean / calls
    ok = catalog.brand_statistics(BRAND) == reference[BRAND]
    base = cold_timing.mean
    records = [
        BenchmarkRecord("caching", "Cold cache (miss)", size, 0,
                        cold_timing.runs, base, cold_timing.stdev, 0.0,
                        1.0, ok),
        BenchmarkRecord("caching", "Warm cache (hit)", size, 0,
                        tuple(r / calls for r in warm_timing.runs),
                        warm_per_call, warm_timing.stdev / calls, 0.0,
                        speedup(base, warm_per_call), ok),
    ]
    # hit/miss analysis and invalidation
    catalog.invalidate()
    for _ in range(50):
        for brand in sorted(reference):
            catalog.brand_statistics(brand)
    hits, misses, size_now = catalog.cache_info()
    before = catalog.brand_statistics(BRAND)
    first_model = next(c.model for c in cars if c.brand == BRAND)
    catalog.update_price(BRAND, first_model, 12345.67)
    after = catalog.brand_statistics(BRAND)
    recomputed = an.manufacturer_statistics_python(
        catalog._cars  # noqa: SLF001 - the benchmark checks the internals
    )
    info = {
        "calls": 50 * len(reference),
        "hits": hits,
        "misses": misses,
        "cache_size": size_now,
        "invalidation_changed_result": before != after,
        "after_update_matches_full_recompute": after == recomputed[BRAND],
    }
    return records, info


# --- experiment 5: race condition ---------------------------------------


def run_race(threads: int, increments: int, repeats: int) -> list[dict]:
    rows = []
    for _ in range(repeats):
        for name, factory in (("Unsafe", par.UnsafeCounter),
                              ("Lock", par.SafeCounter)):
            counter = factory()
            import time
            started = time.perf_counter()
            value = par.run_counter(counter, threads, increments)
            rows.append({
                "variant": name, "threads": threads,
                "expected": threads * increments, "actual": value,
                "lost": threads * increments - value,
                "seconds": time.perf_counter() - started,
            })
    return rows


# --- profiling -----------------------------------------------------------


def all_operations(cars: list[Car]) -> None:
    """The six operations of the variant, one after another."""
    an.search_by_brand_python(cars, BRAND)
    an.filter_by_year_python(cars, YEAR)
    an.average_price_python(cars)
    an.mileage_statistics_python(cars)
    an.most_expensive_python(cars)
    an.manufacturer_statistics_python(cars)


def operation_times(cars: list[Car], repeats: int) -> list[tuple[str, float]]:
    columns = an.to_columns(cars)
    operations: list[tuple[str, Callable[[], object]]] = [
        ("search by brand", lambda: an.search_by_brand_python(cars, BRAND)),
        ("filter by year", lambda: an.filter_by_year_python(cars, YEAR)),
        ("average price", lambda: an.average_price_python(cars)),
        ("mileage statistics", lambda: an.mileage_statistics_python(cars)),
        ("most expensive car", lambda: an.most_expensive_python(cars)),
        ("manufacturer statistics",
         lambda: an.manufacturer_statistics_python(cars)),
        ("manufacturer statistics (NumPy)",
         lambda: an.manufacturer_statistics_numpy(columns)),
    ]
    return [(name, measure(func, repeats).mean) for name, func in operations]


def profile_reports(size: int, out: Path) -> dict[str, object]:
    cars = generate_cars(size, SEED)
    before = profile_call(lambda: all_operations(cars), top=12)
    columns = an.to_columns(cars)

    def numpy_pipeline() -> None:
        an.manufacturer_statistics_numpy(columns)
        an.mileage_statistics_numpy(columns)
        an.average_price_numpy(columns)

    after = profile_call(numpy_pipeline, top=12)
    (out / "profile_baseline.txt").write_text(before.text, encoding="utf-8")
    (out / "profile_numpy.txt").write_text(after.text, encoding="utf-8")
    top = before.rows[1] if len(before.rows) > 1 else before.rows[0]
    return {"before": before, "after": after, "top": top}


# --- main ---------------------------------------------------------------


STAGES = ("operations", "methods", "scaling", "files", "caching",
          "race", "memory", "summary")


def _merge_methods(
    new: list[BenchmarkRecord], path: Path
) -> list[BenchmarkRecord]:
    """Keep the rows of other data sizes already stored in the CSV."""
    if not path.exists():
        return new
    sizes = {r.data_size for r in new}
    old = [r for r in load_records_csv(path) if r.data_size not in sizes]
    return sorted(old + new, key=lambda r: r.data_size)


def run_all(
    sizes: Sequence[int],
    worker_counts: Sequence[int],
    repeats: int,
    out: Path,
    scaling_size: int,
    files: int,
    rows_per_file: int,
    delay: float,
    stages: Sequence[str] = STAGES,
) -> None:
    out.mkdir(parents=True, exist_ok=True)
    workers = 4 if 4 in worker_counts else worker_counts[-1]
    profile_size = min(200_000, max(sizes))
    if "operations" in stages:
        print("operations and profiling", flush=True)
        (out / "hardware.json").write_text(
            json.dumps(hardware_info(), indent=2), encoding="utf-8"
        )
        cars = generate_cars(profile_size, SEED)
        op_times = operation_times(cars, repeats)
        total = sum(t for name, t in op_times if "NumPy" not in name)
        lines = [f"{'Operation':<34}{'Mean, s':>10}{'Share, %':>10}"]
        for name, seconds in op_times:
            share = ""
            if "NumPy" not in name:
                share = f"{100 * seconds / total:>10.1f}"
            lines.append(f"{name:<34}{seconds:>10.4f}{share:>10}")
        (out / "operations.txt").write_text(
            "\n".join(lines), encoding="utf-8"
        )
        profile_reports(profile_size, out)
    if "methods" in stages:
        print("methods x sizes", flush=True)
        methods = run_methods(sizes, workers, repeats)
        save_records_csv(
            _merge_methods(methods, out / "benchmark_results.csv"),
            out / "benchmark_results.csv",
        )
    if "scaling" in stages:
        print("workers scaling, chunking, start methods", flush=True)
        scaling = run_scaling(scaling_size, worker_counts, repeats)
        scaling += run_chunking(scaling_size, workers, (1, 4, 16), repeats)
        scaling += run_start_methods(scaling_size, workers, repeats)
        save_records_csv(scaling, out / "worker_scaling.csv")
    if "files" in stages:
        print("loading files", flush=True)
        file_records = run_file_loading(
            files, rows_per_file, [w for w in worker_counts if w <= files],
            repeats, delay,
        )
        save_records_csv(file_records, out / "file_loading.csv")
    if "caching" in stages:
        print("caching", flush=True)
        cache_records, cache_info = run_caching(profile_size, repeats)
        save_records_csv(cache_records, out / "caching.csv")
        (out / "cache_info.json").write_text(
            json.dumps(cache_info, indent=2), encoding="utf-8"
        )
    if "race" in stages:
        print("race condition", flush=True)
        race = run_race(4, 500, repeats)
        (out / "race.json").write_text(
            json.dumps(race, indent=2), encoding="utf-8"
        )
    if "memory" in stages:
        print("memory of data representations", flush=True)
        count = min(1_000_000, max(sizes))
        cars_mem = generate_cars(count, SEED)
        columns = an.to_columns(cars_mem)
        _, list_mem = trace_memory(lambda: generate_cars(count, SEED))
        memory = {
            "cars": count,
            "list_mb": list_mem.peak_mb,
            "numpy_mb": sum(
                a.nbytes for a in (columns.brands, columns.years,
                                   columns.prices, columns.mileages)
            ) / 2**20,
        }
        (out / "memory.json").write_text(
            json.dumps(memory, indent=2), encoding="utf-8"
        )
    if "summary" in stages:
        records: list[BenchmarkRecord] = []
        for name in ("benchmark_results", "worker_scaling", "file_loading",
                     "caching"):
            path = out / f"{name}.csv"
            if path.exists():
                records += load_records_csv(path)
        table = format_records_table(records)
        (out / "summary_table.txt").write_text(table, encoding="utf-8")
        try:
            from benchmarks import plots

            plots.make_all(out)
        except ImportError as exc:  # matplotlib is optional
            print(f"charts skipped: {exc}")
        print(table)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--sizes", type=int, nargs="+",
                        default=[10_000, 100_000, 200_000, 1_000_000])
    parser.add_argument("--workers", type=int, nargs="+", default=[1, 2, 4, 8])
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--scaling-size", type=int, default=200_000)
    parser.add_argument("--files", type=int, default=8)
    parser.add_argument("--rows-per-file", type=int, default=25_000)
    parser.add_argument("--delay", type=float, default=0.05,
                        help="simulated latency of a remote file, seconds")
    parser.add_argument("--stage", action="append", choices=STAGES,
                        help="run only the given stage(s); default: all")
    parser.add_argument("--output", type=Path, default=RESULTS)
    parser.add_argument("--quick", action="store_true",
                        help="tiny sizes for a smoke run")
    args = parser.parse_args(argv)
    if args.quick:
        args.sizes, args.repeats = [2_000, 5_000], 1
        args.scaling_size, args.files, args.rows_per_file = 3_000, 2, 300
        args.workers = [1, 2]
        args.delay = 0.01
    run_all(args.sizes, args.workers, args.repeats, args.output,
            args.scaling_size, args.files, args.rows_per_file, args.delay,
            args.stage or STAGES)
    return 0


if __name__ == "__main__":
    sys.exit(main())
