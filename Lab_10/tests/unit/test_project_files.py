"""Checks of the production files: packaging, secrets, Docker and CI."""

import json
import re
import tomllib
from pathlib import Path

import pytest
import yaml

import car_catalog
from car_catalog.api import create_app
from car_catalog.config import Settings

ROOT = Path(__file__).resolve().parents[2]
TEXT_SUFFIXES = {
    ".py", ".md", ".toml", ".yml", ".yaml", ".ini", ".txt", ".json",
    ".cfg", ".example", "",
}  # fmt: skip
SKIPPED_DIRS = {".git", ".venv", "__pycache__", "results", ".mypy_cache"}


def project_text_files() -> list[Path]:
    files = []
    for path in ROOT.rglob("*"):
        if not path.is_file() or SKIPPED_DIRS & set(path.parts):
            continue
        if path.name in {".env"} or path.suffix in {".db", ".png", ".docx"}:
            continue
        if path.suffix in TEXT_SUFFIXES or path.name in {
            "Dockerfile", ".dockerignore", ".gitignore", "LICENSE",
        }:  # fmt: skip
            files.append(path)
    return files


@pytest.fixture(scope="module")
def pyproject() -> dict:
    return tomllib.loads((ROOT / "pyproject.toml").read_text("utf-8"))


# --- packaging -----------------------------------------------------------


def test_version_is_defined_in_one_place(pyproject: dict) -> None:
    assert "version" in pyproject["project"]["dynamic"]
    assert pyproject["tool"]["setuptools"]["dynamic"]["version"] == {
        "attr": "car_catalog.__version__"
    }


def test_version_follows_semantic_versioning() -> None:
    assert re.fullmatch(r"\d+\.\d+\.\d+", car_catalog.__version__)


def test_changelog_describes_the_current_version() -> None:
    changelog = (ROOT / "CHANGELOG.md").read_text("utf-8")
    assert f"## [{car_catalog.__version__}]" in changelog


def test_package_metadata_is_complete(pyproject: dict) -> None:
    project = pyproject["project"]
    assert project["name"] == "car-catalog"
    for field in (
        "description", "readme", "requires-python", "license", "authors",
        "classifiers", "dependencies", "urls",
    ):  # fmt: skip
        assert project.get(field), field
    assert (ROOT / "LICENSE").exists()


def test_runtime_and_dev_dependencies_are_separated(pyproject: dict) -> None:
    runtime = " ".join(pyproject["project"]["dependencies"])
    for needed in ("fastapi", "uvicorn", "pydantic-settings", "sqlalchemy"):
        assert needed in runtime
    for tool in ("pytest", "ruff", "mypy", "build"):
        assert tool not in runtime
    dev = " ".join(pyproject["project"]["optional-dependencies"]["dev"])
    assert "ruff" in dev and "mypy" in dev


def test_console_scripts_point_to_existing_functions(pyproject: dict) -> None:
    import importlib

    for command, target in pyproject["project"]["scripts"].items():
        module_name, function = target.split(":")
        module = importlib.import_module(module_name)
        assert callable(getattr(module, function)), command


def test_package_is_typed() -> None:
    assert (ROOT / "src" / "car_catalog" / "py.typed").exists()


def test_src_layout_is_used(pyproject: dict) -> None:
    assert pyproject["tool"]["setuptools"]["packages"]["find"]["where"] == [
        "src"
    ]
    assert (ROOT / "src" / "car_catalog" / "__init__.py").exists()
    assert not (ROOT / "car_catalog").exists()


# --- secrets -----------------------------------------------------------------


def test_dotenv_is_ignored_but_the_example_is_not() -> None:
    patterns = (ROOT / ".gitignore").read_text("utf-8").splitlines()
    assert ".env" in patterns
    assert "!.env.example" in patterns


def test_dotenv_is_excluded_from_the_docker_context() -> None:
    patterns = (ROOT / ".dockerignore").read_text("utf-8").splitlines()
    assert ".env" in patterns


