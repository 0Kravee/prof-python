"""Application settings (defaults can be overridden by CARS_* variables)."""

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATABASE_URL = f"sqlite:///{PROJECT_ROOT / 'data' / 'cars.db'}"

MIN_YEAR = 1886  # the first automobile
MAX_YEAR = 2100


@dataclass(frozen=True)
class Settings:
    """Everything that can be configured without touching the code."""

    database_url: str = DEFAULT_DATABASE_URL
    # None -> the batch endpoint calls this very application in-process
    # (ASGI transport); a URL -> a real HTTP request over the network.
    api_base_url: str | None = None
    max_attempts: int = 3
    backoff_seconds: float = 0.2
    request_timeout: float = 5.0
    batch_timeout: float = 10.0
    max_concurrency: int = 5
    max_batch_size: int = 100

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        if self.max_concurrency < 1:
            raise ValueError("max_concurrency must be at least 1")
        if self.max_batch_size < 1:
            raise ValueError("max_batch_size must be at least 1")
        for name in ("backoff_seconds", "request_timeout", "batch_timeout"):
            if getattr(self, name) < 0:
                raise ValueError(f"{name} must not be negative")
        if self.request_timeout == 0 or self.batch_timeout == 0:
            raise ValueError("timeouts must be positive")

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> "Settings":
        env = os.environ if environ is None else environ
        defaults = cls()
        return cls(
            database_url=env.get("CARS_DATABASE_URL", defaults.database_url),
            api_base_url=env.get("CARS_API_BASE_URL") or None,
            max_attempts=int(
                env.get("CARS_MAX_ATTEMPTS", defaults.max_attempts)
            ),
            backoff_seconds=float(
                env.get("CARS_BACKOFF_SECONDS", defaults.backoff_seconds)
            ),
            request_timeout=float(
                env.get("CARS_REQUEST_TIMEOUT", defaults.request_timeout)
            ),
            batch_timeout=float(
                env.get("CARS_BATCH_TIMEOUT", defaults.batch_timeout)
            ),
            max_concurrency=int(
                env.get("CARS_MAX_CONCURRENCY", defaults.max_concurrency)
            ),
            max_batch_size=int(
                env.get("CARS_MAX_BATCH_SIZE", defaults.max_batch_size)
            ),
        )
