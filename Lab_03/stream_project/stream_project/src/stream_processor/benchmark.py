"""Eager vs lazy experiment: time, peak memory, time to first result."""

import csv
import random
import sys
import tempfile
import tracemalloc
from collections import Counter
from collections.abc import Callable, Iterable
from pathlib import Path
from time import perf_counter
from typing import TypeVar

# Allows running this file directly without installing the package.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from stream_processor.analytics import calculate_statistics  # noqa: E402
from stream_processor.analytics import find_first  # noqa: E402
from stream_processor.filters import validate_row  # noqa: E402
from stream_processor.models import CarRecord  # noqa: E402
from stream_processor.pipeline import build_pipeline  # noqa: E402

BRANDS = {
    "Toyota": (("Camry", "Corolla", "RAV4", "Yaris"), 22000),
    "BMW": (("X5", "3 Series", "i4", "M3"), 45000),
    "Audi": (("A4", "A6", "Q7", "Q3"), 40000),
    "Skoda": (("Octavia", "Superb", "Fabia"), 20000),
    "Volkswagen": (("Golf", "Passat", "Tiguan"), 24000),
    "Tesla": (("Model 3", "Model S", "Model Y"), 60000),
}
T = TypeVar("T")
HEADER = ["id", "brand", "model", "year", "price", "mileage"]


def generate_test_file(
    path: Path, count: int, invalid_every: int = 200, seed: int = 42
) -> None:
    """Write a CSV with `count` records; every N-th record is broken."""
    rng = random.Random(seed)
    brands = list(BRANDS)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(HEADER)
        for index in range(1, count + 1):
            brand = rng.choice(brands)
            models, base_price = BRANDS[brand]
            year = rng.randint(2005, 2025)
            price = round(
                base_price
                * rng.uniform(0.4, 1.6)
                * (0.6 + (year - 2005) / 50),
                2,
            )
            mileage = rng.randint(0, 250_000)
            row = [index, brand, rng.choice(models), year, price, mileage]
            if invalid_every and index % invalid_every == 0:
                row[4] = "error"
            writer.writerow(row)


# ------------------------------------------------------- eager version
def eager_process(
    path: Path, brand: str = "BMW", min_year: int = 2015
) -> dict:
    """Eager variant: every stage materialises a full list."""
    with path.open("r", encoding="utf-8", newline="") as file:
        rows = list(csv.DictReader(file))
    records = [validate_row(row) for row in rows]
    valid = [record for record in records if record is not None]
    selected = [
        car for car in valid if car.brand == brand and car.year >= min_year
    ]
    stats = calculate_statistics(selected)
    stats["invalid"] = len(rows) - len(valid)
    return stats


# -------------------------------------------------------- lazy version
def lazy_process(path: Path, brand: str = "BMW", min_year: int = 2015) -> dict:
    """Lazy variant: the same result through a streaming pipeline."""
    counters: Counter = Counter()
    pipeline = build_pipeline(
        path, brand=brand, min_year=min_year, stats=counters
    )
    stats = calculate_statistics(pipeline)
    stats["invalid"] = counters["invalid"]
    return stats


def time_it(function: Callable[[], T]) -> tuple[T, float]:
    start = perf_counter()
    result = function()
    return result, perf_counter() - start


def peak_memory(function: Callable[[], T]) -> tuple[T, int]:
    """Peak traced memory (bytes); the pipeline must be fully consumed."""
    tracemalloc.start()
    try:
        result = function()
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    return result, peak


def first_result_eager(
    path: Path, brand: str = "BMW", min_year: int = 2015
) -> float:
    """Time until the first matching record is available (eager)."""
    start = perf_counter()
    with path.open("r", encoding="utf-8", newline="") as file:
        rows = list(csv.DictReader(file))
    valid = [
        record
        for record in (validate_row(row) for row in rows)
        if record is not None
    ]
    selected = [
        car for car in valid if car.brand == brand and car.year >= min_year
    ]
    _ = selected[0]
    return perf_counter() - start


def first_result_lazy(
    path: Path, brand: str = "BMW", min_year: int = 2015
) -> float:
    """Time until the lazy pipeline produces the first matching record."""
    start = perf_counter()
    pipeline = build_pipeline(path, brand=brand, min_year=min_year)
    next(pipeline)
    pipeline.close()
    return perf_counter() - start


