"""Entry point: iterators, generators, itertools and the lazy pipeline."""

import sys
import tempfile
from collections import Counter
from itertools import count, islice
from pathlib import Path
from time import perf_counter

# Allows running this file directly (``python main.py``) without
# installing the package: ``src`` is added to sys.path.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from stream_processor.analytics import (  # noqa: E402
    calculate_statistics,
    find_lowest_mileage,
    find_most_expensive,
    first_n_matching,
    group_by_brand,
    price_differences,
    running_total_price,
    streaming_average_price,
)
from stream_processor.batches import batched, dynamic_batches  # noqa: E402
from stream_processor.benchmark import generate_test_file  # noqa: E402
from stream_processor.generators import (  # noqa: E402
    even_numbers,
    flatten,
    generate_numbers,
    natural_numbers,
    traced_generator,
)
from stream_processor.iterators import CarFile, NumberRange  # noqa: E402
from stream_processor.pipeline import (  # noqa: E402
    build_multi_pipeline,
    build_pipeline,
    export_cars,
)
from stream_processor.transformations import describe_cars  # noqa: E402

DEFAULT_INPUT = Path(__file__).resolve().parents[2] / "data" / "input.csv"


def section(title: str) -> None:
    print(f"\n=== {title} ===")


def demo_iteration_protocol() -> None:
    section("Iterable vs iterator")
    values = [10, 20, 30]
    iterator = iter(values)
    print("iter(list) is list:", iter(values) is values)
    print("iter(iterator) is iterator:", iter(iterator) is iterator)
    print("next x3:", next(iterator), next(iterator), next(iterator))
    try:
        next(iterator)
    except StopIteration:
        print("next() after the end -> StopIteration")

    numbers = NumberRange(1, 5)
    print("NumberRange, 1st pass:", list(numbers))
    print("NumberRange, 2nd pass:", list(numbers), "(new iterator every time)")
    spent = iter([1, 2, 3])
    print("one-shot iterator:", list(spent), list(spent))


def demo_generators() -> None:
    section("Generators, yield, yield from")
    log: list[str] = []
    gen = traced_generator(log)
    print("after creating generator, log =", log)
    print("next ->", next(gen), "| log =", log)
    print("next ->", next(gen), "| log =", log)
    print("generate_numbers(1, 6):", list(generate_numbers(1, 6)))
    print("even_numbers(10):", list(even_numbers(10)))
    print("flatten (yield from):", list(flatten([1, [2, 3], [4, [5, 6]]])))
    print("infinite + islice:", list(islice(natural_numbers(), 10)))
    print("itertools.count + islice:", list(islice(count(10, 5), 5)))
    squares = (x * x for x in range(1_000_000))
    print("generator expression sum:", sum(squares))
    print(
        "size of list(1M):",
        sys.getsizeof([x for x in range(1_000_000)]),
        "bytes",
    )
    print(
        "size of generator:",
        sys.getsizeof(x for x in range(1_000_000)),
        "bytes",
    )


def demo_sample_file(path: Path) -> None:
    section(f"Streaming pipeline on {path.name}")
    stats: Counter = Counter()
    counters: Counter = Counter()
    pipeline = build_pipeline(path, stats=stats, counters=counters)
    cars = list(pipeline)
    print(f"valid: {stats['valid']}, invalid: {stats['invalid']}")
    print("stage counters:", dict(counters))

    print("\nMost expensive:", find_most_expensive(build_pipeline(path)))
    print("Lowest mileage:", find_lowest_mileage(build_pipeline(path)))
    average = streaming_average_price(build_pipeline(path))
    print(f"Streaming average price: {average:.2f}")

    print("\nBMW cars:")
    for line in describe_cars(build_pipeline(path, brand="bmw")):
        print(" ", line)
    print("\nCars from 2021:")
    for line in describe_cars(build_pipeline(path, year=2021)):
        print(" ", line)

    print("\nFirst 3 cars with price > 25000:")
    for car in first_n_matching(
        build_pipeline(path), lambda c: c.price > 25000, 3
    ):
        print(" ", car)

    print("\nGroup by brand (sorted first, then itertools.groupby):")
    for brand, members in group_by_brand(build_pipeline(path)):
        print(f"  {brand:<11} {len(members)} cars")

    print("\nBatches of 4:")
    for number, batch in enumerate(batched(build_pipeline(path), 4), start=1):
        print(f"  batch {number}: ids {[car.car_id for car in batch]}")

    print("\nDynamic batches (total price <= 80000):")
    for batch in dynamic_batches(
        build_pipeline(path), 80_000, lambda c: c.price
    ):
        ids = [car.car_id for car in batch]
        total = sum(car.price for car in batch)
        print(f"  ids {ids} total {total:.0f}")

    print(
        "\nRunning total price:",
        [round(v) for v in running_total_price(cars)][:6],
        "...",
    )
    print(
        "Price differences:",
        [round(v) for v in price_differences(cars)][:6],
        "...",
    )

    print("\nReusable iterable CarFile (custom iterator class):")
    car_file = CarFile(path)
    print(
        "  1st pass:",
        sum(1 for _ in car_file),
        "cars; 2nd pass:",
        sum(1 for _ in car_file),
        "cars",
    )


def demo_large_dataset() -> None:
    section("Lazy processing of 100 000 records")
    with tempfile.TemporaryDirectory() as folder:
        folder_path = Path(folder)
        source = folder_path / "cars_100k.csv"
        generate_test_file(source, 100_000)

        stats: Counter = Counter()
        start = perf_counter()
        summary = calculate_statistics(build_pipeline(source, stats=stats))
        elapsed = perf_counter() - start
        print(
            f"records read: {stats['valid'] + stats['invalid']}, "
            f"valid: {stats['valid']}, invalid: {stats['invalid']}"
        )
        print(
            f"average price: {summary['average_price']:.2f}, "
            f"min: {summary['min_price']:.2f}, max: {summary['max_price']:.2f}"
        )
        print(f"brands: {summary['brands']}")
        print(f"elapsed: {elapsed:.3f} s")

        part2 = folder_path / "cars_part2.csv"
        generate_test_file(part2, 1_000, seed=7)
        merged = build_multi_pipeline([source, part2], brand="Tesla")
        print("Tesla cars from two files (chain):", sum(1 for _ in merged))

        target = folder_path / "export_bmw.csv"
        exported = export_cars(
            build_pipeline(source, brand="BMW", min_year=2020), target
        )
        print(
            f"streaming export of BMW 2020+: {exported} rows -> {target.name}"
        )

        early = list(islice(build_pipeline(source, brand="Audi"), 3))
        print(
            "first 3 Audi via islice (early termination):",
            [car.car_id for car in early],
        )
        print(
            "batches of 1000:",
            sum(1 for _ in batched(build_pipeline(source), 1000)),
        )


def main(argv: list[str] | None = None) -> None:
    args = sys.argv[1:] if argv is None else argv
    path = Path(args[0]) if args else DEFAULT_INPUT
    demo_iteration_protocol()
    demo_generators()
    demo_sample_file(path)
    demo_large_dataset()
    print("\nFull eager/lazy experiment: python -m stream_processor.benchmark")


if __name__ == "__main__":
    main()
