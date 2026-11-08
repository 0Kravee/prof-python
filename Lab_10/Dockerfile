# syntax=docker/dockerfile:1

# ---------- stage 1: build the wheel ----------
FROM python:3.12-slim AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /build
RUN pip install build

COPY pyproject.toml README.md LICENSE ./
COPY src ./src
RUN python -m build --wheel --outdir /dist


# ---------- stage 2: small runtime image ----------
FROM python:3.12-slim AS runtime

# Non-secret defaults only. Secrets (API_KEY, real database passwords)
# are passed when the container starts: -e, --env-file or the orchestrator.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    APP_ENV=production \
    LOG_LEVEL=INFO \
    HOST=0.0.0.0 \
    PORT=8000 \
    DATABASE_URL=sqlite:////data/cars.db

# Run as an unprivileged user, not as root
RUN groupadd --system app \
    && useradd --system --gid app --home-dir /app --shell /usr/sbin/nologin app \
    && mkdir -p /app /data \
    && chown -R app:app /app /data

WORKDIR /app

COPY --from=builder /dist/*.whl /tmp/wheels/
RUN pip install /tmp/wheels/*.whl && rm -rf /tmp/wheels

# Alembic configuration and migrations (applied when the container starts)
COPY --chown=app:app alembic.ini ./
COPY --chown=app:app migrations ./migrations

USER app

# SQLite database file lives in a volume
VOLUME ["/data"]
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=15s --retries=3 \
    CMD ["python", "-c", "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:%s/health' % os.environ.get('PORT', '8000'), timeout=2)"]

# Apply database migrations, then start the API server
CMD ["sh", "-c", "alembic upgrade head && exec car-catalog-api"]
