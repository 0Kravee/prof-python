"""Domain and configuration models."""

from collections.abc import Mapping
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import NamedTuple


@dataclass(frozen=True, slots=True)
class Vehicle:
    """A valid vehicle record (immutable)."""

    vehicle_id: int
    brand: str
    model: str
    year: int
    price: float
    mileage: int

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


class RawRow(NamedTuple):
    """One unvalidated input record and where it came from."""

    line_number: int
    data: Mapping[str, object]


@dataclass(frozen=True, slots=True)
class ValidationRules:
    """Validation policy loaded from the configuration."""

    minimum_year: int
    maximum_year: int
    minimum_price: float
    maximum_price: float


@dataclass(frozen=True, slots=True)
class InputConfig:
    path: Path
    format: str


@dataclass(frozen=True, slots=True)
class OutputConfig:
    path: Path
    format: str
    errors_path: Path | None
    backup_existing: bool


@dataclass(frozen=True, slots=True)
class ProcessingConfig:
    skip_invalid: bool
    rules: ValidationRules


@dataclass(frozen=True, slots=True)
class LoggingConfig:
    level: str
    path: Path
    max_bytes: int
    backup_count: int


@dataclass(frozen=True, slots=True)
class AppConfig:
    schema_version: int
    input: InputConfig
    output: OutputConfig
    processing: ProcessingConfig
    logging: LoggingConfig
