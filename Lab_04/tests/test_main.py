"""Headless running, direct launch, static typing and file hygiene."""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"


def run(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, *args],
        cwd=cwd,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )


def test_direct_run_without_installation() -> None:
    result = run(["main.py"], SRC / "domain_app")
    assert result.returncode == 0, result.stderr
    assert "Most expensive: Tesla Model Y" in result.stdout


def test_direct_run_from_project_root() -> None:
    result = run(["src/domain_app/main.py"], ROOT)
    assert result.returncode == 0, result.stderr
    assert "Research: dependency injection" in result.stdout


def test_main_function_can_be_called_twice() -> None:
    from domain_app.main import main

    main()
    main()


def test_mypy_strict_passes_on_sources() -> None:
    result = run(["-m", "mypy"], ROOT)
    assert result.returncode == 0, result.stdout
    assert "Success: no issues found" in result.stdout


def test_type_error_experiment_reports_exactly_three_errors() -> None:
    result = run(["-m", "mypy", "experiments/type_errors_demo.py"], ROOT)
    assert result.returncode == 1
    assert "Found 3 errors" in result.stdout
    for code in ("[assignment]", "[return-value]", "[arg-type]"):
        assert code in result.stdout


def test_fixed_type_experiment_passes() -> None:
    result = run(["-m", "mypy", "experiments/type_errors_fixed.py"], ROOT)
    assert result.returncode == 0, result.stdout


def test_ci_like_check_command_is_importable() -> None:
    from domain_app.check import main

    assert callable(main)


def test_no_utf8_bom_in_sources() -> None:
    files = [*ROOT.rglob("*.py"), ROOT / ".gitignore", ROOT / "README.md"]
    for path in files:
        if ".venv" in path.parts or not path.exists():
            continue
        assert not path.read_bytes().startswith(b"\xef\xbb\xbf"), path
