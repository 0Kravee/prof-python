# Car Catalog

Лабораторна робота №1 з курсу «Професійний Python», варіант №5 —
«Каталог автомобілів».

## Description

Консольний застосунок для роботи з каталогом автомобілів: пошук за маркою,
фільтрація за роком, визначення найдорожчого автомобіля, середня ціна,
автомобіль із найменшим пробігом, сортування, пошук за декількома
критеріями, статистика та інтерактивне меню з додаванням автомобіля.

## Requirements

Python 3.11+

## Installation

    python -m venv .venv
    source .venv/bin/activate        # Windows: .venv\Scripts\activate
    python -m pip install -e ".[test]"

## Run

    python -m car_catalog.main

or

    car-catalog

The file can also be started directly, without installation:

    python src/car_catalog/main.py

In a real terminal the program prints the demo and then opens the
interactive menu. In a non-interactive environment (pipe, CI) only the
demo is executed.

### Example output

    ALL CARS
    Car                   Year   Price       Mileage
    ---------------------------------------------------
    Toyota Camry          2019   21500.00    45000
    BMW X5                2021   48200.00    18000
    ...

    Average price: 28700.00 USD
    Most expensive car: BMW X5 (2021), 48200.00 USD, 18000 km
    Lowest mileage car: Toyota Corolla (2022), 19800.00 USD, 9000 km

## Tests

    python -m pytest
    python -m mypy

## Project structure

- `src/car_catalog/models.py` — data model (`Car`, dataclass)
- `src/car_catalog/services.py` — business logic (no print / input)
- `src/car_catalog/config.py` — configuration constants
- `src/car_catalog/exceptions.py` — custom exceptions
- `src/car_catalog/main.py` — application entry point, menu
- `src/student_project/` — thin compatibility package (re-exports)
- `tests/` — pytest tests

