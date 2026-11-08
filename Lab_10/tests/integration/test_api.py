"""Integration tests of the REST API (FastAPI + SQLite in a temp file)."""

import logging
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from car_catalog import __version__
from car_catalog.api import create_app
from car_catalog.config import Settings

pytestmark = pytest.mark.integration

CAR = {
    "model": "Octavia",
    "year": 2020,
    "price": 17000.0,
    "mileage": 30000,
}


def new_manufacturer(client: TestClient, name: str = "Skoda") -> int:
    response = client.post(
        "/manufacturers", json={"name": name, "country": "Czechia"}
    )
    assert response.status_code == 201
    return int(response.json()["id"])


# --- health -----------------------------------------------------------------


def test_health_returns_200_and_status_ok(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["database"] == "ok"
    assert body["version"] == __version__
    assert body["environment"] == "test"


def test_health_reports_a_missing_database_schema(
    tmp_path: Path,
) -> None:
    """Not migrated database: the container must not look healthy."""
    settings = Settings(
        _env_file=None,  # type: ignore[call-arg]
        database_url=f"sqlite:///{tmp_path / 'empty.db'}",
        app_env="test",
        auto_create_tables=False,
    )
    with TestClient(create_app(settings)) as bare:
        response = bare.get("/health")
    assert response.status_code == 503
    assert response.json()["status"] == "error"
    assert response.json()["database"] == "unavailable"


def test_health_needs_no_api_key(secured_client: TestClient) -> None:
    assert secured_client.get("/health").status_code == 200


def test_health_does_not_expose_secrets(
    secured_client: TestClient, api_key: str
) -> None:
    assert api_key not in secured_client.get("/health").text


# --- documentation -


def test_swagger_and_openapi_are_available(client: TestClient) -> None:
    docs = client.get("/docs")
    assert docs.status_code == 200
    assert "swagger" in docs.text.lower()
    schema = client.get("/openapi.json").json()
    assert schema["info"]["title"] == "Car Catalog API"
    assert schema["info"]["version"] == __version__
    for path in (
        "/health",
        "/cars",
        "/manufacturers",
        "/manufacturers/{manufacturer_id}/cars",
    ):
        assert path in schema["paths"]


# --- manufacturers -


def test_manufacturer_lifecycle(client: TestClient) -> None:
    assert client.get("/manufacturers").json() == []
    manufacturer_id = new_manufacturer(client)
    fetched = client.get(f"/manufacturers/{manufacturer_id}")
    assert fetched.status_code == 200
    assert fetched.json() == {
        "id": manufacturer_id,
        "name": "Skoda",
        "country": "Czechia",
    }
    assert [m["name"] for m in client.get("/manufacturers").json()] == [
        "Skoda"
    ]


def test_manufacturers_are_sorted_by_name(client: TestClient) -> None:
    for name in ("Toyota", "Audi", "BMW"):
        new_manufacturer(client, name)
    names = [m["name"] for m in client.get("/manufacturers").json()]
    assert names == ["Audi", "BMW", "Toyota"]


def test_missing_manufacturer_gives_404(client: TestClient) -> None:
    response = client.get("/manufacturers/999")
    assert response.status_code == 404
    assert "999" in response.json()["detail"]


def test_duplicate_manufacturer_gives_409(client: TestClient) -> None:
    new_manufacturer(client, "BMW")
    response = client.post("/manufacturers", json={"name": "bmw"})
    assert response.status_code == 409


@pytest.mark.parametrize("body", [{}, {"name": ""}, {"name": "x" * 101}])
def test_invalid_manufacturer_gives_422(client: TestClient, body) -> None:
    assert client.post("/manufacturers", json=body).status_code == 422


def test_manufacturer_cars_endpoint(
    client: TestClient, api_data: dict[str, int]
) -> None:
    response = client.get(f"/manufacturers/{api_data['BMW']}/cars")
    assert response.status_code == 200
    assert [c["model"] for c in response.json()] == ["X5", "3 Series"]
    assert {c["manufacturer"] for c in response.json()} == {"BMW"}


def test_cars_of_a_manufacturer_without_cars(client: TestClient) -> None:
    manufacturer_id = new_manufacturer(client)
    response = client.get(f"/manufacturers/{manufacturer_id}/cars")
    assert response.status_code == 200
    assert response.json() == []


def test_cars_of_a_missing_manufacturer_give_404(client: TestClient) -> None:
    assert client.get("/manufacturers/42/cars").status_code == 404


# --- cars: CRUD -


def test_car_lifecycle(client: TestClient) -> None:
    manufacturer_id = new_manufacturer(client)
    created = client.post(
        "/cars", json={"manufacturer_id": manufacturer_id, **CAR}
    )
    assert created.status_code == 201
    car = created.json()
    assert car["manufacturer"] == "Skoda"
    assert car["vin"] is None

    fetched = client.get(f"/cars/{car['id']}")
    assert fetched.status_code == 200
    assert fetched.json() == car

    patched = client.patch(
        f"/cars/{car['id']}", json={"price": 16500.5, "mileage": 31000}
    )
    assert patched.status_code == 200
    assert patched.json()["price"] == 16500.5
    assert patched.json()["mileage"] == 31000

    assert client.delete(f"/cars/{car['id']}").status_code == 204
    assert client.get(f"/cars/{car['id']}").status_code == 404


def test_patch_without_fields_changes_nothing(client: TestClient) -> None:
    manufacturer_id = new_manufacturer(client)
    car = client.post(
        "/cars", json={"manufacturer_id": manufacturer_id, **CAR}
    ).json()
    response = client.patch(f"/cars/{car['id']}", json={})
    assert response.status_code == 200
    assert response.json() == car


def test_delete_twice_gives_404_the_second_time(client: TestClient) -> None:
    manufacturer_id = new_manufacturer(client)
    car = client.post(
        "/cars", json={"manufacturer_id": manufacturer_id, **CAR}
    ).json()
    assert client.delete(f"/cars/{car['id']}").status_code == 204
    assert client.delete(f"/cars/{car['id']}").status_code == 404


def test_car_for_missing_manufacturer_gives_404(client: TestClient) -> None:
    response = client.post("/cars", json={"manufacturer_id": 77, **CAR})
    assert response.status_code == 404


@pytest.mark.parametrize(
    "changes",
    [
        {"year": 1500},
        {"year": 2200},
        {"price": -1},
        {"mileage": -5},
        {"model": ""},
        {"year": "twenty"},
        {"price": "cheap"},
    ],
)
def test_invalid_car_data_gives_422(client: TestClient, changes) -> None:
    manufacturer_id = new_manufacturer(client)
    body = {"manufacturer_id": manufacturer_id, **CAR, **changes}
    assert client.post("/cars", json=body).status_code == 422


def test_domain_validation_also_gives_422(client: TestClient) -> None:
    manufacturer_id = new_manufacturer(client)
    body = {"manufacturer_id": manufacturer_id, **CAR, "vin": "SHORT"}
    response = client.post("/cars", json=body)
    assert response.status_code == 422
    assert "VIN" in response.json()["detail"]


def test_duplicate_vin_gives_409(client: TestClient) -> None:
    manufacturer_id = new_manufacturer(client)
    body = {
        "manufacturer_id": manufacturer_id,
        **CAR,
        "vin": "5UXKR0C58J0000003",
    }
    assert client.post("/cars", json=body).status_code == 201
    assert client.post("/cars", json=body).status_code == 409


def test_negative_price_in_patch_gives_422(client: TestClient) -> None:
    manufacturer_id = new_manufacturer(client)
    car = client.post(
        "/cars", json={"manufacturer_id": manufacturer_id, **CAR}
    ).json()
    assert (
        client.patch(f"/cars/{car['id']}", json={"price": -1}).status_code
        == 422
    )
    assert client.get(f"/cars/{car['id']}").json()["price"] == CAR["price"]


def test_patch_missing_car_gives_404(client: TestClient) -> None:
    assert client.patch("/cars/123", json={"price": 1}).status_code == 404


def test_car_id_must_be_a_number(client: TestClient) -> None:
    assert client.get("/cars/abc").status_code == 422


# --- cars: search, filters, sorting, pagination -


def models(response) -> list[str]:
    assert response.status_code == 200
    return [car["model"] for car in response.json()]


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("brand=toyota", ["Corolla", "Camry"]),
        ("brand=BMW&model=x5", ["X5"]),
        ("model=a4", ["A4"]),
        ("year=2021", ["X5"]),
        ("min_year=2020", ["Corolla", "X5", "3 Series"]),
        ("max_year=2019", ["Camry", "A4"]),
        ("min_price=30000", ["X5", "3 Series"]),
        ("max_price=20000", ["Corolla"]),
        ("max_mileage=18000", ["Corolla", "X5"]),
        ("brand=audi&min_year=2022", []),
        ("brand=Tesla", []),
    ],
)
def test_search_and_filters(
    client: TestClient, api_data, query: str, expected: list[str]
) -> None:
    assert models(client.get(f"/cars?{query}")) == expected


