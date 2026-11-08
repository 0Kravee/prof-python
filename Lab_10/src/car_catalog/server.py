"""Command line entry point of the API server (``car-catalog-api``)."""

import sys
from collections.abc import Sequence

import uvicorn

from car_catalog import __version__
from car_catalog.config import Settings


def main(argv: Sequence[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if args in (["--version"], ["-V"]):
        print(f"car-catalog {__version__}")
        return 0
    settings = Settings()
    uvicorn.run(
        "car_catalog.api:create_app",
        factory=True,
        host=settings.host,
        port=settings.port,
        log_config=None,  # our own logging configuration is used
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
