"""YAML loading: PyYAML when installed, a small safe fallback otherwise.

The fallback understands only the simple subset used by ``config.yaml``
(nested mappings, scalars and comments). It exists so that the program can
be started directly, even before the dependencies are installed.
"""

import importlib
import re
from types import ModuleType

from reliable_importer.exceptions import ConfigurationError

_INTEGER = re.compile(r"^[+-]?\d+$")
_FLOAT = re.compile(r"^[+-]?(\d+\.\d*|\.\d+|\d+)([eE][+-]?\d+)?$")


def load_pyyaml() -> ModuleType | None:
    """Return the PyYAML module or None when it is not installed."""
    try:
        return importlib.import_module("yaml")
    except ImportError:
        return None


def load_yaml_text(text: str) -> object:
    """Parse YAML text safely (``yaml.safe_load`` or the fallback parser)."""
    yaml_module = load_pyyaml()
    if yaml_module is None:
        return parse_simple_yaml(text)
    try:
        result: object = yaml_module.safe_load(text)
    except yaml_module.YAMLError as error:
        raise ConfigurationError("Invalid YAML configuration") from error
    return result


def _strip_comment(line: str) -> str:
    quote: str | None = None
    for index, char in enumerate(line):
        if quote:
            if char == quote:
                quote = None
        elif char in "'\"":
            quote = char
        elif char == "#" and (index == 0 or line[index - 1].isspace()):
            return line[:index]
    return line


def _parse_scalar(text: str) -> object:
    if len(text) >= 2 and text[0] == text[-1] and text[0] in "'\"":
        return text[1:-1]
    if text[0] in "[{":
        raise ConfigurationError(
            "Flow collections are not supported by the fallback YAML parser"
        )
    lowered = text.lower()
    if lowered in ("true", "false"):
        return lowered == "true"
    if lowered in ("null", "~"):
        return None
    if _INTEGER.match(text):
        return int(text)
    if _FLOAT.match(text):
        return float(text)
    return text


def _tokenize(text: str) -> list[tuple[int, int, str, str]]:
    """Split text into (line number, indent, key, raw value) entries."""
    entries: list[tuple[int, int, str, str]] = []
    for number, raw_line in enumerate(text.splitlines(), start=1):
        line = _strip_comment(raw_line).rstrip()
        if not line.strip():
            continue
        stripped = line.lstrip(" ")
        indent = len(line) - len(stripped)
        if stripped.startswith("\t"):
            raise ConfigurationError(f"Invalid YAML: tab at line {number}")
        if stripped.startswith("- "):
            raise ConfigurationError(
                f"Lists are not supported by the fallback parser "
                f"(line {number})"
            )
        key, separator, rest = stripped.partition(":")
        if not separator or not key.strip():
            raise ConfigurationError(f"Invalid YAML at line {number}")
        entries.append((number, indent, key.strip(), rest.strip()))
    return entries


def _parse_block(
    entries: list[tuple[int, int, str, str]], position: int, indent: int
) -> tuple[dict[str, object], int]:
    mapping: dict[str, object] = {}
    while position < len(entries):
        number, line_indent, key, value_text = entries[position]
        if line_indent < indent:
            break
        if line_indent > indent:
            raise ConfigurationError(f"Invalid indentation at line {number}")
        if key in mapping:
            raise ConfigurationError(f"Duplicate key {key!r} at line {number}")
        position += 1
        if value_text:
            mapping[key] = _parse_scalar(value_text)
        elif position < len(entries) and entries[position][1] > indent:
            child, position = _parse_block(
                entries, position, entries[position][1]
            )
            mapping[key] = child
        else:
            mapping[key] = None
    return mapping, position


def parse_simple_yaml(text: str) -> object:
    """Parse nested ``key: value`` mappings (a safe YAML subset)."""
    entries = _tokenize(text)
    if not entries:
        return None
    mapping, position = _parse_block(entries, 0, entries[0][1])
    if position < len(entries):
        raise ConfigurationError(
            f"Invalid indentation at line {entries[position][0]}"
        )
    return mapping