def run_experiment(
    sizes: tuple[int, ...] = (10_000, 100_000, 500_000)
) -> list[dict]:
    """Compare eager and lazy variants for each dataset size."""
    results = []
    with tempfile.TemporaryDirectory() as folder:
        for size in sizes:
            path = Path(folder) / f"cars_{size}.csv"
            generate_test_file(path, size)

            eager_result, eager_time = time_it(lambda: eager_process(path))
            lazy_result, lazy_time = time_it(lambda: lazy_process(path))
            _, eager_peak = peak_memory(lambda: eager_process(path))
            _, lazy_peak = peak_memory(lambda: lazy_process(path))

            results.append(
                {
                    "size": size,
                    "same_result": eager_result == lazy_result,
                    "matched": lazy_result["count"],
                    "invalid": lazy_result["invalid"],
                    "eager_time": eager_time,
                    "lazy_time": lazy_time,
                    "eager_peak_mb": eager_peak / 1024 / 1024,
                    "lazy_peak_mb": lazy_peak / 1024 / 1024,
                    "eager_first": first_result_eager(path),
                    "lazy_first": first_result_lazy(path),
                }
            )
    return results


def early_termination_experiment(size: int = 1_000_000) -> dict:
    """First record matching a condition: lazy search vs eager filtering."""

    def condition(car: CarRecord) -> bool:
        return (
            car.brand == "Tesla" and car.year >= 2024 and car.mileage < 10_000
        )

    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "cars_1m.csv"
        generate_test_file(path, size)

        def lazy() -> CarRecord | None:
            pipeline = build_pipeline(path)
            found = find_first(pipeline, condition)
            pipeline.close()
            return found

        def eager() -> CarRecord | None:
            with path.open("r", encoding="utf-8", newline="") as file:
                rows = list(csv.DictReader(file))
            valid = [
                car
                for car in (validate_row(row) for row in rows)
                if car is not None
            ]
            matching = [car for car in valid if condition(car)]
            return matching[0] if matching else None

        lazy_found, lazy_time = time_it(lazy)
        eager_found, eager_time = time_it(eager)
        _, lazy_peak = peak_memory(lazy)
        _, eager_peak = peak_memory(eager)

    return {
        "size": size,
        "same_record": lazy_found == eager_found,
        "found": lazy_found,
        "lazy_time": lazy_time,
        "eager_time": eager_time,
        "lazy_peak_mb": lazy_peak / 1024 / 1024,
        "eager_peak_mb": eager_peak / 1024 / 1024,
    }


def consume_lazy(items: Iterable[object]) -> int:
    """Fully consume a lazy stream without storing it; return the count."""
    count = 0
    for _ in items:
        count += 1
    return count


measure_peak_memory = peak_memory


def print_report(results: list[dict]) -> None:
    print(
        f"{'Records':>9} {'Eager, s':>10} {'Lazy, s':>10} "
        f"{'Eager MB':>10} {'Lazy MB':>10} "
        f"{'1st eager, s':>13} {'1st lazy, s':>12} {'Same':>6}"
    )
    print("-" * 90)
    for row in results:
        print(
            f"{row['size']:>9} {row['eager_time']:>10.3f} "
            f"{row['lazy_time']:>10.3f} "
            f"{row['eager_peak_mb']:>10.2f} {row['lazy_peak_mb']:>10.2f} "
            f"{row['eager_first']:>13.4f} {row['lazy_first']:>12.6f} "
            f"{str(row['same_result']):>6}"
        )


def main() -> None:
    sizes: tuple[int, ...] = (10_000, 100_000, 500_000)
    if len(sys.argv) > 1 and sys.argv[1] == "--quick":
        sizes = (10_000, 100_000)
    print("EAGER vs LAZY experiment")
    print_report(run_experiment(sizes))
    print("\nEARLY TERMINATION (1 000 000 records)")
    outcome = early_termination_experiment(
        100_000 if "--quick" in sys.argv else 1_000_000
    )
    print(f"first match: {outcome['found']}")
    for name in ("lazy", "eager"):
        print(
            f"{name:<5}: {outcome[name + '_time']:.4f} s, "
            f"peak {outcome[name + '_peak_mb']:.2f} MB"
        )
    print(f"same record found: {outcome['same_record']}")


if __name__ == "__main__":
    main()
