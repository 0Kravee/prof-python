"""Entry point.

``python main.py``          fast in-process demonstration (no server, no port)
``python main.py --serve``  start the real server with uvicorn
"""

import argparse
import asyncio
import importlib.util
import sys
from collections.abc import Sequence
from dataclasses import replace
from pathlib import Path
from time import perf_counter
from typing import Any

# Allows running this file directly (``python main.py``) without
# installing the package: the ``src`` directory is added to sys.path.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

REQUIRED_PACKAGES = ("fastapi", "uvicorn", "sqlalchemy", "httpx", "pydantic")


def ensure_dependencies() -> None:
    """Explain what to do when third-party packages are not installed."""
    missing = [
        name
        for name in REQUIRED_PACKAGES
        if sys.modules.get(name, ...) is None
        or importlib.util.find_spec(name) is None
    ]
    if missing:
        print(
            f"Missing packages: {', '.join(missing)}.\n"
            "Install the dependencies first:\n"
            "    python -m pip install -e .\n"
            "or  python -m pip install -r requirements.txt",
            file=sys.stderr,
        )
        raise SystemExit(1)


ensure_dependencies()

import httpx  # noqa: E402

from car_catalog.api import create_app  # noqa: E402
from car_catalog.config import Settings  # noqa: E402
from car_catalog.dependencies import get_http_client  # noqa: E402
from car_catalog.exceptions import BatchTimeoutError  # noqa: E402
from car_catalog.external_api import (  # noqa: E402
    FetchResult,
    FetchSettings,
    fetch_car,
    fetch_many,
)

DEMO_CARS: list[dict[str, Any]] = [
    {
        "brand": "Toyota",
        "model": "Camry",
        "year": 2019,
        "price": 21500,
        "mileage": 45000,
    },
    {
        "brand": "BMW",
        "model": "X5",
        "year": 2021,
        "price": 48200,
        "mileage": 18000,
    },
    {
        "brand": "Toyota",
        "model": "Corolla",
        "year": 2022,
        "price": 19800,
        "mileage": 9000,
    },
    {
        "brand": "Audi",
        "model": "A4",
        "year": 2018,
        "price": 23000,
        "mileage": 62000,
    },
    {
        "brand": "BMW",
        "model": "3 Series",
        "year": 2020,
        "price": 31000,
        "mileage": 27000,
    },
    {
        "brand": "Tesla",
        "model": "Model 3",
        "year": 2022,
        "price": 41000,
        "mileage": 15000,
    },
    {
        "brand": "Skoda",
        "model": "Octavia",
        "year": 2023,
        "price": 26500,
        "mileage": 1200,
    },
]


def section(title: str) -> None:
    print(f"\n=== {title} ===")


async def call(
    client: httpx.AsyncClient, method: str, url: str, **kwargs: Any
) -> httpx.Response:
    """Send a request and print one line: method, url and status."""
    response = await client.request(method, url, **kwargs)
    print(f"{method:<6} {url} -> {response.status_code}")
    return response


async def demo_crud(client: httpx.AsyncClient) -> None:
    section("CRUD: create cars (POST /cars with a brand)")
    for payload in DEMO_CARS:
        response = await call(client, "POST", "/cars", json=payload)
        car = response.json()
        print(f"       id={car['id']} {car['brand']} {car['model']}")

    section("Read, search, sort, paginate")
    response = await call(client, "GET", "/cars/1")
    print("      ", response.json())
    response = await call(
        client,
        "GET",
        "/cars",
        params={"brand": "BMW", "sort": "price", "order": "desc"},
    )
    print("       BMW by price desc:", [c["model"] for c in response.json()])
    response = await call(
        client,
        "GET",
        "/cars",
        params={"min_year": 2020, "max_price": 45000, "limit": 3, "offset": 1},
    )
    print(
        "       year>=2020, price<=45000, limit=3, offset=1:",
        [c["model"] for c in response.json()],
        "| X-Total-Count =",
        response.headers["X-Total-Count"],
    )
    response = await call(client, "GET", "/cars", params={"model": "mod"})
    print(
        "       model contains 'mod':", [c["model"] for c in response.json()]
    )

    section("Update (PATCH) and delete")
    response = await call(
        client, "PATCH", "/cars/1", json={"price": 20000, "mileage": 46000}
    )
    print("      ", response.json())
    await call(client, "DELETE", "/cars/7")
    await call(client, "GET", "/cars/7")


