"""Write the OpenAPI schema of the API to ``docs/openapi.json``.

python scripts/export_openapi.py
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from car_catalog.api import create_app  # noqa: E402
from car_catalog.config import Settings  # noqa: E402


def build_schema() -> dict[str, object]:
    settings = Settings(_env_file=None, database_url="sqlite://")
    return create_app(settings).openapi()


def main() -> int:
    target = ROOT / "docs" / "openapi.json"
    target.parent.mkdir(exist_ok=True)
    target.write_text(
        json.dumps(build_schema(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"written {target}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
