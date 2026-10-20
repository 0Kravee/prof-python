# Stream Processor — Car Catalog

Лабораторна робота №3 з курсу «Професійний Python», варіант №5 —
«Потокова обробка каталогу автомобілів» (узгоджено з Lab_01 та Lab_02).

## Description

Потоковий (lazy) конвеєр обробки CSV-каталогу автомобілів
`id,brand,model,year,price,mileage`:

    CSV -> read_lines -> clean_lines -> parse_csv_rows -> validate_cars
        -> filter -> normalize -> aggregation / batching / export

Використано iterator protocol, generator functions, `yield`, `yield from`,
generator expressions та `itertools` (`islice`, `chain`, `groupby`,
`accumulate`, `pairwise`, `count`).

## Requirements

Python 3.11+

## Installation

    python -m venv .venv
    source .venv/bin/activate   # Windows: .venv\Scripts\activate
    python -m pip install -e ".[test]"

## Run

    python -m stream_processor.main                 # demo (data/input.csv + 100 000 records)
    python -m stream_processor.benchmark            # eager vs lazy: 10k / 100k / 500k + early termination
    python -m stream_processor.benchmark --quick    # reduced experiment

Without installation the files can also be started directly:

    python src/stream_processor/main.py
    python src/stream_processor/benchmark.py --quick

The programs do not use `input()`, so they also run in CI / pipes.
The compatibility package can be started the same way:

    python -m student_project.main

### Example output

    === Streaming pipeline on input.csv ===
    valid: ..., invalid: ...
    Most expensive: CarRecord(car_id=..., brand=..., ...)
    ...

## Tests

    python -m pytest
    python -m mypy

## Project structure

- `data/input.csv` — демонстраційний вхідний файл (є некоректні записи)
- `src/stream_processor/models.py` — data model (`CarRecord`, frozen dataclass with validation)
- `src/stream_processor/config.py` — configuration constants
- `src/stream_processor/exceptions.py` — custom exceptions (`InvalidCarDataError`, `InvalidBatchSizeError`)
- `src/stream_processor/readers.py` — streaming reader, cleaning
- `src/stream_processor/parsers.py` — CSV parsing
- `src/stream_processor/filters.py` — validation, filtering
- `src/stream_processor/transformations.py` — transformation stage
- `src/stream_processor/batches.py` — batching, dynamic batching
- `src/stream_processor/analytics.py` — streaming aggregation, groupby, accumulate, pairwise
- `src/stream_processor/pipeline.py` — pipeline assembly, multi-file chain, export
- `src/stream_processor/iterators.py` — custom iterator classes
- `src/stream_processor/generators.py` — generator examples (yield, yield from, infinite)
- `src/stream_processor/benchmark.py` — eager/lazy experiment, memory, time-to-first-result
- `src/stream_processor/main.py` — application entry point, demonstration
- `src/student_project/` — thin compatibility package (re-exports)
- `tests/` — pytest tests

## Author

Student: Кравець Владислав
Group: ФЕП-31
