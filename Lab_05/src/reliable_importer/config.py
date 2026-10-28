"""Configuration loader and validation."""

import copy
import math
import os
from collections.abc import Mapping
from pathlib import Path

from reliable_importer.exceptions import ConfigurationError
from reliable_importer.logging_config import LEVELS
from reliable_importer.models import (
    AppConfig,
    InputConfig,
    LoggingConfig,
    OutputConfig,
    ProcessingConfig,
    ValidationRules,
)
from reliable_importer.yaml_loader import load_yaml_text

SUPPORTED_SCHEMA_VERSION = 1
INPUT_FORMATS = ("auto", "csv", "json", "jsonl", "yaml")
OUTPUT_FORMATS = ("auto", "json", "jsonl")
ABSOLUTE_MIN_YEAR = 1886  # the first automobile
ABSOLUTE_MAX_YEAR = 2100

# environment variable -> path of the key in the configuration
ENV_OVERRIDES: dict[str, tuple[str, str]] = {
    "IMPORTER_INPUT_PATH": ("input", "path"),
    "IMPORTER_OUTPUT_PATH": ("output", "path"),
    "IMPORTER_SKIP_INVALID": ("processing", "skip_invalid"),
    "IMPORTER_LOG_LEVEL": ("logging", "level"),
}
_TRUE = ("1", "true", "yes", "on")
_FALSE = ("0", "false", "no", "off")


def load_config(
    path: Path, environ: Mapping[str, str] | None = None
) -> AppConfig:
    """Read, override from the environment, build and validate the config."""
    raw = _read_mapping(path)
    raw = apply_env_overrides(raw, os.environ if environ is None else environ)
    config = _build_config(raw, base_dir=path.parent)
    validate_config(config)
    return config


def _read_mapping(path: Path) -> dict[str, object]:
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError as error:
        raise ConfigurationError(
            f"Configuration file not found: {path}"
        ) from error
    except (OSError, UnicodeDecodeError) as error:
        raise ConfigurationError(
            f"Cannot read configuration file: {path}"
        ) from error
    loaded = load_yaml_text(text)
    if not isinstance(loaded, dict):
        raise ConfigurationError("Configuration root must be a mapping")
    return {str(key): value for key, value in loaded.items()}


def apply_env_overrides(
    raw: Mapping[str, object], environ: Mapping[str, str]
) -> dict[str, object]:
    """Return a copy of ``raw`` with values taken from IMPORTER_* variables."""
    result: dict[str, object] = copy.deepcopy(dict(raw))
    for variable, (section, key) in ENV_OVERRIDES.items():
        if variable not in environ:
            continue
        value: object = environ[variable]
        if variable == "IMPORTER_SKIP_INVALID":
            value = _parse_bool_text(variable, str(value))
        target = result.get(section)
        if not isinstance(target, dict):
            target = {}
            result[section] = target
        target[key] = value
    return result


def _parse_bool_text(name: str, text: str) -> bool:
    lowered = text.strip().lower()
    if lowered in _TRUE:
        return True
    if lowered in _FALSE:
        return False
    raise ConfigurationError(f"{name} must be a boolean, got {text!r}")


def _section(raw: Mapping[str, object], name: str) -> Mapping[str, object]:
    value = raw.get(name)
    if value is None:
        raise ConfigurationError(f"Missing configuration section: {name}")
    if not isinstance(value, dict):
        raise ConfigurationError(f"Section {name!r} must be a mapping")
    return value


def _required(section: Mapping[str, object], name: str, key: str) -> object:
    if key not in section or section[key] is None:
        raise ConfigurationError(f"Missing configuration key: {name}.{key}")
    return section[key]


def _text(section: Mapping[str, object], name: str, key: str) -> str:
    value = _required(section, name, key)
    if not isinstance(value, str) or not value.strip():
        raise ConfigurationError(f"{name}.{key} must be a non-empty string")
    return value.strip()


