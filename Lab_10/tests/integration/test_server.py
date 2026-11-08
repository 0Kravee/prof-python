"""Integration tests of the server command (car-catalog-api)."""

import pytest

from car_catalog import __version__, server

pytestmark = pytest.mark.integration


@pytest.mark.parametrize("flag", ["--version", "-V"])
def test_version_flag_prints_the_version(
    flag: str, capsys: pytest.CaptureFixture[str]
) -> None:
    assert server.main([flag]) == 0
    assert capsys.readouterr().out.strip() == f"car-catalog {__version__}"


def test_server_starts_uvicorn_with_the_settings_from_the_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[tuple[object, ...], dict[str, object]]] = []
    monkeypatch.setattr(
        server.uvicorn, "run", lambda *a, **k: calls.append((a, k))
    )
    monkeypatch.setenv("HOST", "0.0.0.0")
    monkeypatch.setenv("PORT", "9001")
    assert server.main([]) == 0
    ((args, kwargs),) = calls
    assert args == ("car_catalog.api:create_app",)
    assert kwargs["factory"] is True
    assert (kwargs["host"], kwargs["port"]) == ("0.0.0.0", 9001)
    assert kwargs["log_config"] is None


def test_module_can_be_run_as_a_script(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    import runpy
    import sys

    monkeypatch.setattr(sys, "argv", ["car-catalog-api", "--version"])
    monkeypatch.delitem(sys.modules, "car_catalog.server")
    with pytest.raises(SystemExit) as excinfo:
        runpy.run_module("car_catalog.server", run_name="__main__")
    assert excinfo.value.code == 0
    assert capsys.readouterr().out.strip() == f"car-catalog {__version__}"
