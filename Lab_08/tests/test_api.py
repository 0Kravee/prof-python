"""REST API: status codes, validation, search, errors, OpenAPI."""

from typing import Any

import pytest
from fastapi.testclient import TestClient

from conftest import CARS


# ------------------------------------------------------------------ system
def test_root_and_health(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {
        "name": "Car Catalog API",
        "version": "0.8.0",
        "docs": "/docs",
    }
    assert client.get("/health").json() == {"status": "ok"}


def test_openapi_documents_every_endpoint(client: TestClient) -> None:
    schema = client.get("/openapi.json").json()
    assert schema["info"]["title"] == "Car Catalog API"
    paths = schema["paths"]
    expected = {
        ("/cars", "get"),
        ("/cars", "post"),
        ("/cars/{car_id}", "get"),
        ("/cars/{car_id}", "patch"),
        ("/cars/{car_id}", "delete"),
        ("/cars/most-expensive", "get"),
        ("/cars/lowest-mileage", "get"),
        ("/cars/statistics", "get"),
        ("/cars/batch", "post"),
        ("/manufacturers", "get"),
        ("/manufacturers", "post"),
        ("/manufacturers/{manufacturer_id}", "get"),
        ("/manufacturers/{manufacturer_id}", "delete"),
        ("/manufacturers/{manufacturer_id}/cars", "get"),
    }
    assert expected <= {(p, m) for p, ops in paths.items() for m in ops}
    assert {t["name"] for t in schema["tags"]} >= {"cars", "manufacturers"}
    assert client.get("/docs").status_code == 200
    summaries = {
        op["summary"] for ops in paths.values() for op in ops.values()
    }
    assert "Get a car" in summaries
    assert "Load many cars concurrently through HTTPX" in summaries
    assert "Get Car" not in summaries  # no auto-generated titles


# ------------------------------------------------------------------- create
def test_create_car_with_brand(client: TestClient) -> None:
    response = client.post("/cars", json=CARS[0])
    assert response.status_code == 201
    body = response.json()
    assert body == {
        "id": 1,
        "manufacturer_id": 1,
        "brand": "Toyota",
        "model": "Camry",
        "year": 2019,
        "price": 21500.0,
        "mileage": 45000,
    }
    assert client.get("/manufacturers").json() == [
        {"id": 1, "name": "Toyota", "country": None}
    ]


def test_create_car_with_manufacturer_id(client: TestClient) -> None:
    maker = client.post(
        "/manufacturers", json={"name": "Skoda", "country": "Czechia"}
    )
    assert maker.status_code == 201
    response = client.post(
        "/cars",
        json={
            "manufacturer_id": maker.json()["id"],
            "model": "Octavia",
            "year": 2023,
            "price": 26500,
            "mileage": 1200,
        },
    )
    assert response.status_code == 201 and response.json()["brand"] == "Skoda"


@pytest.mark.parametrize(
    "override",
    [
        {"year": 1700},
        {"price": -1},
        {"mileage": -5},
        {"model": ""},
        {"year": "abc"},
        {"extra": True},
        {"manufacturer_id": 1},  # both brand and manufacturer_id
    ],
)
def test_create_validation_errors(
    client: TestClient, override: dict[str, Any]
) -> None:
    response = client.post("/cars", json={**CARS[0], **override})
    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "validation_error" and body["detail"]
    assert client.get("/cars").json() == []  # nothing was stored


def test_create_requires_a_manufacturer_reference(client: TestClient) -> None:
    payload = {k: v for k, v in CARS[0].items() if k != "brand"}
    assert client.post("/cars", json=payload).status_code == 422


def test_create_with_unknown_manufacturer_is_404(client: TestClient) -> None:
    payload = {k: v for k, v in CARS[0].items() if k != "brand"}
    response = client.post("/cars", json={**payload, "manufacturer_id": 77})
    assert response.status_code == 404
    assert response.json()["code"] == "not_found"


def test_malformed_json_is_422(client: TestClient) -> None:
    response = client.post(
        "/cars",
        content=b"{broken",
        headers={"content-type": "application/json"},
    )
    assert response.status_code == 422


# --------------------------------------------------------------------- read
def test_get_car_and_404(seeded: TestClient) -> None:
    assert seeded.get("/cars/2").json()["model"] == "X5"
    response = seeded.get("/cars/999")
    assert response.status_code == 404
    assert response.json() == {
        "detail": "Car 999 not found",
        "code": "not_found",
    }
    assert seeded.get("/cars/abc").status_code == 422


def test_list_all(seeded: TestClient) -> None:
    response = seeded.get("/cars")
    assert response.status_code == 200 and len(response.json()) == 5
    assert response.headers["X-Total-Count"] == "5"


def test_search_by_brand_and_model(seeded: TestClient) -> None:
    by_brand = seeded.get("/cars", params={"brand": "bmw"}).json()
    assert [c["model"] for c in by_brand] == ["X5", "3 Series"]
    by_model = seeded.get("/cars", params={"model": "oro"}).json()
    assert [c["model"] for c in by_model] == ["Corolla"]
    assert seeded.get("/cars", params={"brand": "Ford"}).json() == []


def test_filter_by_year_and_price(seeded: TestClient) -> None:
    assert len(seeded.get("/cars", params={"year": 2022}).json()) == 1
    response = seeded.get(
        "/cars", params={"min_year": 2020, "max_price": 40000}
    )
    assert sorted(c["model"] for c in response.json()) == [
        "3 Series",
        "Corolla",
    ]
    assert len(seeded.get("/cars", params={"max_mileage": 18000}).json()) == 2


def test_sorting_and_pagination(seeded: TestClient) -> None:
    desc = seeded.get(
        "/cars", params={"sort": "price", "order": "desc"}
    ).json()
    prices = [c["price"] for c in desc]
    assert prices == sorted(prices, reverse=True)
    page = seeded.get("/cars", params={"limit": 2, "offset": 2})
    assert [c["id"] for c in page.json()] == [3, 4]
    assert page.headers["X-Total-Count"] == "5"  # the total, not the page


@pytest.mark.parametrize(
    "params",
    [
        {"limit": 0},
        {"limit": 101},
        {"offset": -1},
        {"sort": "color"},
        {"order": "sideways"},
        {"min_price": -1},
        {"year": 1500},
        {"min_year": 2022, "max_year": 2000},
        {"min_price": 500, "max_price": 100},
    ],
)
def test_invalid_query_parameters(
    seeded: TestClient, params: dict[str, Any]
) -> None:
    assert seeded.get("/cars", params=params).status_code == 422


def test_fixed_paths_are_not_swallowed_by_the_id_route(
    seeded: TestClient,
) -> None:
    """/cars/{car_id} is declared last, so these are not parsed as ids."""
    assert seeded.get("/cars/statistics").status_code == 200
    assert seeded.get("/cars/most-expensive").json()["model"] == "X5"
    assert seeded.get("/cars/lowest-mileage").json()["model"] == "Corolla"


def test_statistics(seeded: TestClient) -> None:
    stats = seeded.get("/cars/statistics").json()
    assert stats["count"] == 5 and stats["average_price"] == 28700.0
    assert (stats["min_price"], stats["max_price"]) == (19800.0, 48200.0)
    assert stats["total_value"] == 143500.0
    assert stats["most_expensive"]["model"] == "X5"
    assert stats["lowest_mileage"]["model"] == "Corolla"


def test_empty_catalog(client: TestClient) -> None:
    stats = client.get("/cars/statistics").json()
    assert stats["count"] == 0 and stats["most_expensive"] is None
    for path in ("/cars/most-expensive", "/cars/lowest-mileage"):
        response = client.get(path)
        assert response.status_code == 404
        assert response.json()["code"] == "not_found"
    assert client.get("/cars").json() == []


# ------------------------------------------------------------------- update
def test_patch_price_and_mileage(seeded: TestClient) -> None:
    response = seeded.patch("/cars/1", json={"price": 20000, "mileage": 46000})
    assert response.status_code == 200
    body = response.json()
    assert (body["price"], body["mileage"], body["model"]) == (
        20000.0,
        46000,
        "Camry",
    )
    assert seeded.get("/cars/1").json()["price"] == 20000.0


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"price": None},
        {"price": -1},
        {"year": 3000},
        {"brand": "Kia"},
        {"mileage": "many"},
    ],
)
def test_patch_validation(seeded: TestClient, body: dict[str, Any]) -> None:
    assert seeded.patch("/cars/1", json=body).status_code == 422
    assert seeded.get("/cars/1").json()["price"] == 21500.0


