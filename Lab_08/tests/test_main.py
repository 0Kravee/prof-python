"""Direct launch, a real server over the network, typing and hygiene."""

import os
import socket
import subprocess
import sys
import time
from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
MAIN = SRC / "car_catalog" / "main.py"


def launch(
    args: list[str], cwd: Path, **kwargs: object
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, *args],
        cwd=cwd,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
        **kwargs,  # type: ignore[call-overload]
    )


def test_direct_run_from_the_source_directory() -> None:
    """``python main.py`` must not need installation or a port."""
    result = launch(["main.py"], MAIN.parent)
    assert result.returncode == 0, result.stderr
    out = result.stdout
    assert "POST   /cars -> 201" in out
    assert "GET    /cars/999 -> 404" in out
    assert "X-Total-Count" in out
    assert "POST   /cars/batch -> 200" in out
    assert "POST   /cars/batch -> 504" in out
    assert "max requests in flight   : 5" in out
    assert "Demo finished" in out


def test_direct_run_from_any_directory(tmp_path: Path) -> None:
    result = launch([str(MAIN)], tmp_path)
    assert result.returncode == 0, result.stderr
    assert not list(tmp_path.iterdir())  # the demo leaves no files behind


def test_demo_uses_no_database_file() -> None:
    before = set((ROOT / "data").iterdir())
    assert launch([str(MAIN)], ROOT).returncode == 0
    assert set((ROOT / "data").iterdir()) == before


def test_module_launch() -> None:
    result = launch(
        ["-m", "car_catalog.main"],
        ROOT,
        env={**os.environ, "PYTHONPATH": str(SRC)},
    )
    assert result.returncode == 0, result.stderr


def test_missing_dependency_is_explained() -> None:
    code = (
        "import sys, runpy; sys.modules['fastapi'] = None; "
        f"runpy.run_path({str(MAIN)!r}, run_name='__main__')"
    )
    result = launch(["-c", code], ROOT)
    assert result.returncode == 1
    assert "Missing packages: fastapi" in result.stderr
    assert "pip install" in result.stderr and "Traceback" not in result.stderr


# ------------------------------------------------ a real server over the net
def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@pytest.fixture
def server(tmp_path: Path) -> Iterator[str]:
    port = free_port()
    env = {
        **os.environ,
        "CARS_DATABASE_URL": f"sqlite:///{tmp_path / 'cars.db'}",
        "CARS_BACKOFF_SECONDS": "0.01",
    }
    process = subprocess.Popen(
        [sys.executable, str(MAIN), "--serve", "--port", str(port)],
        cwd=tmp_path,
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    base = f"http://127.0.0.1:{port}"
    try:
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            if process.poll() is not None:
                pytest.fail("the server process exited early")
            try:
                if httpx.get(f"{base}/health", timeout=1).status_code == 200:
                    break
            except httpx.TransportError:
                time.sleep(0.2)
        else:
            pytest.fail("the server did not start in time")
        yield base
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()


def test_real_server_end_to_end(server: str) -> None:
    """Real sockets: CRUD, search and a batch that calls the server itself."""
    with httpx.Client(base_url=server, timeout=10) as client:
        for brand, model, price in (
            ("Toyota", "Camry", 21500),
            ("BMW", "X5", 48200),
            ("Audi", "A4", 23000),
        ):
            response = client.post(
                "/cars",
                json={
                    "brand": brand,
                    "model": model,
                    "year": 2020,
                    "price": price,
                    "mileage": 1000,
                },
            )
            assert response.status_code == 201
        listing = client.get(
            "/cars", params={"sort": "price", "order": "desc"}
        )
        assert [c["model"] for c in listing.json()] == ["X5", "A4", "Camry"]
        assert client.get("/cars/999").json()["code"] == "not_found"
        batch = client.post("/cars/batch", json={"ids": [1, 2, 3, 42]})
        assert batch.status_code == 200
        body = batch.json()
        assert [c["id"] for c in body["found"]] == [1, 2, 3]
        assert body["missing"] == [42] and body["failed"] == []
        assert client.get("/docs").status_code == 200
        assert "paths" in client.get("/openapi.json").json()


# ------------------------------------------------------------------ hygiene
def test_mypy_strict_passes() -> None:
    result = launch(["-m", "mypy"], ROOT)
    assert result.returncode == 0, result.stdout
    assert "Success: no issues found" in result.stdout


def test_requirements_match_pyproject() -> None:
    names = {
        line.split(">")[0].split("=")[0].strip().lower()
        for line in (ROOT / "requirements.txt").read_text().splitlines()
        if line.strip()
    }
    assert names == {"fastapi", "uvicorn", "sqlalchemy", "httpx", "pydantic"}
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    for name in names:
        assert f'"{name}' in pyproject


def test_no_utf8_bom_in_project_files() -> None:
    names = [".gitignore", "README.md", "requirements.txt", "pyproject.toml"]
    files = [*ROOT.rglob("*.py"), *[ROOT / name for name in names]]
    for path in files:
        if ".venv" in path.parts or not path.exists():
            continue
        assert not path.read_bytes().startswith(b"\xef\xbb\xbf"), path
