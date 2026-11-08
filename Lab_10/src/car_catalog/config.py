"""Configuration of the car catalog.

Module level constants are the defaults; :class:`AppConfig` carries the
effective values and :func:`load_config` builds it from an optional JSON
file and environment variables (environment wins).
"""

import json
import os
from collections.abc import Mapping
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Any, Literal

from pydantic import AliasChoices, Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError

from car_catalog.exceptions import ConfigurationError

MIN_YEAR: int = 1900
MAX_YEAR: int = 2100
MIN_PRICE: float = 0.0
MAX_PRICE: float = 10_000_000.0
MIN_MILEAGE: int = 0
CURRENCY: str = "USD"

ENV_PREFIX: str = "CAR_CATALOG_"


@dataclass(frozen=True, slots=True)
class AppConfig:
    """Effective limits used to validate cars."""

    min_year: int = MIN_YEAR
    max_year: int = MAX_YEAR
    min_price: float = MIN_PRICE
    max_price: float = MAX_PRICE
    currency: str = CURRENCY

    def __post_init__(self) -> None:
        if self.min_year > self.max_year:
            raise ConfigurationError("min_year must not exceed max_year")
        if self.min_price < 0:
            raise ConfigurationError("min_price cannot be negative")
        if self.min_price > self.max_price:
            raise ConfigurationError("min_price must not exceed max_price")
        if not self.currency.strip():
            raise ConfigurationError("currency must not be empty")


_CASTS: dict[str, type] = {
    "min_year": int,
    "max_year": int,
    "min_price": float,
    "max_price": float,
    "currency": str,
}


def _convert(name: str, raw: Any) -> Any:
    try:
        return _CASTS[name](raw)
    except (TypeError, ValueError) as exc:
        raise ConfigurationError(f"Invalid value for {name}: {raw!r}") from exc


def _read_file(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ConfigurationError(f"Config file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ConfigurationError(
            f"Config file is not valid JSON: {path}"
        ) from exc
    if not isinstance(data, dict):
        raise ConfigurationError("Config file must contain a JSON object")
    unknown = set(data) - set(_CASTS)
    if unknown:
        raise ConfigurationError(
            f"Unknown config keys: {', '.join(sorted(unknown))}"
        )
    return data


def load_config(
    path: Path | None = None,
    environ: Mapping[str, str] | None = None,
) -> AppConfig:
    """Build the configuration: defaults < JSON file < environment."""
    values: dict[str, Any] = {}
    if path is not None:
        values.update(_read_file(path))
    env = os.environ if environ is None else environ
    for field in fields(AppConfig):
        raw = env.get(ENV_PREFIX + field.name.upper())
        if raw is not None:
            values[field.name] = raw
    converted = {name: _convert(name, raw) for name, raw in values.items()}
    return AppConfig(**converted)


# --- production configuration (laboratory work 10) --------------------------
# The values come from environment variables (or a local ``.env`` file that
# is never committed). Nothing secret is stored in the source code.

LOG_LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")


class Settings(BaseSettings):
    """Application settings read from the environment."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    database_url: str = Field(
        default="sqlite:///./cars.db",
        repr=False,  # the URL may contain a password
        validation_alias=AliasChoices(
            "DATABASE_URL", "CAR_CATALOG_DATABASE_URL"
        ),
    )
    app_env: Literal["development", "test", "production"] = Field(
        default="development",
        validation_alias=AliasChoices("APP_ENV", "ENVIRONMENT"),
    )
    log_level: str = Field(default="INFO", validation_alias="LOG_LEVEL")
    api_key: SecretStr | None = Field(default=None, validation_alias="API_KEY")
    host: str = Field(default="127.0.0.1", validation_alias="HOST")
    port: int = Field(default=8000, ge=1, le=65535, validation_alias="PORT")
    auto_create_tables: bool = Field(
        default=False, validation_alias="AUTO_CREATE_TABLES"
    )

    @field_validator("app_env", mode="before")
    @classmethod
    def _normalize_environment(cls, value: object) -> object:
        return value.strip().lower() if isinstance(value, str) else value

    @field_validator("log_level", mode="before")
    @classmethod
    def _normalize_log_level(cls, value: object) -> str:
        level = str(value).strip().upper()
        if level not in LOG_LEVELS:
            raise ValueError(
                f"LOG_LEVEL must be one of {', '.join(LOG_LEVELS)}"
            )
        return level

    @field_validator("database_url")
    @classmethod
    def _check_database_url(cls, value: str) -> str:
        try:
            make_url(value)
        except ArgumentError as exc:
            raise ValueError(
                "DATABASE_URL is not a valid database URL"
            ) from exc
        return value

    @field_validator("api_key", mode="before")
    @classmethod
    def _empty_key_means_no_key(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def safe_database_url(self) -> str:
        """The URL with the password hidden: safe to log and to show."""
        return make_url(self.database_url).render_as_string(hide_password=True)

    def summary(self) -> dict[str, object]:
        """Settings for logs; secrets are never included."""
        return {
            "app_env": self.app_env,
            "database_url": self.safe_database_url,
            "log_level": self.log_level,
            "api_key_set": self.api_key is not None,
            "host": self.host,
            "port": self.port,
        }
