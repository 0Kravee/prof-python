"""Command line behaviour, direct launch, headless runs and static typing."""

import contextlib
import io
import json
import subprocess
import sys
from pathlib import Path

import pytest

from conftest import make_config
from reliable_importer import main as main_module
from reliable_importer.main import find_config, main

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
MAIN_FILE = SRC / "reliable_importer" / "main.py"


def run_main(*argv: str) -> tuple[int, str]:
    buffer = io.StringIO()
    with contextlib.redirect_stderr(buffer):
        code = main(list(argv))
    return code, buffer.getvalue()


def test_success_exit_code_and_outputs(tmp_path: Path, csv_file: Path) -> None:
    config = make_config(tmp_path)
    code, stderr = run_main("--config", str(config))
    assert code == 0
    assert "Total=6, valid=3, invalid=3, exported=3" in stderr
    assert "Most expensive: BMW X5" in stderr
    assert json.loads((tmp_path / "out" / "result.json").read_text("utf-8"))
    assert "Total=6" in (tmp_path / "app.log").read_text(encoding="utf-8")


def test_strict_flag_overrides_the_config(
    tmp_path: Path, csv_file: Path
) -> None:
    config = make_config(tmp_path, skip=True)
    code, stderr = run_main("--config", str(config), "--strict")
    assert code == 1
    assert "Mode: strict" in stderr
    assert "Application error: Vehicle brand is empty" in stderr
    assert not (tmp_path / "out" / "result.json").exists()


def test_tolerant_flag_overrides_the_config(
    tmp_path: Path, csv_file: Path
) -> None:
    config = make_config(tmp_path, skip=False)
    code, stderr = run_main("--config", str(config), "--tolerant")
    assert code == 0 and "Mode: tolerant" in stderr


def test_strict_failure_keeps_the_previous_output(
    tmp_path: Path, csv_file: Path
) -> None:
    config = make_config(tmp_path, skip=True)
    assert run_main("--config", str(config))[0] == 0
    output = tmp_path / "out" / "result.json"
    before = output.read_bytes()
    assert run_main("--config", str(config), "--strict")[0] == 1
    assert output.read_bytes() == before
    assert not list((tmp_path / "out").glob("*.tmp"))


def test_missing_config_is_a_controlled_exit(tmp_path: Path) -> None:
    code, stderr = run_main("--config", str(tmp_path / "nope.yaml"))
    assert code == 1
    assert "Configuration error: Configuration file not found" in stderr
    assert "Traceback" not in stderr
    assert "Caused by: FileNotFoundError" in stderr


def test_invalid_config_value_is_a_controlled_exit(
    tmp_path: Path, csv_file: Path
) -> None:
    path = make_config(tmp_path)
    path.write_text(
        path.read_text(encoding="utf-8").replace("2026", "3000"),
        encoding="utf-8",
    )
    code, stderr = run_main("--config", str(path))
    assert code == 1 and "Years must be between" in stderr


def test_missing_input_file_is_a_controlled_exit(tmp_path: Path) -> None:
    code, stderr = run_main("--config", str(make_config(tmp_path)))
    assert code == 1 and "Input file not found" in stderr


def test_unreadable_input_reports_the_cause(tmp_path: Path) -> None:
    (tmp_path / "vehicles.csv").write_bytes(b"\xff\xfe\x00bad")
    code, stderr = run_main("--config", str(make_config(tmp_path)))
    assert code == 1
    assert "Caused by: UnicodeDecodeError" in stderr


