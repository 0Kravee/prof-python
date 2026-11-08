# Car Catalog

Каталог автомобілів (варіант №5): REST API, база даних SQLite, міграції
Alembic, пакет Python, Docker-образ і CI/CD у GitHub Actions.
Лабораторна робота №10 з курсу «Професійний Python»; продовження проєкту
Lab_01 (консольний каталог), Lab_06 (tests), Lab_07 (база даних) і Lab_09
(продуктивність).

## Предметна система

Каталог зберігає **виробників** (`manufacturers`) і **автомобілі**
(`cars`: марка, модель, рік, ціна, пробіг, VIN). Один виробник має багато
автомобілів. Функції Lab_01 збережено:

- пошук за маркою та моделлю;
- фільтрація за роком, ціною, пробігом;
- найдорожчий автомобіль, середня ціна, мінімальний пробіг;
- статистика за виробниками.

## Вимоги

Python 3.11+. Для запуску у Docker потрібен лише Docker.

## Installation

```bash
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
python -m pip install -e ".[dev]"
```

Лише для запуску (без інструментів розробки): `python -m pip install .`

## Configuration

Усі налаштування передаються через **environment variables** (або локальний
файл `.env`, якого немає в Git). Зразок — `.env.example`.

| Змінна | Значення за замовчуванням | Опис |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./cars.db` | URL бази даних |
| `APP_ENV` (або `ENVIRONMENT`) | `development` | `development`, `test` або `production` |
| `LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` |
| `API_KEY` | _порожньо_ | ключ для `POST`/`PATCH`/`DELETE` (заголовок `X-API-Key`); якщо не задано, ключ не потрібен |
| `HOST` | `127.0.0.1` | адреса, яку слухає сервер |
| `PORT` | `8000` | порт сервера |
| `AUTO_CREATE_TABLES` | `false` | створити таблиці при старті (для демонстрацій) |

```bash
cp .env.example .env      # потім відредагуйте значення
```

### Secrets

- Реальні паролі, токени та ключі **ніколи** не записуються в код, README,
  `Dockerfile` або Git. У репозиторії є лише `.env.example` без секретів.
- `.env` занесено в `.gitignore` і `.dockerignore`.
- `API_KEY` має тип `SecretStr`: його не видно в `repr`, логах і `/health`;
  пароль у `DATABASE_URL` маскується (`user:***@host`).
- У Docker секрети передаються під час запуску (`-e API_KEY=...`,
  `--env-file`), а в CI — через **GitHub Secrets** (`${{ secrets.NAME }}`).

## Запуск локально

```bash
alembic upgrade head                 # створити таблиці (міграції 0001, 0002)
car-catalog-api                      # або: uvicorn car_catalog.api:create_app --factory
```

Сервер: <http://127.0.0.1:8000>, документація Swagger: `/docs`,
схема OpenAPI: `/openapi.json`.

Консольний каталог з Lab_01: `car-catalog`; демонстрація бази: `car-catalog-db`.

## Запуск у Docker

```bash
docker build -t car-catalog:1.0.0 .
docker volume create car-data
docker run -d --name car-api -p 8000:8000 \
    -v car-data:/data \
    -e API_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')" \
    car-catalog:1.0.0
curl http://localhost:8000/health
```

Образ багатоетапний (stage `builder` збирає wheel, `runtime` лише
встановлює його), працює від користувача без прав root, має `HEALTHCHECK`
на `/health`. При старті контейнера виконується `alembic upgrade head`,
файл бази лежить у томі `/data`, тому дані зберігаються між запусками.

Через Docker Compose: `docker compose up --build`.

Корисно: `docker ps` (стан `healthy`), `docker logs car-api`,
`docker stop car-api && docker rm car-api`.

## REST API

| Метод і шлях | Опис |
|---|---|
| `GET /health` | стан сервісу та бази: `{"status": "ok", ...}`, 503 якщо база недоступна |
| `GET /cars` | список з фільтрами `brand`, `model`, `year`, `min_year`, `max_year`, `min_price`, `max_price`, `max_mileage`, сортуванням `sort_by`, `descending` та пагінацією `limit`, `offset` |
| `POST /cars` | створити автомобіль (потрібен API-ключ, якщо він заданий) |
| `GET /cars/{id}` | автомобіль за id |
| `PATCH /cars/{id}` | змінити ціну та/або пробіг |
| `DELETE /cars/{id}` | видалити автомобіль |
| `GET /cars/most-expensive` | найдорожчий автомобіль |
| `GET /cars/lowest-mileage` | автомобіль з мінімальним пробігом |
| `GET /cars/average-price` | середня ціна |
| `GET /manufacturers` | список виробників |
| `POST /manufacturers` | створити виробника |
| `GET /manufacturers/{id}` | виробник за id |
| `GET /manufacturers/{id}/cars` | автомобілі виробника |
| `GET /statistics` | кількість, мінімальна/максимальна/середня ціна, статистика за виробниками |

Коди помилок: `404` — запис не знайдено, `409` — дублікат (назва виробника,
VIN), `422` — некоректні дані, `401` — відсутній або хибний API-ключ.

Приклади:

```bash
curl -X POST localhost:8000/manufacturers -H 'X-API-Key: ...' \
     -H 'Content-Type: application/json' -d '{"name": "Skoda", "country": "Czechia"}'
