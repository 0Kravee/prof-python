"""Logging configuration (the application never uses ``print`` for logs)."""

import logging
import logging.config
from typing import Any

DEVELOPMENT_FORMAT = "%(asctime)s %(levelname)-8s %(name)s: %(message)s"
PRODUCTION_FORMAT = (
    "%(asctime)s level=%(levelname)s logger=%(name)s message=%(message)s"
)


def build_logging_config(
    level: str = "INFO", environment: str = "development"
) -> dict[str, Any]:
    """dictConfig for the given level and environment."""
    log_format = (
        PRODUCTION_FORMAT
        if environment == "production"
        else DEVELOPMENT_FORMAT
    )
    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {"default": {"format": log_format}},
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "default",
                "stream": "ext://sys.stderr",
            }
        },
        "root": {"level": level.upper(), "handlers": ["console"]},
        "loggers": {
            # keep third-party libraries quiet unless DEBUG is requested
            "sqlalchemy.engine": {
                "level": "INFO" if level.upper() == "DEBUG" else "WARNING"
            },
            "uvicorn.access": {"level": "WARNING"},
        },
    }


def configure_logging(
    level: str = "INFO", environment: str = "development"
) -> None:
    """Apply the configuration (safe to call more than once)."""
    logging.config.dictConfig(build_logging_config(level, environment))
