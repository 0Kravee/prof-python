"""CI-like command: static type checking followed by the tests.

Run it with ``python -m domain_app.check`` or ``domain-check``.
"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def run_step(title: str, command: list[str]) -> int:
    print(f"\n=== {title} ===")
    completed = subprocess.run(command, cwd=ROOT, check=False)
    print(f"-> exit code {completed.returncode}")
    return completed.returncode


def main() -> int:
    steps = [
        ("mypy (strict)", [sys.executable, "-m", "mypy"]),
        ("pytest", [sys.executable, "-m", "pytest", "-q"]),
    ]
    for title, command in steps:
        code = run_step(title, command)
        if code != 0:
            print(f"\nFAILED at step: {title}")
            return code
    print("\nAll checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