def test_env_example_lists_every_setting() -> None:
    example = (ROOT / ".env.example").read_text("utf-8")
    names = set(re.findall(r"^([A-Z_]+)=", example, flags=re.M))
    expected = {
        "DATABASE_URL", "APP_ENV", "LOG_LEVEL", "API_KEY", "HOST", "PORT",
        "AUTO_CREATE_TABLES",
    }  # fmt: skip
    assert expected <= names


def test_env_example_contains_no_real_secret() -> None:
    example = (ROOT / ".env.example").read_text("utf-8")
    assert re.search(r"^API_KEY=$", example, flags=re.M)  # empty


def test_env_example_loads_as_valid_settings() -> None:
    settings = Settings(_env_file=ROOT / ".env.example")  # type: ignore[call-arg]
    assert settings.app_env == "development"
    assert settings.api_key is None


SECRET_PATTERNS = {
    "private key": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    "GitHub token": re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}\b"),
    "AWS key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "URL with password": re.compile(
        r"://[^/\s:@'\"]+:(?!\*{3}|password|pass\b|user\b|\$|\{)[^/\s@'\"]{4,}@"
    ),
    "assigned secret": re.compile(
        r"""(?ix)\b(api[_-]?key|secret|token|passwd|password)\b
            \s*[:=]\s*["'][A-Za-z0-9_\-]{12,}["']"""
    ),
}  # fmt: skip

# files that deliberately contain fake values used by the tests
FAKE_SECRET_FILES = {
    "test_settings.py", "test_api.py", "conftest.py", "test_project_files.py",
    "test_config_validation.py",
}  # fmt: skip


@pytest.mark.parametrize("name", sorted(SECRET_PATTERNS))
def test_no_secrets_in_tracked_files(name: str) -> None:
    pattern = SECRET_PATTERNS[name]
    found = []
    for path in project_text_files():
        if path.name in FAKE_SECRET_FILES:
            continue
        text = path.read_text("utf-8", errors="ignore")
        for match in pattern.finditer(text):
            found.append(f"{path.relative_to(ROOT)}: {match.group(0)[:40]}")
    assert not found, found


def test_the_secret_scanner_really_detects_secrets() -> None:
    fake_header = (
        "-----BEGIN " + "RSA PRIVATE KEY-----"
    )  # split: no scanner hit
    assert SECRET_PATTERNS["private key"].search(fake_header)
    assert SECRET_PATTERNS["URL with password"].search(
        "postgresql://admin:Sup3rSecret@db:5432/x"
    )
    assert SECRET_PATTERNS["assigned secret"].search(
        'API_KEY = "abcdef1234567890"'
    )
    assert not SECRET_PATTERNS["URL with password"].search(
        "postgresql://user:***@db/cars"
    )


# --- Docker -


@pytest.fixture(scope="module")
def dockerfile() -> str:
    return (ROOT / "Dockerfile").read_text("utf-8")


def test_dockerfile_is_multi_stage(dockerfile: str) -> None:
    assert len(re.findall(r"^FROM ", dockerfile, flags=re.M)) == 2
    assert " AS builder" in dockerfile and " AS runtime" in dockerfile


def test_container_does_not_run_as_root(dockerfile: str) -> None:
    users = re.findall(r"^USER (\S+)", dockerfile, flags=re.M)
    assert users and users[-1] not in {"root", "0"}


def test_dockerfile_has_a_healthcheck_for_the_health_endpoint(
    dockerfile: str,
) -> None:
    assert "HEALTHCHECK" in dockerfile
    assert "/health" in dockerfile


def test_dockerfile_uses_a_volume_and_runs_migrations(
    dockerfile: str,
) -> None:
    assert re.search(r"^VOLUME \[\"/data\"\]", dockerfile, flags=re.M)
    assert "alembic upgrade head" in dockerfile


