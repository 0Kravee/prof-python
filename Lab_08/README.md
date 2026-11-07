# Car Catalog API

Лабораторна робота №8 з курсу «Професійний Python», варіант №5 —
«REST API каталогу автомобілів» (узгоджено з Lab_01–Lab_05).
Тема: асинхронний REST API на FastAPI, `async/await`, `asyncio`, HTTPX.

## Description

Асинхронний REST API для автомобілів і виробників:

- **cars** — CRUD, пошук за маркою/моделлю, фільтри за роком/ціною/пробігом,
  сортування, пагінація (`X-Total-Count`), статистика, найдорожчий
  автомобіль, автомобіль із найменшим пробігом;
- **manufacturers** — виробники та їхні автомобілі;
- **batch** — `POST /cars/batch` паралельно завантажує групу автомобілів
  через `httpx.AsyncClient` (`asyncio.Task`, `asyncio.gather`,
  `asyncio.Semaphore`, timeout, retry з exponential backoff).

Шари: `api.py` (HTTP) → `services.py` (use cases) → `repositories.py` (SQL)
→ `models.py` / `database.py` (SQLAlchemy + SQLite); `schemas.py` — Pydantic.

## Requirements

Python 3.11+ і сторонні пакети (FastAPI, SQLAlchemy, HTTPX, Pydantic,
Uvicorn). **Без їх встановлення застосунок не запуститься** (програма
підкаже, що саме встановити).

## Installation

    python -m venv .venv
    source .venv/bin/activate        # Windows: .venv\Scripts\activate
    python -m pip install -e ".[dev]"

або лише залежності:

    python -m pip install -r requirements.txt      # runtime
    python -m pip install -r requirements-dev.txt  # + pytest, mypy

## Run

Швидка демонстрація в процесі (без сервера й порту, база в пам'яті):

    python -m car_catalog.main
    python src/car_catalog/main.py

Сервер:

    python -m car_catalog.main --serve                  # http://127.0.0.1:8000
    python -m car_catalog.main --serve --port 9000
    uvicorn car_catalog.api:app --reload

Swagger UI: <http://127.0.0.1:8000/docs>, ReDoc: `/redoc`,
OpenAPI: `/openapi.json`.

## Endpoints

| Метод | Шлях | Коди | Опис |
|---|---|---|---|
| GET | `/` , `/health` | 200 | інформація про сервіс, стан |
| GET | `/cars` | 200, 422 | пошук, фільтри, сортування, пагінація |
| GET | `/cars/{id}` | 200, 404 | один автомобіль |
| POST | `/cars` | 201, 404, 422 | створити (за `brand` або `manufacturer_id`) |
| PATCH | `/cars/{id}` | 200, 404, 422 | змінити ціну / пробіг / модель / рік |
| DELETE | `/cars/{id}` | 204, 404 | видалити |
| GET | `/cars/most-expensive` | 200, 404 | найдорожчий |
| GET | `/cars/lowest-mileage` | 200, 404 | найменший пробіг |
| GET | `/cars/statistics` | 200 | кількість, середня/мін/макс ціна |
| POST | `/cars/batch` | 200, 422, 504 | паралельне завантаження через HTTPX |
| GET, POST | `/manufacturers` | 200, 201, 409 | список, створення |
| GET, DELETE | `/manufacturers/{id}` | 200, 204, 404, 409 | виробник |
| GET | `/manufacturers/{id}/cars` | 200, 404 | автомобілі виробника |

Параметри `GET /cars`: `brand`, `model`, `year`, `min_year`, `max_year`,
`min_price`, `max_price`, `max_mileage`, `sort` (`id|price|year|mileage|model`),
`order` (`asc|desc`), `limit` (1–100), `offset`.
Помилки мають єдиний формат `{"detail": ..., "code": ...}`.

### Examples

    curl -X POST http://127.0.0.1:8000/cars -H "Content-Type: application/json" \
         -d '{"brand":"Toyota","model":"Camry","year":2019,"price":21500,"mileage":45000}'
    curl "http://127.0.0.1:8000/cars?brand=toyota&sort=price&order=desc"
    curl -X PATCH http://127.0.0.1:8000/cars/1 -H "Content-Type: application/json" \
         -d '{"price":20000,"mileage":46000}'
    curl -X POST http://127.0.0.1:8000/cars/batch -H "Content-Type: application/json" \
         -d '{"ids":[1,2,3]}'

## Configuration (environment)

| Змінна | За замовчуванням | Опис |
|---|---|---|
| `CARS_DATABASE_URL` | `sqlite:///data/cars.db` | рядок підключення SQLAlchemy |
| `CARS_API_BASE_URL` | (немає) | URL для реальних HTTP-запитів batch; без нього — in-process ASGI |
| `CARS_MAX_ATTEMPTS` | 3 | спроб на один запит |
| `CARS_BACKOFF_SECONDS` | 0.2 | базова пауза (×2 після кожної невдачі) |
| `CARS_REQUEST_TIMEOUT` | 5 | timeout одного запиту, с |
| `CARS_BATCH_TIMEOUT` | 10 | timeout усього batch, с (далі 504) |
| `CARS_MAX_CONCURRENCY` | 5 | ліміт паралельних запитів (Semaphore) |

## Tests

    python -m pytest
    python -m mypy            # strict mode

## Project structure

- `src/car_catalog/api.py` — FastAPI app, routers, error handlers
- `src/car_catalog/schemas.py` — Pydantic schemas
- `src/car_catalog/models.py`, `database.py` — ORM, database
- `src/car_catalog/repositories.py`, `services.py` — repository and service layers
- `src/car_catalog/external_api.py` — async HTTP: retry, timeout, Semaphore, gather
- `src/car_catalog/dependencies.py` — dependency injection
- `src/car_catalog/config.py`, `exceptions.py`, `main.py`
- `tests/` — pytest tests (unit, API, async, real server)

## Author

Student: Кравець Владислав
Group: ФЕП-31