def test_patch_missing_car(client: TestClient) -> None:
    response = client.patch("/cars/5", json={"price": 1})
    assert response.status_code == 404


# ------------------------------------------------------------------- delete
def test_delete_car(seeded: TestClient) -> None:
    response = seeded.delete("/cars/1")
    assert response.status_code == 204 and response.content == b""
    assert seeded.get("/cars/1").status_code == 404
    assert seeded.delete("/cars/1").status_code == 404
    assert len(seeded.get("/cars").json()) == 4


# ------------------------------------------------------------ manufacturers
def test_manufacturer_crud_and_conflicts(seeded: TestClient) -> None:
    made = seeded.post("/manufacturers", json={"name": "Kia"})
    assert made.status_code == 201
    duplicate = seeded.post("/manufacturers", json={"name": "KIA"})
    assert duplicate.status_code == 409
    assert duplicate.json()["code"] == "duplicate"
    kia_id = made.json()["id"]
    assert seeded.get(f"/manufacturers/{kia_id}").json()["name"] == "Kia"
    assert seeded.delete(f"/manufacturers/{kia_id}").status_code == 204
    assert seeded.get(f"/manufacturers/{kia_id}").status_code == 404
    conflict = seeded.delete("/manufacturers/1")  # Toyota has cars
    assert (
        conflict.status_code == 409 and conflict.json()["code"] == "conflict"
    )
    assert seeded.delete("/manufacturers/999").status_code == 404


def test_manufacturer_cars(seeded: TestClient) -> None:
    response = seeded.get("/manufacturers/2/cars")
    assert response.status_code == 200
    assert [c["model"] for c in response.json()] == ["X5", "3 Series"]
    assert seeded.get("/manufacturers/999/cars").status_code == 404


def test_every_error_has_detail_and_code(seeded: TestClient) -> None:
    for response in (
        seeded.get("/cars/999"),
        seeded.post("/cars", json={}),
        seeded.delete("/manufacturers/1"),
    ):
        body = response.json()
        assert set(body) == {"detail", "code"} and response.status_code >= 400


def test_unknown_route_is_404(client: TestClient) -> None:
    assert client.get("/nothing-here").status_code == 404
    assert client.put("/cars/1", json={}).status_code == 405
