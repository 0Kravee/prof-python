"""Command line entry point of the reliable importer."""

import argparse
import logging
import sys
from collections.abc import Sequence
from dataclasses import replace
from pathlib import Path

# Allows running this file directly (``python main.py``) without
# installing the package: the ``src`` directory is added to sys.path.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from reliable_importer.config import load_config  # noqa: E402
from reliable_importer.exceptions import ApplicationError  # noqa: E402
from reliable_importer.logging_config import (  # noqa: E402
    close_logging,
    configure_logging,
)
from reliable_importer.models import AppConfig  # noqa: E402
from reliable_importer.services import RunResult, run_import  # noqa: E402

logger = logging.getLogger("reliable_importer")

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def find_config(explicit: Path | None) -> Path:
    """Explicit path, else ./config.yaml, else the project's config.yaml."""
    if explicit is not None:
        return explicit
    local = Path.cwd() / "config.yaml"
    return local if local.is_file() else PROJECT_ROOT / "config.yaml"


def parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="reliable-importer",
        description="Import vehicles from a file, validate and export them.",
    )
    parser.add_argument("--config", type=Path, help="path to config.yaml")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--strict",
        action="store_true",
        help="abort on the first invalid record (overrides the config)",
    )
    mode.add_argument(
        "--tolerant",
        action="store_true",
        help="skip invalid records (overrides the config)",
    )
    return parser.parse_args(argv)


def apply_mode(config: AppConfig, args: argparse.Namespace) -> AppConfig:
    if not (args.strict or args.tolerant):
        return config
    processing = replace(config.processing, skip_invalid=args.tolerant)
    return replace(config, processing=processing)


def log_result(result: RunResult) -> None:
    stats, summary = result.statistics, result.summary
    logger.info(
        "Total=%s, valid=%s, invalid=%s, exported=%s",
        stats.total,
        stats.valid,
        stats.invalid,
        stats.exported,
    )
    expensive = summary.most_expensive
    lowest = summary.lowest_mileage
    logger.info(
        "Average price of exported vehicles: %.2f", summary.average_price
    )
    if expensive is not None:
        logger.info(
            "Most expensive: %s %s (%.2f)",
            expensive.brand,
            expensive.model,
            expensive.price,
        )
    if lowest is not None:
        logger.info(
            "Lowest mileage: %s %s (%s km)",
            lowest.brand,
            lowest.model,
            lowest.mileage,
        )


def main(argv: Sequence[str] | None = None) -> int:
    """Run the application; the return value is the process exit code."""
    args = parse_args(argv)
    try:
        config = apply_mode(load_config(find_config(args.config)), args)
        configure_logging(
            config.logging.level,
            config.logging.path,
            max_bytes=config.logging.max_bytes,
            backup_count=config.logging.backup_count,
        )
    except ApplicationError as error:
        print(f"Configuration error: {error}", file=sys.stderr)
        if error.__cause__ is not None:
            print(f"Caused by: {error.__cause__!r}", file=sys.stderr)
        return 1
    try:
        mode = "tolerant" if config.processing.skip_invalid else "strict"
        logger.info("Mode: %s", mode)
        log_result(run_import(config))
        return 0
    except ApplicationError as error:
        logger.error("Application error: %s", error)
        if error.__cause__ is not None:
            logger.error("Caused by: %r", error.__cause__)
        return 1
    except Exception:  # last-resort boundary: log the traceback, exit 2
        logger.exception("Unexpected error")
        return 2
    finally:
        close_logging()


if __name__ == "__main__":
    raise SystemExit(main())
