"""Context managers: operation logging and transaction-like file output."""

import logging
import os
import shutil
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from time import perf_counter
from typing import TextIO

logger = logging.getLogger(__name__)


@contextmanager
def logged_operation(operation: str) -> Iterator[None]:
    """Log the start, the duration or the failure of an operation."""
    logger.info("%s started", operation)
    start = perf_counter()
    try:
        yield
    except Exception:
        logger.exception("%s failed", operation)
        raise
    else:
        elapsed = perf_counter() - start
        logger.info("%s finished in %.6f s", operation, elapsed)


@contextmanager
def atomic_output(
    path: Path,
    *,
    newline: str | None = None,
    backup: bool = False,
) -> Iterator[TextIO]:
    """Write to a temporary file and replace ``path`` only on success.

    If anything fails inside the ``with`` block, the temporary file is
    removed and the previous content of ``path`` stays untouched.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    try:
        with temporary.open("w", encoding="utf-8", newline=newline) as file:
            yield file
            file.flush()
            os.fsync(file.fileno())
        if backup and path.exists():
            shutil.copy2(path, path.with_name(path.name + ".bak"))
        temporary.replace(path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
