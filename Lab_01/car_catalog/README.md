# Car Catalog

Лабораторна робота №1 з курсу «Професійний Python», варіант №5 — «Каталог автомобілів».

## Description

Консольний застосунок для роботи з каталогом автомобілів: пошук за маркою,
фільтрація за роком, визначення найдорожчого автомобіля, обчислення середньої
ціни та пошук автомобіля з найменшим пробігом.

## Requirements

Python 3.11+

## Installation

    python -m venv .venv
    python -m pip install -e .

## Run

    python -m car_catalog.main

or, after installation:

    car-catalog

## Tests

    python -m pip install -e ".[test]"
    python -m pytest

## Project structure

- `src/car_catalog/models.py` — data model (`Car`)
- `src/car_catalog/services.py` — business logic
- `src/car_catalog/main.py` — application entry point

## Author

Student: Name Surname
Group: XX-00