async def demo_errors(client: httpx.AsyncClient) -> None:
    section("Structured errors")
    response = await call(client, "GET", "/cars/999")
    print("      ", response.json())
    response = await call(
        client,
        "POST",
        "/cars",
        json={
            "brand": "X",
            "model": "",
            "year": 1700,
            "price": -5,
            "mileage": 0,
        },
    )
    body = response.json()
    print("       code:", body["code"], "| problems:", len(body["detail"]))
    for problem in body["detail"]:
        print(
            "        -",
            ".".join(map(str, problem["loc"][1:])),
            ":",
            problem["msg"],
        )
    response = await call(client, "DELETE", "/manufacturers/1")
    print("      ", response.json())
    response = await call(
        client, "GET", "/cars", params={"min_year": 2022, "max_year": 2000}
    )
    print("      ", response.json())


async def demo_statistics(client: httpx.AsyncClient) -> None:
    section("Statistics and manufacturers")
    response = await call(client, "GET", "/cars/most-expensive")
    print(
        "       most expensive:",
        response.json()["brand"],
        response.json()["model"],
    )
    response = await call(client, "GET", "/cars/lowest-mileage")
    print(
        "       lowest mileage:",
        response.json()["brand"],
        response.json()["model"],
    )
    response = await call(client, "GET", "/cars/statistics")
    stats = response.json()
    print(
        f"       count={stats['count']}, average={stats['average_price']}, "
        f"min={stats['min_price']}, max={stats['max_price']}"
    )
    response = await call(client, "GET", "/manufacturers")
    print("      ", [m["name"] for m in response.json()])
    response = await call(client, "GET", "/manufacturers/2/cars")
    print(
        "       cars of manufacturer 2:", [c["model"] for c in response.json()]
    )


async def demo_batch(client: httpx.AsyncClient) -> None:
    section("Batch: many cars loaded concurrently through HTTPX")
    response = await call(
        client, "POST", "/cars/batch", json={"ids": [1, 2, 3, 4, 5, 99]}
    )
    body = response.json()
    print(
        "       found:",
        [c["id"] for c in body["found"]],
        "| missing:",
        body["missing"],
        "| failed:",
        body["failed"],
    )


def upstream_handler(
    latency: float, state: dict[str, int], flaky: dict[int, int]
) -> Any:
    """A fake upstream service: latency, in-flight counter, failures."""

    async def handler(request: httpx.Request) -> httpx.Response:
        car_id = int(request.url.path.rsplit("/", 1)[-1])
        state["active"] += 1
        state["peak"] = max(state["peak"], state["active"])
        try:
            await asyncio.sleep(latency)
        finally:
            state["active"] -= 1
        if flaky.get(car_id, 0) > 0:
            flaky[car_id] -= 1
            return httpx.Response(503, json={"detail": "busy"})
        return httpx.Response(
            200,
            json={
                "id": car_id,
                "manufacturer_id": 1,
                "brand": "Demo",
                "model": f"M{car_id}",
                "year": 2020,
                "price": 1000.0,
                "mileage": 1,
            },
        )

    return handler


