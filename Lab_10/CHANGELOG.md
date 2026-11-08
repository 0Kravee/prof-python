# Changelog

All notable changes of the project. The format follows
[Keep a Changelog](https://keepachangelog.com/) and the project uses
[Semantic Versioning](https://semver.org/).

## [1.0.0] - 2026-11-06

First production-oriented release (laboratory work 10).

### Added
- REST API (FastAPI): `/cars`, `/manufacturers`,
  `/manufacturers/{id}/cars`, `/statistics` and `GET /health`.
- Configuration through environment variables (`DATABASE_URL`, `APP_ENV`,
  `LOG_LEVEL`, `API_KEY` ...) with validation (pydantic-settings).
- Optional API key protection for `POST`, `PATCH` and `DELETE`.
- Production logging configuration.
- Python packaging: wheel and sdist, `py.typed`, console scripts.
- Dockerfile (multi-stage, non-root user, HEALTHCHECK), `.dockerignore`,
  Docker Compose, migrations applied on container start.
- GitHub Actions: ruff, mypy, pytest (Python 3.11 and 3.12) with coverage
  threshold, package build, Docker build and smoke test, release on tag.
- Pre-commit hooks, OpenAPI export (`docs/openapi.json`).

### Changed
- `DATABASE_URL` is the main database variable (`CAR_CATALOG_DATABASE_URL`
  from earlier laboratory works still works).

## [0.9.0] - Laboratory work 9
- Profiling, NumPy analytics, threads, processes, caching.

## [0.7.0] - Laboratory work 7
- SQLite persistence layer, SQLAlchemy ORM, Alembic migrations.

## [0.4.0] - Laboratory work 6
- Automated tests, CSV import, JSON export.

## [0.2.0] - Laboratory work 1
- Console application "Car catalog".
