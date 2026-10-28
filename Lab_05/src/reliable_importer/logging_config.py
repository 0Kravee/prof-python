"""Logging configuration: console + rotating log file."""

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOG_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")


def configure_logging(
    level: str,
    path: Path,
    *,
    max_bytes: int = 1_048_576,
    backup_count: int = 3,
) -> None:
    """Replace the root handlers by a rotating file and a console handler."""
    path.parent.mkdir(parents=True, exist_ok=True)
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    formatter = logging.Formatter(LOG_FORMAT)
    file_handler = RotatingFileHandler(
        path,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    console_handler = logging.StreamHandler(sys.stderr)
    root = logging.getLogger()
    close_logging()
    for handler in (file_handler, console_handler):
        handler.setFormatter(formatter)
        root.addHandler(handler)
    root.setLevel(numeric_level)


def close_logging() -> None:
    """Flush and close every root handler (releases the log file)."""
    root = logging.getLogger()
    for handler in list(root.handlers):
        root.removeHandler(handler)
        handler.close()
