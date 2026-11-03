# Car Catalog — profiling and optimization

Лабораторна робота №9 з курсу «Професійний Python», варіант №5 —
«Каталог автомобілів» (продовження проєкту Lab_01, Lab_06 і Lab_07).

## Description

Каталог автомобілів із попередніх лабораторних доповнено засобами
вимірювання та оптимізації продуктивності для великих каталогів
(200 000+ автомобілів):

- генератор тестових даних (`datagen.py`) — детермінований, з `seed`;
- аналітика (`analytics.py`): пошук за маркою, фільтрація за роком,
  середня ціна, статистика пробігу, найдорожчий автомобіль, статистика
  виробників — на чистому Python (baseline) і на NumPy (векторизація);
- паралельні версії (`parallel.py`): `ThreadPoolExecutor`,
  `ProcessPoolExecutor`, `threading.Thread` + `Lock`, демонстрація
  race condition;
- кешування (`caching.py`): `lru_cache` для статистики марки з
  invalidation після кожної зміни даних;
- інструменти вимірювання (`profiling.py`): `perf_counter`, `cProfile`,
  `tracemalloc`, розрахунок speedup, збереження результатів у CSV;
- `benchmarks/` — запуск експериментів, CSV і графіки.

## Requirements

Python 3.11+, NumPy, (для графіків) matplotlib.

## Installation

    python -m venv .venv
    source .venv/bin/activate          # Windows: .venv\Scripts\activate
    python -m pip install -e ".[dev]"

## Run the benchmarks

Повний експеримент (3+ розміри даних, 1/2/4/8 workers, 5 повторів):

    python benchmarks/benchmark.py

Швидка перевірка (кілька секунд):

    python benchmarks/benchmark.py --quick

Корисні параметри: `--sizes 10000 100000 1000000`,
`--workers 1 2 4 8`, `--repeats 5`, `--output папка`.
Результати: `benchmarks/results/` — CSV (`benchmark_results.csv`,
`worker_scaling.csv`, `file_loading.csv`, `caching.csv`), звіти
`cProfile` (`profile_baseline.txt`, `profile_numpy.txt`), таблиця
`summary_table.txt` і графіки `execution_time.png`,
`speedup_workers.png`.

> Результати залежать від комп'ютера. Прискорення `ProcessPoolExecutor`
> можна побачити лише на машині з кількома ядрами (`hardware.json`
> показує, скільки CPU було доступно під час запуску).

## Run the tests

    pytest -v
    pytest -m "not integration"
    pytest -v --cov=car_catalog --cov-branch --cov-report=term-missing

## Usage example

    from car_catalog.datagen import generate_cars
    from car_catalog import analytics, parallel

    cars = generate_cars(200_000)
    baseline = analytics.manufacturer_statistics_python(cars)
    fast = analytics.manufacturer_statistics_numpy(analytics.to_columns(cars))
    assert analytics.statistics_close(baseline, fast)

    if __name__ == "__main__":      # обов'язково для multiprocessing (Windows)
        result = parallel.manufacturer_statistics_processes(cars, workers=4)

## Project structure

- `src/car_catalog/datagen.py` — генерація каталогу, CSV-файли
- `src/car_catalog/analytics.py` — Python- і NumPy-реалізації аналітики
- `src/car_catalog/parallel.py` — threads, processes, Lock
- `src/car_catalog/caching.py` — `CatalogAnalytics`, кеш з invalidation
- `src/car_catalog/profiling.py` — вимірювання, cProfile, tracemalloc
- `src/car_catalog/` — решта модулів з Lab_01 / Lab_06 / Lab_07
  (`models`, `services`, `orm_models`, `repositories`, `db_services` ...)
- `benchmarks/benchmark.py`, `benchmarks/plots.py`, `benchmarks/results/`
- `tests/unit/`, `tests/integration/` — pytest
- `migrations/`, `alembic.ini` — міграції Alembic (Lab_07)
- `report/` — звіт

## Author

Student: Кравець Владислав
Group: ФЕП-31