def _integer(section: Mapping[str, object], name: str, key: str) -> int:
    value = _required(section, name, key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ConfigurationError(f"{name}.{key} must be an integer")
    return value


def _number(section: Mapping[str, object], name: str, key: str) -> float:
    value = _required(section, name, key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ConfigurationError(f"{name}.{key} must be a number")
    if not math.isfinite(value):
        raise ConfigurationError(f"{name}.{key} must be a finite number")
    return float(value)


def _boolean(section: Mapping[str, object], name: str, key: str) -> bool:
    value = _required(section, name, key)
    if not isinstance(value, bool):
        raise ConfigurationError(f"{name}.{key} must be true or false")
    return value


def _resolve(base_dir: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else base_dir / path


def _build_config(raw: Mapping[str, object], *, base_dir: Path) -> AppConfig:
    schema_version = raw.get("schema_version", SUPPORTED_SCHEMA_VERSION)
    if (
        isinstance(schema_version, bool)
        or schema_version != SUPPORTED_SCHEMA_VERSION
    ):
        raise ConfigurationError(
            f"Unsupported schema_version: {schema_version!r} "
            f"(expected {SUPPORTED_SCHEMA_VERSION})"
        )

    source = _section(raw, "input")
    target = _section(raw, "output")
    processing = _section(raw, "processing")
    logging_section = _section(raw, "logging")

    errors_value = target.get("errors_path")
    errors_path: Path | None = None
    if errors_value is not None:
        errors_path = _resolve(
            base_dir, _text(target, "output", "errors_path")
        )
    backup = target.get("backup_existing", False)
    if not isinstance(backup, bool):
        raise ConfigurationError(
            "output.backup_existing must be true or false"
        )

    return AppConfig(
        schema_version=SUPPORTED_SCHEMA_VERSION,
        input=InputConfig(
            path=_resolve(base_dir, _text(source, "input", "path")),
            format=str(source.get("format", "auto")).strip().lower(),
        ),
        output=OutputConfig(
            path=_resolve(base_dir, _text(target, "output", "path")),
            format=str(target.get("format", "auto")).strip().lower(),
            errors_path=errors_path,
            backup_existing=backup,
        ),
        processing=ProcessingConfig(
            skip_invalid=_boolean(processing, "processing", "skip_invalid"),
            rules=ValidationRules(
                minimum_year=_integer(
                    processing, "processing", "minimum_year"
                ),
                maximum_year=_integer(
                    processing, "processing", "maximum_year"
                ),
                minimum_price=_number(
                    processing, "processing", "minimum_price"
                ),
                maximum_price=_number(
                    processing, "processing", "maximum_price"
                ),
            ),
        ),
        logging=LoggingConfig(
            level=_text(logging_section, "logging", "level").upper(),
            path=_resolve(base_dir, _text(logging_section, "logging", "path")),
            max_bytes=_optional_int(logging_section, "max_bytes", 1_048_576),
            backup_count=_optional_int(logging_section, "backup_count", 3),
        ),
    )


def _optional_int(
    section: Mapping[str, object], key: str, default: int
) -> int:
    value = section.get(key, default)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ConfigurationError(f"logging.{key} must be an integer")
    return value


def validate_config(config: AppConfig) -> None:
    """Check the meaning of the values and the existence of the input."""
    rules = config.processing.rules
    if not (
        ABSOLUTE_MIN_YEAR <= rules.minimum_year <= ABSOLUTE_MAX_YEAR
        and ABSOLUTE_MIN_YEAR <= rules.maximum_year <= ABSOLUTE_MAX_YEAR
    ):
        raise ConfigurationError(
            f"Years must be between {ABSOLUTE_MIN_YEAR} "
            f"and {ABSOLUTE_MAX_YEAR}"
        )
    if rules.minimum_year > rules.maximum_year:
        raise ConfigurationError("minimum_year must not exceed maximum_year")
    if rules.minimum_price < 0:
        raise ConfigurationError("minimum_price must not be negative")
    if rules.minimum_price > rules.maximum_price:
        raise ConfigurationError("minimum_price must not exceed maximum_price")
    if config.logging.level not in LEVELS:
        raise ConfigurationError(
            f"Unknown logging level {config.logging.level!r}; "
            f"expected one of {', '.join(LEVELS)}"
        )
    if config.logging.max_bytes < 0 or config.logging.backup_count < 0:
        raise ConfigurationError("max_bytes and backup_count must be >= 0")
    if config.input.format not in INPUT_FORMATS:
        raise ConfigurationError(
            f"Unknown input format: {config.input.format}"
        )
    if config.output.format not in OUTPUT_FORMATS:
        raise ConfigurationError(
            f"Unknown output format: {config.output.format}"
        )
    if not config.input.path.is_file():
        raise ConfigurationError(f"Input file not found: {config.input.path}")
    if config.output.path.is_dir():
        raise ConfigurationError(
            f"Output path is a directory: {config.output.path}"
        )