def test_sorting_by_price(client: TestClient, api_data) -> None:
    cheap_first = models(client.get("/cars?sort_by=price"))
    assert cheap_first[0] == "Corolla"
    dear_first = models(client.get("/cars?sort_by=price&descending=true"))
    assert dear_first[0] == "X5"


def test_pagination(client: TestClient, api_data) -> None:
    first = models(client.get("/cars?sort_by=price&limit=2"))
    second = models(client.get("/cars?sort_by=price&limit=2&offset=2"))
    assert len(first) == 2 and len(second) == 2
    assert not set(first) & set(second)
    assert models(client.get("/cars?offset=100")) == []


@pytest.mark.parametrize(
    "query",
    ["limit=0", "limit=1001", "offset=-1", "min_price=-5", "sort_by=color"],
)
def test_bad_query_parameters_give_422(
    client: TestClient, api_data, query: str
) -> None:
    assert client.get(f"/cars?{query}").status_code == 422


def test_empty_catalog_lists_nothing(client: TestClient) -> None:
    assert client.get("/cars").json() == []


# --- the Lab_01 operations -


def test_most_expensive_car(client: TestClient, api_data) -> None:
    car = client.get("/cars/most-expensive").json()
    assert (car["manufacturer"], car["model"]) == ("BMW", "X5")


