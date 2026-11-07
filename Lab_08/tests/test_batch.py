"""POST /cars/batch: the endpoint on top of the concurrent HTTP code."""

import asyncio
from dataclasses import replace
from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from car_catalog.config import Settings
from car_catalog.dependencies import get_http_client


def override_upstream(app: FastAPI, handler: Any) -> None:
    """Replace the HTTP client dependency with a mock upstream."""

    async def provide() -> httpx.AsyncClient:
        return httpx.AsyncClient(
            transport=httpx.MockTransport(handler), base_url="http://up"
        )

    app.dependency_overrides[get_http_client] = provide


def car_json(car_id: int) -> dict[str, Any]:
    return {
        "id": car_id,
        "manufacturer_id": 1,
        "brand": "Demo",
        "model": f"M{car_id}",
        "year": 2020,
        "price": 10.0,
        "mileage": 1,
    }


def test_batch_loads_cars_through_http_in_process(seeded: TestClient) -> None:
    response = seeded.post("/cars/batch", json={"ids": [1, 2, 3, 99]})
    assert response.status_code == 200
    body = response.json()
    assert body["requested"] == 4
    assert [c["id"] for c in body["found"]] == [1, 2, 3]
    assert body["found"][1]["model"] == "X5"
    assert body["missing"] == [99] and body["failed"] == []
    assert body["duration_seconds"] >= 0


def test_batch_removes_duplicate_ids_and_keeps_order(
    seeded: TestClient,
) -> None:
    body = seeded.post("/cars/batch", json={"ids": [3, 1, 3, 1, 2]}).json()
    assert body["requested"] == 3
    assert [c["id"] for c in body["found"]] == [3, 1, 2]


@pytest.mark.parametrize(
    "payload",
    [{}, {"ids": []}, {"ids": [0]}, {"ids": ["a"]}, {"ids": [1], "x": 1}],
)
def test_batch_validation(client: TestClient, payload: dict[str, Any]) -> None:
    assert client.post("/cars/batch", json=payload).status_code == 422


def test_batch_size_limit(app: FastAPI, settings: Settings) -> None:
    app.state.settings = replace(settings, max_batch_size=3)
    with TestClient(app) as client:
        response = client.post("/cars/batch", json={"ids": [1, 2, 3, 4]})
    assert response.status_code == 422
    assert response.json()["code"] == "invalid_query"


def test_flaky_upstream_is_retried_and_reported(app: FastAPI) -> None:
    attempts: dict[int, int] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        car_id = int(request.url.path.rsplit("/", 1)[-1])
        attempts[car_id] = attempts.get(car_id, 0) + 1
        if car_id == 1 and attempts[car_id] < 3:
            return httpx.Response(503)  # recovers on the third attempt
        if car_id == 2:
            return httpx.Response(500)  # never recovers
        if car_id == 3:
            return httpx.Response(404)
        return httpx.Response(200, json=car_json(car_id))

    override_upstream(app, handler)
    with TestClient(app) as client:
        body = client.post("/cars/batch", json={"ids": [1, 2, 3, 4]}).json()
    assert [c["id"] for c in body["found"]] == [1, 4]
    assert body["missing"] == [3]
    assert body["failed"] == [
        {
            "id": 2,
            "reason": "failed after 3 attempts: HTTPStatusError",
            "attempts": 3,
        }
    ]
    assert attempts == {1: 3, 2: 3, 3: 1, 4: 1}  # 404 is not retried


def test_upstream_timeouts_are_reported_per_car(app: FastAPI) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow")

    override_upstream(app, handler)
    with TestClient(app) as client:
        body = client.post("/cars/batch", json={"ids": [1]}).json()
    assert body["found"] == [] and body["failed"][0]["attempts"] == 3
    assert "ReadTimeout" in body["failed"][0]["reason"]


def test_invalid_upstream_payload_becomes_a_failure(app: FastAPI) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"id": "oops"})

    override_upstream(app, handler)
    with TestClient(app) as client:
        body = client.post("/cars/batch", json={"ids": [1]}).json()
    assert body["failed"] == [
        {"id": 1, "reason": "invalid payload from upstream", "attempts": 1}
    ]


def test_batch_timeout_is_504(app: FastAPI, settings: Settings) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        await asyncio.sleep(5)
        return httpx.Response(200, json=car_json(1))

    override_upstream(app, handler)
    app.state.settings = replace(settings, batch_timeout=0.1)
    with TestClient(app) as client:
        response = client.post("/cars/batch", json={"ids": [1, 2]})
    assert response.status_code == 504
    assert response.json()["code"] == "batch_timeout"


def test_http_client_is_shared_and_closed_on_shutdown(app: FastAPI) -> None:
    with TestClient(app) as client:
        client.post("/cars/batch", json={"ids": [1]})
        first = app.state.http_client
        client.post("/cars/batch", json={"ids": [1]})
        assert app.state.http_client is first  # one pooled client
        assert not first.is_closed
    assert first.is_closed and app.state.http_client is None


async def test_the_api_can_be_called_with_an_async_client(
    app: FastAPI,
) -> None:
    """The same app driven by httpx.AsyncClient over the ASGI transport."""
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://t"
        ) as client:
            created = await client.post(
                "/cars",
                json={
                    "brand": "Kia",
                    "model": "Rio",
                    "year": 2020,
                    "price": 9000,
                    "mileage": 5,
                },
            )
            batch = await client.post("/cars/batch", json={"ids": [1, 2]})
    assert created.status_code == 201
    assert batch.json()["missing"] == [2] and len(batch.json()["found"]) == 1
