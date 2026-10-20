"""Tests for the streaming pipeline."""

from collections import Counter
from itertools import count, islice
from pathlib import Path

import pytest

from stream_processor.analytics import (
    find_first,
    find_lowest_mileage,
    find_most_expensive,
    first_n_matching,
    group_by_brand,
    price_differences,
    running_total_price,
    streaming_average_price,
)
from stream_processor.batches import batched, dynamic_batches
from stream_processor.benchmark import (
    eager_process,
    generate_test_file,
    lazy_process,
)
from stream_processor.filters import validate_cars, validate_row
from stream_processor.generators import (
    flatten,
    natural_numbers,
    traced_generator,
)
from stream_processor.iterators import CarFile, NumberRange
from stream_processor.models import CarRecord
from stream_processor.parsers import parse_csv_rows
from stream_processor.pipeline import (
    build_multi_pipeline,
    build_pipeline,
    export_cars,
)
from stream_processor.readers import clean_lines

CSV_TEXT = """id,brand,model,year,price,mileage
1,Toyota,Camry,2019,21500,45000
2,BMW,X5,2021,48200,18000
3,Toyota,Corolla,2022,19800,9000
4,Audi,A4,2018,23000,62000
5,Skoda,Octavia,2023,error,1200
6,,Golf,2019,18000,40000
7,bmw,M3,2022,72000,5000

8,Audi,Q7,1850,54000,1000
"""


@pytest.fixture
def csv_file(tmp_path: Path) -> Path:
    path = tmp_path / "cars.csv"
    path.write_text(CSV_TEXT, encoding="utf-8")
    return path


def test_validate_row_valid_and_invalid() -> None:
    good = {
        "id": "1",
        "brand": " BMW ",
        "model": "X5",
        "year": "2020",
        "price": "100",
        "mileage": "0",
    }
    assert validate_row(good) == CarRecord(1, "BMW", "X5", 2020, 100.0, 0)
    assert validate_row({**good, "price": "abc"}) is None
    assert validate_row({**good, "year": "1800"}) is None
    assert validate_row({**good, "brand": ""}) is None
    assert validate_row({"id": "1"}) is None


def test_pipeline_validation_counts(csv_file: Path) -> None:
    stats: Counter = Counter()
    cars = list(build_pipeline(csv_file, stats=stats))
    assert stats["valid"] == 5
    assert stats["invalid"] == 3
    assert [car.car_id for car in cars] == [1, 2, 3, 4, 7]


def test_normalization_and_filters(csv_file: Path) -> None:
    bmw = list(build_pipeline(csv_file, brand="BMW"))
    assert [car.car_id for car in bmw] == [2, 7]
    assert all(car.brand == "BMW" for car in bmw)
    assert [car.car_id for car in build_pipeline(csv_file, year=2022)] == [
        3,
        7,
    ]
    assert [car.car_id for car in build_pipeline(csv_file, min_year=2021)] == [
        2,
        3,
        7,
    ]


def test_aggregations(csv_file: Path) -> None:
    assert find_most_expensive(build_pipeline(csv_file)).car_id == 7
    assert find_lowest_mileage(build_pipeline(csv_file)).car_id == 7
    expected = (21500 + 48200 + 19800 + 23000 + 72000) / 5
    assert streaming_average_price(build_pipeline(csv_file)) == pytest.approx(
        expected
    )
    assert streaming_average_price([]) == 0.0
    assert find_most_expensive([]) is None


def test_first_n_and_find_first(csv_file: Path) -> None:
    first = first_n_matching(
        build_pipeline(csv_file), lambda car: car.price > 20000, 2
    )
    assert [car.car_id for car in first] == [1, 2]
    assert (
        find_first(
            build_pipeline(csv_file), lambda car: car.year == 2018
        ).car_id
        == 4
    )
    assert (
        find_first(build_pipeline(csv_file), lambda car: car.year == 1999)
        is None
    )


def test_group_by_brand_needs_sorted_input(csv_file: Path) -> None:
    groups = {
        brand: [car.car_id for car in members]
        for brand, members in group_by_brand(build_pipeline(csv_file))
    }
    assert groups == {"Audi": [4], "BMW": [2, 7], "Toyota": [1, 3]}


def test_batching() -> None:
    assert list(batched(range(10), 3)) == [
        [0, 1, 2],
        [3, 4, 5],
        [6, 7, 8],
        [9],
    ]
    assert list(batched([], 3)) == []
    with pytest.raises(ValueError):
        list(batched(range(3), 0))


def test_dynamic_batches() -> None:
    result = list(dynamic_batches([5, 4, 3, 9, 1], 10, lambda x: x))
    assert result == [[5, 4], [3], [9, 1]]


def test_accumulate_and_pairwise(csv_file: Path) -> None:
    cars = list(build_pipeline(csv_file))
    assert list(running_total_price(cars))[-1] == pytest.approx(
        sum(car.price for car in cars)
    )
    assert list(price_differences(cars))[0] == pytest.approx(48200 - 21500)


def test_custom_iterator_is_reusable() -> None:
    numbers = NumberRange(1, 4)
    assert list(numbers) == [1, 2, 3]
    assert list(numbers) == [1, 2, 3]


def test_car_file_iterable_reads_twice(csv_file: Path) -> None:
    car_file = CarFile(csv_file)
    assert len(list(car_file)) == 5
    assert len(list(car_file)) == 5


def test_generator_is_lazy_and_exhaustible() -> None:
    log: list[str] = []
    gen = traced_generator(log)
    assert log == []
    assert next(gen) == 1
    assert log == ["start"]
    assert list(gen) == [2]
    assert list(gen) == []


def test_infinite_generator_with_islice() -> None:
    assert list(islice(natural_numbers(), 5)) == [1, 2, 3, 4, 5]
    assert list(islice(count(10, 5), 3)) == [10, 15, 20]


def test_flatten_recursive() -> None:
    assert list(flatten([1, [2, 3], [4, [5, 6]]])) == [1, 2, 3, 4, 5, 6]


def test_lazy_exception_appears_only_on_consumption() -> None:
    def parse(values):
        for value in values:
            yield int(value)

    stream = parse(["1", "x"])  # no error yet
    assert next(stream) == 1
    with pytest.raises(ValueError):
        next(stream)


def test_clean_and_parse_lines() -> None:
    lines = ["id,brand", "  ", "1,BMW\n", ""]
    assert list(parse_csv_rows(clean_lines(lines))) == [
        {"id": "1", "brand": "BMW"}
    ]


def test_multi_file_and_export(csv_file: Path, tmp_path: Path) -> None:
    merged = list(build_multi_pipeline([csv_file, csv_file], brand="Audi"))
    assert len(merged) == 2
    target = tmp_path / "out.csv"
    assert export_cars(build_pipeline(csv_file, brand="Toyota"), target) == 2
    assert len(list(build_pipeline(target))) == 2


def test_eager_and_lazy_give_same_result(tmp_path: Path) -> None:
    path = tmp_path / "generated.csv"
    generate_test_file(path, 2_000)
    assert eager_process(path) == lazy_process(path)
    assert lazy_process(path)["invalid"] == 10


def test_validate_cars_without_stats() -> None:
    rows = [
        {
            "id": "1",
            "brand": "A",
            "model": "B",
            "year": "2000",
            "price": "1",
            "mileage": "1",
        }
    ]
    assert len(list(validate_cars(rows))) == 1
