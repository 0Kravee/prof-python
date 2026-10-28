"""Configuration loading, validation, YAML parsers and env overrides."""

from pathlib import Path

import pytest

from conftest import make_config
from reliable_importer import yaml_loader
from reliable_importer.config import (
    apply_env_overrides,
    load_config,
    validate_config,
)
from reliable_importer.exceptions import ConfigurationError
from reliable_importer.yaml_loader import load_yaml_text, parse_simple_yaml


@pytest.fixture
def folder(tmp_path: Path, csv_file: Path) -> Path:
    return tmp_path


def test_valid_config_resolves_paths_relative_to_the_file(
    folder: Path,
) -> None:
    config = load_config(make_config(folder), environ={})
    assert config.input.path == folder / "vehicles.csv"
    assert config.output.path == folder / "out" / "result.json"
    assert config.output.errors_path == folder / "errors.csv"
    assert config.processing.skip_invalid is True
    assert config.processing.rules.maximum_price == 200000.0
    assert config.logging.level == "INFO" and config.logging.backup_count == 3


def test_missing_file(tmp_path: Path) -> None:
    with pytest.raises(ConfigurationError, match="not found") as info:
        load_config(tmp_path / "nope.yaml", environ={})
    assert isinstance(info.value.__cause__, FileNotFoundError)


def test_invalid_yaml_keeps_the_cause(tmp_path: Path) -> None:
    path = tmp_path / "bad.yaml"
    path.write_text("input: [unclosed\n", encoding="utf-8")
    with pytest.raises(ConfigurationError, match="Invalid YAML") as info:
        load_config(path, environ={})
    assert info.value.__cause__ is not None


def test_root_must_be_a_mapping(tmp_path: Path) -> None:
    path = tmp_path / "list.yaml"
    path.write_text("- a\n- b\n", encoding="utf-8")
    with pytest.raises(ConfigurationError, match="mapping"):
        load_config(path, environ={})


def test_unreadable_encoding(tmp_path: Path) -> None:
    path = tmp_path / "latin.yaml"
    path.write_bytes(b"input: \xff\xfe\n")
    with pytest.raises(ConfigurationError, match="Cannot read"):
        load_config(path, environ={})


@pytest.mark.parametrize(
    ("old", "new", "message"),
    [
        (
            "  path: vehicles.csv\n",
            "  format: csv\n",
            "Missing configuration key: input.path",
        ),
        ("maximum_year: 2026", "maximum_year: 3000", "Years must be between"),
        ("maximum_year: 2026", "maximum_year: 1980", "must not exceed"),
        ("minimum_price: 0", "minimum_price: -5", "must not be negative"),
        ("maximum_price: 200000", "maximum_price: -1", "must not exceed"),
        ("maximum_year: 2026", "maximum_year: abc", "must be an integer"),
        ("maximum_year: 2026", "maximum_year: true", "must be an integer"),
        ("skip_invalid: true", "skip_invalid: maybe", "true or false"),
        ("level: INFO", "level: LOUD", "Unknown logging level"),
        ("path: vehicles.csv", "path: missing.csv", "Input file not found"),
        (
            "schema_version: 1",
            "schema_version: 2",
            "Unsupported schema_version",
        ),
        ("path: app.log", "path: ''", "non-empty string"),
    ],
)
def test_invalid_values(
    folder: Path, old: str, new: str, message: str
) -> None:
    path = make_config(folder)
    text = path.read_text(encoding="utf-8")
    assert old in text
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    with pytest.raises(ConfigurationError, match=message):
        load_config(path, environ={})


def test_missing_sections(folder: Path) -> None:
    path = make_config(folder)
    text = path.read_text(encoding="utf-8")
    path.write_text(text.replace("input:\n  path: vehicles.csv\n", ""))
    with pytest.raises(ConfigurationError, match="section: input"):
        load_config(path, environ={})


def test_output_path_must_not_be_a_directory(folder: Path) -> None:
    (folder / "out").mkdir()
    path = make_config(folder, output_name="out")
    with pytest.raises(ConfigurationError, match="is a directory"):
        load_config(path, environ={})


def test_environment_overrides(folder: Path) -> None:
    path = make_config(folder, skip=True)
    environ = {
        "IMPORTER_SKIP_INVALID": "no",
        "IMPORTER_LOG_LEVEL": "debug",
        "IMPORTER_OUTPUT_PATH": "elsewhere.json",
    }
    config = load_config(path, environ=environ)
    assert config.processing.skip_invalid is False
    assert config.logging.level == "DEBUG"
    assert config.output.path == folder / "elsewhere.json"


def test_environment_override_validation(folder: Path) -> None:
    path = make_config(folder)
    with pytest.raises(ConfigurationError, match="boolean"):
        load_config(path, environ={"IMPORTER_SKIP_INVALID": "perhaps"})


def test_overrides_do_not_mutate_the_input() -> None:
    raw: dict[str, object] = {"processing": {"skip_invalid": True}}
    result = apply_env_overrides(raw, {"IMPORTER_SKIP_INVALID": "0"})
    assert raw == {"processing": {"skip_invalid": True}}
    assert result == {"processing": {"skip_invalid": False}}


def test_validate_config_can_be_called_directly(folder: Path) -> None:
    validate_config(load_config(make_config(folder), environ={}))


# ------------------------------------------------------------ YAML parsers
def test_fallback_parser_matches_pyyaml_on_the_project_config() -> None:
    root = Path(__file__).resolve().parents[1]
    text = (root / "config.yaml").read_text(encoding="utf-8")
    pyyaml = yaml_loader.load_pyyaml()
    assert pyyaml is not None
    assert parse_simple_yaml(text) == pyyaml.safe_load(text)


def test_loader_uses_the_fallback_when_pyyaml_is_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(yaml_loader, "load_pyyaml", lambda: None)
    assert load_yaml_text("a:\n  b: 1\n  c: x # comment\n") == {
        "a": {"b": 1, "c": "x"}
    }


@pytest.mark.parametrize(
    "text",
    [
        "input:\n  path: x\n bad: 1",
        "a: 1\n  b: 2",
        "just text",
        "x: [1, 2]",
        "a:\n\tb: 1",
        "k: 1\nk: 2",
        "- item",
    ],
)
def test_fallback_parser_rejects_bad_yaml(text: str) -> None:
    with pytest.raises(ConfigurationError):
        parse_simple_yaml(text)


def test_fallback_scalars() -> None:
    parsed = parse_simple_yaml(
        "i: 5\nf: 2.5\nb: true\nn: null\ne:\ns: 'x # y'\nt: plain text\n"
    )
    assert parsed == {
        "i": 5,
        "f": 2.5,
        "b": True,
        "n": None,
        "e": None,
        "s": "x # y",
        "t": "plain text",
    }
    assert parse_simple_yaml("# only a comment\n") is None
