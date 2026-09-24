# Data Processor — Car Catalog

Лабораторна робота №2 з курсу «Професійний Python», варіант №5 — «Каталог автомобілів».

## Description

Модуль обробки структурованих даних каталогу автомобілів: пошук, фільтрація,
групування (у т.ч. вкладене), сортування та агрегація з використанням list,
tuple, set, dict, а також collections.Counter, collections.defaultdict і
collections.deque.

## Requirements

Python 3.11+

## Installation

    python -m venv .venv
    python -m pip install -e .

## Run

    python -m data_processor.main

## Tests

    python -m pip install -e ".[test]"
    python -m pytest

## Project structure

- `src/data_processor/data.py` — вхідні структуровані дані
- `src/data_processor/processors.py` — пошук, фільтрація, групування
- `src/data_processor/analytics.py` — агрегація, сортування, closures, *args/**kwargs
- `src/data_processor/decorators.py` — measure_time та параметризований track_history
- `src/data_processor/main.py` — точка входу, демонстрація та benchmark

## Author

Student: Name Surname
Group: XX-00