def test_unexpected_error_exits_with_code_2(
    tmp_path: Path, csv_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def explode(*_: object, **__: object) -> None:
        raise RuntimeError("surprise")

    monkeypatch.setattr(main_module, "run_import", explode)
    code, stderr = run_main("--config", str(make_config(tmp_path)))
    assert code == 2 and "Unexpected error" in stderr and "surprise" in stderr


def test_environment_override_reaches_the_application(
    tmp_path: Path, csv_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("IMPORTER_SKIP_INVALID", "false")
    code, stderr = run_main("--config", str(make_config(tmp_path)))
    assert code == 1 and "Mode: strict" in stderr


def test_config_discovery(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    assert find_config(None) == main_module.PROJECT_ROOT / "config.yaml"
    local = tmp_path / "config.yaml"
    local.write_text("x: 1\n", encoding="utf-8")
    assert find_config(None) == local
    assert find_config(Path("explicit.yaml")) == Path("explicit.yaml")


def test_conflicting_mode_flags_are_rejected(tmp_path: Path) -> None:
    with pytest.raises(SystemExit) as info:
        main(["--strict", "--tolerant"])
    assert info.value.code == 2


# ---------------------------------------------- launching as a real process
def launch(
    args: list[str], cwd: Path, *, code: str | None = None
) -> subprocess.CompletedProcess[str]:
    command = (
        [sys.executable, *args]
        if code is None
        else [sys.executable, "-c", code]
    )
    return subprocess.run(
        command,
        cwd=cwd,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )


def project_copy(tmp_path: Path) -> Path:
    """A throw-away copy of config.yaml + data, so the repo stays clean."""
    for name in ("config.yaml",):
        (tmp_path / name).write_text(
            (ROOT / name).read_text(encoding="utf-8"), encoding="utf-8"
        )
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "vehicles.csv").write_text(
        (ROOT / "data" / "vehicles.csv").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    return tmp_path


def test_direct_run_with_explicit_config(tmp_path: Path) -> None:
    folder = project_copy(tmp_path)
    result = launch(
        [str(MAIN_FILE), "--config", str(folder / "config.yaml")], tmp_path
    )
    assert result.returncode == 0, result.stderr
    assert "Total=15, valid=8, invalid=7, exported=8" in result.stderr
    assert (folder / "output" / "vehicles.json").exists()
    assert (folder / "output" / "errors.csv").exists()
    assert (folder / "logs" / "application.log").exists()


def test_direct_run_uses_the_config_in_the_current_directory(
    tmp_path: Path,
) -> None:
    folder = project_copy(tmp_path)
    result = launch([str(MAIN_FILE)], folder)
    assert result.returncode == 0, result.stderr
    assert (folder / "output" / "vehicles.json").exists()


def test_direct_run_from_the_source_directory(tmp_path: Path) -> None:
    """``python main.py`` in src/reliable_importer must not crash."""
    folder = project_copy(tmp_path)
    result = launch(
        ["main.py", "--config", str(folder / "config.yaml")], MAIN_FILE.parent
    )
    assert result.returncode == 0, result.stderr


def test_run_without_pyyaml_uses_the_fallback_parser(tmp_path: Path) -> None:
    folder = project_copy(tmp_path)
    code = (
        "import sys, runpy; sys.modules['yaml'] = None; "
        "sys.argv = ['main.py', '--config', sys.argv[1]]; "
        f"runpy.run_path({str(MAIN_FILE)!r}, run_name='__main__')"
    )
    result = subprocess.run(
        [sys.executable, "-c", code, str(folder / "config.yaml")],
        cwd=tmp_path,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_default_project_run_is_headless(tmp_path: Path) -> None:
    """No input() anywhere: closed stdin never matters."""
    folder = project_copy(tmp_path)
    result = launch(
        [str(MAIN_FILE), "--config", str(folder / "config.yaml")], tmp_path
    )
    assert "EOFError" not in result.stderr and result.returncode == 0


def test_mypy_strict_passes_on_sources() -> None:
    result = launch(["-m", "mypy"], ROOT)
    assert result.returncode == 0, result.stdout
    assert "Success: no issues found" in result.stdout


def test_no_utf8_bom_in_project_files() -> None:
    names = [".gitignore", "README.md", "config.yaml", "data/vehicles.csv"]
    files = [*ROOT.rglob("*.py"), *[ROOT / name for name in names]]
    for path in files:
        if ".venv" in path.parts or not path.exists():
            continue
        assert not path.read_bytes().startswith(b"\xef\xbb\xbf"), path


def test_project_config_is_valid_for_both_yaml_parsers() -> None:
    from reliable_importer.config import load_config

    config = load_config(ROOT / "config.yaml", environ={})
    assert config.processing.rules.minimum_year == 1990
    assert config.input.path == ROOT / "data" / "vehicles.csv"
