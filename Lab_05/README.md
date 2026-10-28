# Reliable Importer — Vehicle Catalog

Лабораторна робота №5 з курсу «Професійний Python», варіант №5 —
«Імпорт каталогу автомобілів» (узгоджено з Lab_01–Lab_04).
Тема: надійний імпорт/експорт даних, конфігурація YAML, logging, власні
exceptions, context managers, atomic output.

## Description

Програма потоково читає файл автомобілів (`vehicle_id, brand, model, year,
price, mileage`), перевіряє кожен запис, експортує коректні записи в JSON,
веде статистику й журнал, а некоректні записи зберігає окремо з причиною.

- **tolerant** режим (`skip_invalid: true`): некоректні записи пропускаються;
- **strict** режим (`skip_invalid: false`): перша помилка зупиняє обробку,
  попередній результат не пошкоджується (atomic output);
- діапазони `year` і `price` та інші параметри беруться з `config.yaml`;
- формати: CSV (потоково), JSON Lines (потоково), JSON, YAML (вхід);
  JSON та JSON Lines (вихід).

## Requirements

Python 3.11+, PyYAML (встановлюється автоматично).
Якщо PyYAML недоступний, `config.yaml` читає вбудований запасний парсер
простого підмножини YAML (для запуску без встановлення залежностей).

## Installation

    python -m venv .venv
    source .venv/bin/activate        # Windows: .venv\Scripts\activate
    python -m pip install -e ".[dev]"

## Run

    python -m reliable_importer.main
    python -m reliable_importer.main --config path/to/config.yaml
    python -m reliable_importer.main --strict      # або --tolerant

or

    reliable-importer

Without installation the file can be started directly:

    python src/reliable_importer/main.py

`config.yaml` is searched in the current directory, then in the project
root; paths inside it are relative to the config file. The program has no
`input()`, so it also runs in CI / pipes. Exit codes: `0` success,
`1` application error (configuration, input or output), `2` unexpected error.

### Environment overrides

`IMPORTER_INPUT_PATH`, `IMPORTER_OUTPUT_PATH`, `IMPORTER_SKIP_INVALID`
(`true/false`), `IMPORTER_LOG_LEVEL` override the matching `config.yaml` keys.

### Example output

    Mode: tolerant
    Invalid record at line 9: Vehicle brand is empty
    Invalid record at line 10: Year must be between 1990 and 2026
    ...
    Total=15, valid=8, invalid=7, exported=8
    Average price of exported vehicles: 27875.00

Results: `output/vehicles.json`, `output/errors.csv`, `logs/application.log`.

## Experiments

    python -m reliable_importer.experiments            # full (up to 500 000)
    python -m reliable_importer.experiments --quick

strict vs tolerant, streaming vs eager (time, peak memory), exception
chaining, atomic output, configuration errors.

## Type checking and tests

    python -m mypy            # strict mode, 0 errors expected
    python -m pytest

## Project structure

- `config.yaml`, `data/vehicles.csv` — configuration and sample input
- `src/reliable_importer/config.py` — YAML config, validation, env overrides
- `src/reliable_importer/yaml_loader.py` — PyYAML + safe fallback parser
- `src/reliable_importer/readers.py`, `importers.py` — streaming input
- `src/reliable_importer/validators.py` — record validation
- `src/reliable_importer/services.py` — import service, summary, error report
- `src/reliable_importer/exporters.py` — JSON / JSON Lines, atomic output
- `src/reliable_importer/utils.py` — context managers
- `src/reliable_importer/logging_config.py` — logging with rotation
- `src/reliable_importer/exceptions.py`, `models.py`, `main.py`
- `src/reliable_importer/experiments.py` — experiments
- `tests/` — pytest tests

## Author

Student: Кравець Владислав
Group: ФЕП-31