curl -X POST localhost:8000/cars -H 'X-API-Key: ...' \
     -H 'Content-Type: application/json' \
     -d '{"manufacturer_id": 1, "model": "Octavia", "year": 2020, "price": 17000, "mileage": 30000}'
curl 'localhost:8000/cars?brand=skoda&min_year=2019&sort_by=price&limit=10'
curl localhost:8000/cars/most-expensive
curl localhost:8000/manufacturers/1/cars
```

Схема OpenAPI збережена в `docs/openapi.json`
(оновлення: `python scripts/export_openapi.py`).

## Tests, lint, types

```bash
pytest -v                                         # tests
pytest -v --cov=car_catalog --cov-branch --cov-report=term-missing
ruff check .                                      # lint
ruff format --check .                             # format check
mypy                                              # type checking
```

Поріг покриття — 80% (у CI перевіряється `--cov-fail-under=80`).
Tests використовують окремі тимчасові бази SQLite.

## Package build

```bash
python -m build            # dist/car_catalog-1.0.0-py3-none-any.whl + .tar.gz
twine check dist/*
python -m venv /tmp/clean && /tmp/clean/bin/pip install dist/*.whl
/tmp/clean/bin/car-catalog-api --version
```

Версію визначає `car_catalog.__version__` (Semantic Versioning); історія
змін — у `CHANGELOG.md`.

## CI/CD (GitHub Actions)

Workflow `.github/workflows/ci.yml` запускається на `push`, `pull_request`
і теги `v*`:

| Job | Що робить |
|---|---|
| `lint` | `ruff check .` і `ruff format --check .` |
| `typecheck` | `mypy` |
| `test` | `pytest` з coverage для Python 3.11 і 3.12, поріг 80% |
| `build` | `python -m build`, `twine check`, встановлення wheel у чистому venv, збереження wheel/sdist як artifact |
| `docker` | `docker build`, запуск контейнера, перевірка `/health` |
| `release` | при тезі `v*` створює GitHub Release з wheel і sdist |

Jobs `build` і `docker` запускаються лише після успішних `lint`, `typecheck`
і `test`. Секрети беруться тільки з GitHub Secrets (необов'язковий
`CI_API_KEY`).

Реліз: `git tag v1.0.0 && git push origin v1.0.0`.

## Сценарій демонстрації (варіант №5)

1. `docker build -t car-catalog:1.0.0 .` і `docker run ...` (див. вище).
2. `curl localhost:8000/health` → `{"status":"ok", ...}`.
3. Відкрити `http://localhost:8000/docs` (Swagger).
4. `POST /manufacturers` (Toyota, BMW) і `POST /cars` з API-ключем.
5. `GET /cars?brand=bmw`, `GET /cars?year=2021`, `GET /cars/most-expensive`,
   `GET /cars/average-price`, `GET /cars/lowest-mileage`.
6. `GET /manufacturers/{id}/cars` і `GET /statistics`.
7. Запит без ключа → `401`; повторний VIN → `409`.
8. Перезапустити контейнер: дані на місці (том `/data`).
9. Показати GitHub Actions: lint, mypy, pytest, build, docker.

## Структура проєкту

```
.github/workflows/ci.yml   CI/CD
src/car_catalog/
    api.py, schemas.py     REST API (FastAPI)
    server.py              команда car-catalog-api
    config.py              налаштування з environment variables
    logging_config.py      logging
    models.py, services.py, validators.py   предметна логіка (Lab_01)
    orm_models.py, database.py, repositories.py, db_services.py   БД (Lab_07)
    analytics.py, parallel.py, caching.py   оптимізації (Lab_09)
tests/                     unit- та integration-tests
benchmarks/                експерименти продуктивності (Lab_09)
migrations/, alembic.ini   міграції Alembic
Dockerfile, .dockerignore, docker-compose.yml
pyproject.toml, LICENSE, CHANGELOG.md, .env.example
```

## Troubleshooting

- `/health` повертає 503 — база не створена: виконайте `alembic upgrade head`.
- `401` на `POST` — додайте заголовок `X-API-Key` зі значенням `API_KEY`.
- Порт зайнятий — змініть `PORT` або `-p 8080:8000` у `docker run`.

## Author

Student: Кравець Владислав
Group: ФЕП-31

Ліцензія: MIT.