def test_lowest_mileage_car(client: TestClient, api_data) -> None:
    assert client.get("/cars/lowest-mileage").json()["model"] == "Corolla"


def test_average_price(client: TestClient, api_data) -> None:
    body = client.get("/cars/average-price").json()
    assert body["count"] == 5
    assert body["average_price"] == pytest.approx(28700.0)


def test_empty_catalog_has_no_most_expensive_car(client: TestClient) -> None:
    assert client.get("/cars/most-expensive").status_code == 404
    assert client.get("/cars/lowest-mileage").status_code == 404
    assert client.get("/cars/average-price").json() == {
        "count": 0,
        "average_price": 0.0,
    }


def test_statistics(client: TestClient, api_data) -> None:
    body = client.get("/statistics").json()
    assert body["count"] == 5
    assert body["min_price"] == 19800.0
    assert body["max_price"] == 48200.0
    by_name = {m["manufacturer"]: m for m in body["manufacturers"]}
    assert by_name["BMW"]["cars"] == 2
    assert by_name["Toyota"]["average_price"] == pytest.approx(20650.0)


# --- API key (secret) -


def test_reading_needs_no_key(secured_client: TestClient) -> None:
    assert secured_client.get("/cars").status_code == 200
    assert secured_client.get("/manufacturers").status_code == 200


@pytest.mark.parametrize(
    ("method", "url", "body"),
    [
        ("post", "/manufacturers", {"name": "Kia"}),
        ("post", "/cars", {"manufacturer_id": 1, **CAR}),
        ("patch", "/cars/1", {"price": 1}),
        ("delete", "/cars/1", None),
    ],
)
def test_changing_requests_without_key_give_401(
    secured_client: TestClient, method: str, url: str, body
) -> None:
    response = getattr(secured_client, method)(
        url, **({"json": body} if body else {})
    )
    assert response.status_code == 401


