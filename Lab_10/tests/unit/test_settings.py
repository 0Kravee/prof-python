"""Unit tests of the environment based configuration."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from car_catalog.config import LOG_LEVELS, Settings


def make(**values: object) -> Settings:
    """Settings without the developer's own .env file."""
    return Settings(_env_file=None, **values)  # type: ignore[arg-type]


def test_defaults_are_safe_for_development() -> None:
    settings = make()
    assert settings.app_env == "development"
    assert settings.log_level == "INFO"
    assert settings.database_url == "sqlite:///./cars.db"
    assert settings.api_key is None
    assert settings.host == "127.0.0.1"  # not open to the network
    assert settings.port == 8000
    assert settings.auto_create_tables is False
    assert settings.is_production is False


def test_values_are_read_from_environment_variables(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DATABASE_URL", "sqlite:////data/cars.db")
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("LOG_LEVEL", "WARNING")
    monkeypatch.setenv("PORT", "9000")
    monkeypatch.setenv("HOST", "0.0.0.0")
    monkeypatch.setenv("AUTO_CREATE_TABLES", "true")
    settings = make()
    assert settings.database_url == "sqlite:////data/cars.db"
    assert settings.is_production
    assert settings.log_level == "WARNING"
    assert (settings.host, settings.port) == ("0.0.0.0", 9000)
    assert settings.auto_create_tables is True


def test_environment_is_an_alias_of_app_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ENVIRONMENT", "test")
    assert make().app_env == "test"


def test_app_env_wins_over_its_alias(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("ENVIRONMENT", "test")
    assert make().app_env == "production"


def test_legacy_database_variable_from_earlier_labs_still_works(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CAR_CATALOG_DATABASE_URL", "sqlite:///legacy.db")
    assert make().database_url == "sqlite:///legacy.db"


def test_values_can_be_passed_by_field_name() -> None:
    settings = make(database_url="sqlite:///x.db", app_env="test", port=8080)
    assert (settings.database_url, settings.app_env) == (
        "sqlite:///x.db",
        "test",
    )
    assert settings.port == 8080


@pytest.mark.parametrize("raw", ["production", "PRODUCTION", " Production "])
def test_environment_name_is_normalized(raw: str) -> None:
    assert make(app_env=raw).app_env == "production"


@pytest.mark.parametrize("raw", ["staging", "", "prod"])
def test_unknown_environment_is_rejected(raw: str) -> None:
    with pytest.raises(ValidationError):
        make(app_env=raw)


@pytest.mark.parametrize("level", LOG_LEVELS)
def test_all_standard_log_levels_are_accepted(level: str) -> None:
    assert make(log_level=level.lower()).log_level == level


@pytest.mark.parametrize("level", ["verbose", "", "TRACE"])
def test_unknown_log_level_is_rejected(level: str) -> None:
    with pytest.raises(ValidationError, match="LOG_LEVEL"):
        make(log_level=level)


@pytest.mark.parametrize("port", [0, 70000, -1])
def test_port_must_be_a_valid_number(port: int) -> None:
    with pytest.raises(ValidationError):
        make(port=port)


def test_port_text_from_environment_must_be_numeric(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PORT", "eight")
    with pytest.raises(ValidationError):
        make()


def test_invalid_database_url_is_rejected() -> None:
    with pytest.raises(ValidationError, match="DATABASE_URL"):
        make(database_url="this is not a url")


# --- secrets ---------------------------------------------------------------


def test_api_key_is_a_secret_and_is_hidden_in_repr_and_str() -> None:
    settings = make(api_key="super-secret-value")
    assert "super-secret-value" not in repr(settings)
    assert "super-secret-value" not in str(settings)
    assert settings.api_key is not None
    assert settings.api_key.get_secret_value() == "super-secret-value"


def test_summary_never_contains_the_key_or_the_password() -> None:
    settings = make(
        api_key="super-secret-value",
        database_url="postgresql://user:db-password@db:5432/cars",
    )
    summary = str(settings.summary())
    assert "super-secret-value" not in summary
    assert "db-password" not in summary
    assert settings.summary()["api_key_set"] is True


def test_database_password_is_hidden_in_repr_and_safe_url() -> None:
    settings = make(database_url="postgresql://user:db-password@db/cars")
    assert "db-password" not in repr(settings)
    assert settings.safe_database_url == "postgresql://user:***@db/cars"
    # the real URL is still available for the engine
    assert "db-password" in settings.database_url


def test_url_without_password_is_unchanged() -> None:
    assert make().safe_database_url == "sqlite:///./cars.db"


@pytest.mark.parametrize("value", ["", "   "])
def test_empty_api_key_means_no_key(value: str) -> None:
    assert make(api_key=value).api_key is None


def test_empty_api_key_variable_in_the_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("API_KEY", "")  # as in .env.example
    assert make().api_key is None


# --- .env file ---------------------------------------------------------------


def test_values_are_read_from_a_dotenv_file(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "APP_ENV=production\nLOG_LEVEL=error\nPORT=8123\n", encoding="utf-8"
    )
    settings = Settings(_env_file=env_file)  # type: ignore[call-arg]
    assert settings.app_env == "production"
    assert settings.log_level == "ERROR"
    assert settings.port == 8123


def test_real_environment_wins_over_the_dotenv_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("LOG_LEVEL=ERROR\n", encoding="utf-8")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    assert Settings(_env_file=env_file).log_level == "DEBUG"  # type: ignore[call-arg]


def test_unknown_variables_in_dotenv_are_ignored(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("SOMETHING_ELSE=1\n", encoding="utf-8")
    assert Settings(_env_file=env_file).app_env == "development"  # type: ignore[call-arg]
