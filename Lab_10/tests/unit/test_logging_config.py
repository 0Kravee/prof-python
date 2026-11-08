"""Unit tests of the logging configuration."""

import logging

import pytest

from car_catalog.logging_config import (
    DEVELOPMENT_FORMAT,
    PRODUCTION_FORMAT,
    build_logging_config,
    configure_logging,
)


@pytest.fixture
def restore_logging():
    """configure_logging changes the root logger: put it back afterwards."""
    root = logging.getLogger()
    level, handlers = root.level, list(root.handlers)
    yield
    root.setLevel(level)
    root.handlers[:] = handlers


def test_config_uses_the_requested_level() -> None:
    config = build_logging_config("warning")
    assert config["root"]["level"] == "WARNING"


def test_production_and_development_formats_differ() -> None:
    development = build_logging_config("INFO", "development")
    production = build_logging_config("INFO", "production")
    assert development["formatters"]["default"]["format"] == DEVELOPMENT_FORMAT
    assert production["formatters"]["default"]["format"] == PRODUCTION_FORMAT
    assert "level=" in PRODUCTION_FORMAT


def test_logs_go_to_stderr_not_to_stdout() -> None:
    handler = build_logging_config()["handlers"]["console"]
    assert handler["stream"] == "ext://sys.stderr"


def test_noisy_libraries_are_quiet_by_default() -> None:
    loggers = build_logging_config("INFO")["loggers"]
    assert loggers["sqlalchemy.engine"]["level"] == "WARNING"
    assert (
        build_logging_config("DEBUG")["loggers"]["sqlalchemy.engine"]["level"]
        == "INFO"
    )


def test_existing_loggers_are_not_disabled() -> None:
    assert build_logging_config()["disable_existing_loggers"] is False


def test_configure_logging_sets_the_root_level(restore_logging) -> None:
    configure_logging("ERROR", "production")
    assert logging.getLogger().level == logging.ERROR
    configure_logging("DEBUG")
    assert logging.getLogger().level == logging.DEBUG


def test_configure_logging_can_be_called_twice(restore_logging) -> None:
    configure_logging("INFO")
    configure_logging("INFO")
    handlers = [
        h
        for h in logging.getLogger().handlers
        if isinstance(h, logging.StreamHandler)
    ]
    assert len(handlers) >= 1
    assert len(logging.getLogger().handlers) == len(
        {id(h) for h in logging.getLogger().handlers}
    )
