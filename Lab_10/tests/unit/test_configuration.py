"""Unit tests of the configuration (defaults, JSON file, environment)."""

import json
from pathlib import Path

import pytest

from car_catalog.config import (
    CURRENCY,
    MAX_PRICE,
    MAX_YEAR,
    MIN_PRICE,
    MIN_YEAR,
    AppConfig,
    load_config,
)
from car_catalog.exceptions import ConfigurationError


def test_defaults_match_module_constants() -> None:
    config = AppConfig()
    assert (config.min_year, config.max_year) == (MIN_YEAR, MAX_YEAR)
    assert (config.min_price, config.max_price) == (MIN_PRICE, MAX_PRICE)
    assert config.currency == CURRENCY


def test_load_config_without_sources_returns_defaults() -> None:
    assert load_config() == AppConfig()


def test_environment_variables_override_defaults(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CAR_CATALOG_MIN_YEAR", "2000")
    monkeypatch.setenv("CAR_CATALOG_MAX_PRICE", "75000.5")
    monkeypatch.setenv("CAR_CATALOG_CURRENCY", "EUR")
    config = load_config()
    assert config.min_year == 2000
    assert config.max_price == pytest.approx(75000.5)
    assert config.currency == "EUR"
    assert config.max_year == MAX_YEAR  # untouched


def test_explicit_environ_mapping_ignores_real_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CAR_CATALOG_MIN_YEAR", "2000")
    config = load_config(environ={"CAR_CATALOG_MIN_YEAR": "2010"})
    assert config.min_year == 2010


def test_removed_variable_falls_back_to_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CAR_CATALOG_MIN_YEAR", "2000")
    monkeypatch.delenv("CAR_CATALOG_MIN_YEAR")
    assert load_config().min_year == MIN_YEAR


def test_json_file_is_read(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    path.write_text(
        json.dumps({"min_year": 1990, "max_year": 2030, "currency": "UAH"}),
        encoding="utf-8",
    )
    config = load_config(path)
    assert (config.min_year, config.max_year) == (1990, 2030)
    assert config.currency == "UAH"


def test_environment_wins_over_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"min_year": 1990}), encoding="utf-8")
    monkeypatch.setenv("CAR_CATALOG_MIN_YEAR", "2005")
    assert load_config(path).min_year == 2005


@pytest.mark.parametrize(
    "kwargs",
    [
        {"min_year": 2020, "max_year": 2010},
        {"min_price": -1.0},
        {"min_price": 100.0, "max_price": 50.0},
        {"currency": "  "},
    ],
    ids=[
        "years-swapped",
        "negative-min-price",
        "prices-swapped",
        "blank-currency",
    ],
)
def test_inconsistent_configuration_is_rejected(kwargs) -> None:
    with pytest.raises(ConfigurationError):
        AppConfig(**kwargs)


def test_equal_bounds_are_allowed() -> None:
    config = AppConfig(min_year=2020, max_year=2020)
    assert config.min_year == config.max_year


def test_non_numeric_environment_value_keeps_original_error() -> None:
    with pytest.raises(ConfigurationError, match="min_year") as excinfo:
        load_config(environ={"CAR_CATALOG_MIN_YEAR": "abc"})
    assert isinstance(excinfo.value.__cause__, ValueError)


@pytest.mark.parametrize(
    ("content", "message"),
    [
        ("{not json", "not valid JSON"),
        ("[1, 2]", "JSON object"),
        ('{"colour": "red"}', "Unknown config keys: colour"),
        ('{"min_year": "x"}', "min_year"),
    ],
)
def test_broken_config_files(tmp_path: Path, content, message) -> None:
    path = tmp_path / "config.json"
    path.write_text(content, encoding="utf-8")
    with pytest.raises(ConfigurationError, match=message):
        load_config(path)


def test_missing_config_file(tmp_path: Path) -> None:
    with pytest.raises(ConfigurationError, match="not found"):
        load_config(tmp_path / "absent.json")
