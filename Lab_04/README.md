# Domain App — Vehicle Catalog

Лабораторна робота №4 з курсу «Професійний Python», варіант №5 —
«Каталог автомобілів» (узгоджено з Lab_01–Lab_03).
Тема: ООП, типізація, Protocol, Generic, TypedDict, SOLID, DI, `mypy`.

## Description

Типізована об'єктна модель каталогу автомобілів:

- доменні класи `Vehicle` (ABC), `Car`, `ElectricCar`, `VehicleCatalog`,
  value objects `Money`, `Mileage`, `VehicleSpecification`;
- абстракція критеріїв пошуку `SearchCriteria` (strategy, комбінування
  `&`, `|`, `~`);
- generic repository `InMemoryRepository[E]` та segregated protocols
  `ReadableRepository` / `WritableRepository` / `Repository`;
- прикладний сервіс `CatalogService` з dependency injection
  (`Notifier`, `Repository`) та ручний DI-контейнер;
- зовнішні дані: `TypedDict` `VehiclePayload` + валідація `parse_payload`;
- дослідження: успадкування vs композиція, DI vs жорстка залежність,
  експеримент з навмисними помилками типів.

## Requirements

Python 3.11+

## Installation

    python -m venv .venv
    source .venv/bin/activate        # Windows: .venv\Scripts\activate
    python -m pip install -e ".[dev]"

## Run

    python -m domain_app.main

or

    domain-app

Without installation the file can be started directly:

    python src/domain_app/main.py

The program is non-interactive (no `input()`), so it also runs in CI / pipes.

### Example output

    === Adding vehicles (notifications go through the Notifier) ===
    [notify] Added: Toyota Camry (2019)
    ...
    Most expensive: Tesla Model Y (2023): suv, electric, 8000 km, 52000.00 USD, ...
    Average price: 33785.71 USD

## Type checking and tests

    python -m mypy                   # strict mode, 0 errors expected
    python -m pytest
    python -m mypy experiments/type_errors_demo.py    # 3 deliberate errors
    python -m domain_app.check       # mypy + pytest in one command

## Project structure

- `src/domain_app/value_objects.py` — `Money`, `Mileage`, `VehicleSpecification`
- `src/domain_app/models.py` — `Vehicle`, `Car`, `ElectricCar`, `VehicleCatalog`
- `src/domain_app/protocols.py` — `Protocol` interfaces
- `src/domain_app/criteria.py` — search criteria (strategy)
- `src/domain_app/repositories.py` — generic repository
- `src/domain_app/dto.py` — `TypedDict` payload, DTOs
- `src/domain_app/services.py` — application services
- `src/domain_app/container.py`, `notifiers.py` — DI
- `src/domain_app/processing.py`, `experiments.py` — design research
- `src/domain_app/generics.py`, `exceptions.py`, `config.py`, `check.py`
- `experiments/` — type-checking experiment (errors and fixed version)
- `tests/` — pytest tests

## Author

Student: Кравець Владислав
Group: ФЕП-31