def test_wrong_key_gives_401(secured_client: TestClient) -> None:
    response = secured_client.post(
        "/manufacturers", json={"name": "Kia"}, headers={"X-API-Key": "wrong"}
    )
    assert response.status_code == 401
    assert "wrong" not in response.text


def test_correct_key_allows_changes(
    secured_client: TestClient, api_key: str
) -> None:
    headers = {"X-API-Key": api_key}
    created = secured_client.post(
        "/manufacturers", json={"name": "Kia"}, headers=headers
    )
    assert created.status_code == 201
    car = secured_client.post(
        "/cars",
        json={"manufacturer_id": created.json()["id"], **CAR},
        headers=headers,
    )
    assert car.status_code == 201
    assert (
        secured_client.delete(
            f"/cars/{car.json()['id']}", headers=headers
        ).status_code
        == 204
    )


def test_unauthorized_request_does_not_change_data(
    secured_client: TestClient,
) -> None:
    secured_client.post("/manufacturers", json={"name": "Kia"})
    assert secured_client.get("/manufacturers").json() == []


def test_key_is_not_written_to_the_logs(
    secured_client: TestClient,
    api_key: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.DEBUG):
        secured_client.post(
            "/manufacturers",
            json={"name": "Kia"},
            headers={"X-API-Key": api_key},
        )
    assert api_key not in caplog.text


# --- logging and life cycle -


def test_requests_are_logged(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.INFO, logger="car_catalog.api"):
        client.get("/health")
    assert "GET /health -> 200" in caplog.text


def test_startup_log_contains_safe_settings_only(
    db_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """create_app configures logging (to stderr), so read stderr here."""
    settings = Settings(
        _env_file=None,  # type: ignore[call-arg]
        database_url=f"sqlite:///{db_path}",
        app_env="test",
        auto_create_tables=True,
        api_key="never-log-this",
    )
    with TestClient(create_app(settings)):
        pass
    logs = capsys.readouterr().err
    assert "Application started" in logs
    assert "Application stopped" in logs
    assert "never-log-this" not in logs
    assert "api_key_set': True" in logs


def test_production_without_key_logs_a_warning(
    db_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    settings = Settings(
        _env_file=None,  # type: ignore[call-arg]
        database_url=f"sqlite:///{db_path}",
        app_env="production",
        auto_create_tables=True,
    )
    with TestClient(create_app(settings)):
        pass
    logs = capsys.readouterr().err
    assert "API_KEY is not set" in logs
    assert "level=WARNING" in logs  # the production log format


def test_application_reads_settings_from_the_environment(
    db_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("AUTO_CREATE_TABLES", "true")
    with TestClient(create_app()) as env_client:
        body = env_client.get("/health").json()
    assert body["environment"] == "test"
    assert db_path.exists()


def test_data_survives_a_restart_of_the_application(
    db_path: Path,
) -> None:
    """The database file (a Docker volume) keeps data between runs."""
    settings = Settings(
        _env_file=None,  # type: ignore[call-arg]
        database_url=f"sqlite:///{db_path}",
        app_env="test",
        auto_create_tables=True,
    )
    with TestClient(create_app(settings)) as first:
        first.post("/manufacturers", json={"name": "Kia"})
    with TestClient(create_app(settings)) as second:
        assert [m["name"] for m in second.get("/manufacturers").json()] == [
            "Kia"
        ]


def test_database_is_not_touched_by_other_tests(db_path: Path) -> None:
    assert not db_path.exists()


def test_health_after_the_table_is_dropped(
    client: TestClient, db_path: Path
) -> None:
    from sqlalchemy import create_engine

    engine = create_engine(f"sqlite:///{db_path}")
    with engine.begin() as connection:
        connection.execute(text("DROP TABLE cars"))
        connection.execute(text("DROP TABLE manufacturers"))
    engine.dispose()
    assert client.get("/health").status_code == 503
