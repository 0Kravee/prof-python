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
from typing import Any

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
        raise ConfigurationError(
            f"Invalid value for {name}: {raw!r}"
        ) from exc


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
