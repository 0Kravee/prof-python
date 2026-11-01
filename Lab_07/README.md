# Car Catalog — database persistence

Лабораторна робота №7 з курсу «Професійний Python», варіант №5 —
«Каталог автомобілів» (продовження проєкту Lab_01 і Lab_06).

## Description

Каталог автомобілів із Lab_01 тепер зберігає дані в SQLite:
таблиці `manufacturers` і `cars` (зв'язок один-до-багатьох), SQLAlchemy
ORM, Repository Pattern, окремий persistence layer, service layer із
транзакціями (commit / rollback), параметризований пошук через Python
DB-API (`sqlite3`), міграції Alembic (migration `0002` додає `VIN` з
UNIQUE constraint) та integration tests на окремій тестовій базі.

Функції Lab_01 збережено: пошук за маркою, фільтрація за роком,
найдорожчий автомобіль, середня ціна, мінімальний пробіг (тепер їх
виконує SQL). Додано CRUD, зміну ціни та пробігу, масове оновлення цін
виробника в одній транзакції.

## Architecture

    Application (db_main.py)
        |
    Service Layer      db_services.py   (commit / rollback)
        |
    Repository Layer   repositories.py  (ManufacturerRepository, CarRepository)
        |
    SQLAlchemy ORM     orm_models.py, database.py
        |
    SQLite             + dbapi.py (plain DB-API), migrations/ (Alembic)

## Database schema

    manufacturers                      cars
    -------------                      ----
    id        INTEGER PK               id              INTEGER PK
    name      VARCHAR(100) UNIQUE      manufacturer_id INTEGER FK -> manufacturers.id
    country   VARCHAR(100) NULL                          ON DELETE CASCADE
                                       model           VARCHAR(100)
                                       year            INTEGER  CHECK 1900..2100
                                       price           FLOAT    CHECK >= 0
                                       mileage         INTEGER  CHECK >= 0
                                       vin             VARCHAR(17) UNIQUE NULL  (migration 0002)

## Requirements

Python 3.11+

## Installation

    python -m venv .venv
    source .venv/bin/activate          # Windows: .venv\Scripts\activate
    python -m pip install -e ".[dev]"

(залежності: `sqlalchemy`, `alembic`, `pytest`, `pytest-cov`, `pytest-asyncio`)

## Run the application

Демонстрація у тимчасовій базі в пам'яті:

    python -m car_catalog.db_main

База у файлі (дані зберігаються між запусками):

    python -m car_catalog.db_main --database cars.db

Консольне меню з Lab_01 працює як і раніше:

    python -m car_catalog.main

## Migrations (Alembic)

URL бази береться зі змінної `CAR_CATALOG_DATABASE_URL`
(за замовчуванням `sqlite:///cars.db`).

    alembic upgrade head        # створити таблиці та додати VIN
    alembic current             # поточна версія
    alembic downgrade -1        # відкотити останню migration
    alembic revision --autogenerate -m "message"

## Run the tests

    pytest -v
    pytest -m integration       # лише integration tests
    pytest -v --cov=car_catalog --cov-branch --cov-report=term-missing

Кожен integration test створює власний SQLite-файл у `tmp_path`
(fixtures у `tests/integration/conftest.py`), реальна `cars.db` не
використовується.

### Example result

    349 passed
    TOTAL  912 statements, 190 branches  ->  100% coverage

## Project structure

- `src/car_catalog/orm_models.py` — ORM models `Manufacturer`, `CarEntity`
- `src/car_catalog/database.py` — engine, session factory, `session_scope`
- `src/car_catalog/repositories.py` — `ManufacturerRepository`,
  `CarRepository` (+ in-memory repository from Lab_06)
- `src/car_catalog/db_services.py` — `CarDatabaseService`, transactions
- `src/car_catalog/dbapi.py` — parameterized queries through `sqlite3`
- `src/car_catalog/db_main.py` — demonstration of the database version
- `src/car_catalog/models.py` — `Car` dataclass (Lab_01)
- `src/car_catalog/services.py`, `config.py`, `exceptions.py`,
  `validators.py`, `importers.py`, `exporters.py`, `main.py` — Lab_01/Lab_06
- `src/student_project/` — thin compatibility package (re-exports)
- `migrations/`, `alembic.ini` — Alembic (`0001` tables, `0002` VIN)
- `tests/unit/` — unit tests (Lab_06 + database helpers)
- `tests/integration/` — repository, constraint, transaction, DB-API,
  migration and CLI integration tests
- `report/` — report of the laboratory work

## Author

Student: Кравець Владислав
Group: ФЕП-31