async def demo_concurrency() -> None:
    section("Concurrency: sequential vs gather (upstream latency 50 ms)")
    ids = list(range(1, 11))
    settings = FetchSettings(attempts=1, max_concurrency=5, batch_timeout=5)

    state = {"active": 0, "peak": 0}
    transport = httpx.MockTransport(upstream_handler(0.05, state, {}))
    async with httpx.AsyncClient(
        transport=transport, base_url="http://up"
    ) as client:
        started = perf_counter()
        for car_id in ids:
            await fetch_car(client, car_id, settings)
        sequential = perf_counter() - started

    state = {"active": 0, "peak": 0}
    transport = httpx.MockTransport(upstream_handler(0.05, state, {}))
    async with httpx.AsyncClient(
        transport=transport, base_url="http://up"
    ) as client:
        started = perf_counter()
        results = await fetch_many(client, ids, settings)
        concurrent = perf_counter() - started
    print(f"       10 requests sequentially : {sequential:.3f} s")
    print(f"       10 requests with gather  : {concurrent:.3f} s")
    print(
        f"       max requests in flight   : {state['peak']} "
        f"(Semaphore limit 5)"
    )
    print("       all ok:", all(r.status == "ok" for r in results))


def describe(result: FetchResult) -> str:
    return (
        f"id={result.car_id} {result.status} "
        f"after {result.attempts} attempt(s)"
    )


async def demo_retry_and_timeout(app: Any) -> None:
    section("Retry with exponential backoff (upstream: 503, 503, then 200)")
    state = {"active": 0, "peak": 0}
    flaky = {1: 2, 2: 99}  # car 1 recovers, car 2 never does
    transport = httpx.MockTransport(upstream_handler(0.0, state, flaky))
    settings = FetchSettings(attempts=3, backoff_seconds=0.02, batch_timeout=5)
    delays: list[float] = []

    async def record_sleep(delay: float) -> None:
        delays.append(delay)
        await asyncio.sleep(delay)

    async with httpx.AsyncClient(
        transport=transport, base_url="http://up"
    ) as client:
        results = await fetch_many(client, [1, 2, 3], settings, record_sleep)
    for result in results:
        print("      ", describe(result), "|", result.error or "")
    print("       backoff pauses:", [round(d, 2) for d in delays])

    section("Timeout of the whole batch -> HTTP 504")
    slow = httpx.MockTransport(upstream_handler(1.0, state, {}))
    slow_client = httpx.AsyncClient(transport=slow, base_url="http://up")

    async def provide_slow_client() -> httpx.AsyncClient:
        return slow_client

    app.dependency_overrides[get_http_client] = provide_slow_client
    app.state.settings = replace(app.state.settings, batch_timeout=0.15)
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://demo"
        ) as client:
            response = await call(
                client, "POST", "/cars/batch", json={"ids": [1, 2, 3]}
            )
            print("      ", response.json())
    finally:
        app.dependency_overrides.clear()
        await slow_client.aclose()
    try:
        async with httpx.AsyncClient(
            transport=slow, base_url="http://up"
        ) as client:
            await fetch_many(
                client, [1], FetchSettings(attempts=1, batch_timeout=0.1)
            )
    except BatchTimeoutError as error:
        print("       BatchTimeoutError:", error)


async def run_demo() -> None:
    app = create_app(Settings(database_url="sqlite://", backoff_seconds=0.01))
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://demo"
        ) as client:
            response = await call(client, "GET", "/")
            print("      ", response.json())
            await demo_crud(client)
            await demo_errors(client)
            await demo_statistics(client)
            await demo_batch(client)
        await demo_concurrency()
        await demo_retry_and_timeout(app)
    print("\nDemo finished. Start the real server: python main.py --serve")


def serve(host: str, port: int) -> None:
    import uvicorn

    base = Settings.from_env()
    target = "127.0.0.1" if host == "0.0.0.0" else host
    settings = (
        base
        if base.api_base_url
        else replace(
            base,
            api_base_url=f"http://{target}:{port}",
        )
    )
    uvicorn.run(create_app(settings), host=host, port=port)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Car catalog REST API")
    parser.add_argument(
        "--serve", action="store_true", help="start the server"
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args(argv)
    if args.serve:
        serve(args.host, args.port)
        return 0
    asyncio.run(run_demo())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