def test_dockerfile_contains_no_secret_values(dockerfile: str) -> None:
    instructions = [
        line
        for line in dockerfile.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    assert not [line for line in instructions if "API_KEY" in line.upper()]
    assert not re.search(
        r"(PASSWORD|TOKEN|SECRET)\s*=", dockerfile, flags=re.I
    )


def test_dockerfile_uses_environment_variables_from_the_settings(
    dockerfile: str,
) -> None:
    for name in ("DATABASE_URL", "APP_ENV", "LOG_LEVEL"):
        assert name in dockerfile


def test_compose_file_is_valid_and_has_a_volume() -> None:
    compose = yaml.safe_load((ROOT / "docker-compose.yml").read_text("utf-8"))
    service = compose["services"]["api"]
    assert service["volumes"] == ["car-data:/data"]
    assert "car-data" in compose["volumes"]
    assert "API_KEY" in service["environment"]
    assert "secret" not in json.dumps(compose).lower()


# --- CI -


@pytest.fixture(scope="module")
def workflow() -> dict:
    return yaml.safe_load(
        (ROOT / ".github" / "workflows" / "ci.yml").read_text("utf-8")
    )


def workflow_text() -> str:
    return (ROOT / ".github" / "workflows" / "ci.yml").read_text("utf-8")


def test_workflow_has_the_required_jobs(workflow: dict) -> None:
    assert {"lint", "typecheck", "test", "build", "docker"} <= set(
        workflow["jobs"]
    )


def test_workflow_runs_every_required_tool() -> None:
    text = workflow_text()
    for command in (
        "ruff check .",
        "ruff format --check .",
        "mypy",
        "pytest",
        "python -m build",
        "twine check",
        "docker/build-push-action",
    ):
        assert command in text, command


def test_workflow_tests_several_python_versions(workflow: dict) -> None:
    matrix = workflow["jobs"]["test"]["strategy"]["matrix"]
    assert {"3.11", "3.12"} <= set(matrix["python-version"])


def test_workflow_has_a_coverage_threshold() -> None:
    assert "--cov-fail-under=80" in workflow_text()


def test_build_and_docker_wait_for_the_quality_jobs(workflow: dict) -> None:
    for job in ("build", "docker"):
        assert {"lint", "typecheck", "test"} <= set(
            workflow["jobs"][job]["needs"]
        )


def test_workflow_uses_no_hard_coded_secret() -> None:
    text = workflow_text()
    assert "ghp_" not in text
    assert "${{ secrets." in text  # secrets only through GitHub Secrets


def test_workflow_has_least_privilege_permissions(workflow: dict) -> None:
    assert workflow["permissions"] == {"contents": "read"}


def test_pre_commit_config_is_valid() -> None:
    config = yaml.safe_load(
        (ROOT / ".pre-commit-config.yaml").read_text("utf-8")
    )
    hooks = {hook["id"] for repo in config["repos"] for hook in repo["hooks"]}
    assert {"ruff-check", "ruff-format", "detect-private-key"} <= hooks


# --- documentation -


def test_exported_openapi_schema_is_up_to_date() -> None:
    """Run `python scripts/export_openapi.py` after changing the API."""
    stored = json.loads((ROOT / "docs" / "openapi.json").read_text("utf-8"))
    settings = Settings(_env_file=None, database_url="sqlite://")  # type: ignore[call-arg]
    current = json.loads(json.dumps(create_app(settings).openapi()))
    assert stored == current


@pytest.mark.parametrize(
    "endpoint",
    [
        "/cars",
        "/manufacturers",
        "/manufacturers/{id}/cars",
        "GET /health",
        "DATABASE_URL",
        "APP_ENV",
        "LOG_LEVEL",
        "docker build",
        "docker run",
        "ruff check",
        "python -m build",
    ],
)
def test_readme_documents_the_important_things(endpoint: str) -> None:
    assert endpoint in (ROOT / "README.md").read_text("utf-8")
