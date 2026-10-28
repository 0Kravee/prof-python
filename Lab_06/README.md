# Car Catalog — automated testing

Лабораторна робота №6 з курсу «Професійний Python», варіант №5 —
«Каталог автомобілів» (узгоджено з Lab_01).

## Description

Консольний каталог автомобілів із Lab_01, розширений для тестування:
CSV import, JSON export (атомарний запис), конфігурація допустимих
діапазонів (JSON-файл + environment variables), репозиторій, сервіс із
зовнішніми залежностями (sync та async) і повний pytest test suite
(unit + integration, Mock/AsyncMock, tmp_path, monkeypatch, coverage).

## Requirements

Python 3.11+

## Installation

    python -m venv .venv
    source .venv/bin/activate        # Windows: .venv\Scripts\activate
    python -m pip install -e ".[dev]"

## Run the application

    python -m car_catalog.main

або без встановлення:

    python src/car_catalog/main.py

## Run the tests

Одна команда (tests + statement/branch coverage + HTML report):

    pytest -v --cov=car_catalog --cov-branch --cov-report=term-missing --cov-report=html

Лише unit або лише integration:

    pytest -m "not integration"
    pytest -m integration

HTML-звіт: `htmlcov/index.html`. Поріг покриття (`fail_under = 80`)
налаштований у `pyproject.toml`.

### Example result

    178 passed
    TOTAL  492 statements, 124 branches  ->  100% coverage

## Configuration

Значення за замовчуванням: `src/car_catalog/config.py`. Їх можна змінити
JSON-файлом (`load_config(path)`) або змінними середовища
`CAR_CATALOG_MIN_YEAR`, `CAR_CATALOG_MAX_YEAR`, `CAR_CATALOG_MIN_PRICE`,
`CAR_CATALOG_MAX_PRICE`, `CAR_CATALOG_CURRENCY` (середовище має
пріоритет над файлом).

## Project structure

- `src/car_catalog/models.py` — data model (`Car`, dataclass)
- `src/car_catalog/services.py` — business logic, `CatalogService`
- `src/car_catalog/config.py` — configuration constants and `load_config`
- `src/car_catalog/exceptions.py` — custom exceptions
- `src/car_catalog/validators.py` — validation against configured ranges
- `src/car_catalog/protocols.py` — interfaces of external dependencies
- `src/car_catalog/repositories.py` — in-memory repository
- `src/car_catalog/importers.py` — CSV import
- `src/car_catalog/exporters.py` — JSON export
- `src/car_catalog/main.py` — application entry point, menu
- `src/student_project/` — thin compatibility package (re-exports)
- `tests/conftest.py` — shared fixtures
- `tests/unit/` — unit tests (models, services, validators, configuration,
  repositories, importers, exporters, catalog service, async, console)
- `tests/integration/` — import / export pipelines and application flow
- `report/` — report of the laboratory work

## Author

Student: Кравець Владислав
Group: ФЕП-31
