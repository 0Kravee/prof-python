"""Asynchronous HTTP code on a mock upstream (no real network)."""

import asyncio
from collections.abc import Awaitable, Callable
from time import perf_counter
from typing import Any

import httpx
import pytest

from car_catalog.config import Settings
from car_catalog.exceptions import BatchTimeoutError
from car_catalog.external_api import (
    FetchError,
    FetchSettings,
    backoff_delay,
    fetch_car,
    fetch_json,
    fetch_many,
)

Handler = Callable[[httpx.Request], Awaitable[httpx.Response]]


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


def make_client(handler: Handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="http://up"
    )


class Recorder:
    """Counts calls and records the pauses requested by the retry code."""

    def __init__(self) -> None:
        self.delays: list[float] = []

    async def sleep(self, delay: float) -> None:
        self.delays.append(delay)


def car_id_of(request: httpx.Request) -> int:
    return int(request.url.path.rsplit("/", 1)[-1])


# --------------------------------------------------------------- backoff
def test_backoff_is_exponential() -> None:
    assert [backoff_delay(0.2, n) for n in (1, 2, 3, 4)] == [
        0.2,
        0.4,
        0.8,
        1.6,
    ]


def test_fetch_settings_from_settings() -> None:
    fetch = FetchSettings.from_settings(
        Settings(
            max_attempts=4,
            backoff_seconds=0.5,
            max_concurrency=2,
            batch_timeout=9,
        )
    )
    assert fetch == FetchSettings(4, 0.5, 2, 9.0)


# ----------------------------------------------------------- fetch_json
async def test_success_on_the_first_attempt() -> None:
    calls = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json={"ok": True})

    recorder = Recorder()
    async with make_client(handler) as client:
        data, attempts = await fetch_json(client, "/x", sleep=recorder.sleep)
    assert (data, attempts, calls, recorder.delays) == ({"ok": True}, 1, 1, [])


async def test_retries_503_with_growing_pauses_then_succeeds() -> None:
    responses = iter([503, 503, 200])

    async def handler(request: httpx.Request) -> httpx.Response:
        status = next(responses)
        return httpx.Response(status, json={"n": status})

    recorder = Recorder()
    async with make_client(handler) as client:
        data, attempts = await fetch_json(
            client, "/x", attempts=3, backoff_seconds=0.1, sleep=recorder.sleep
        )
    assert attempts == 3 and data == {"n": 200}
    assert recorder.delays == [0.1, 0.2]


async def test_gives_up_after_all_attempts() -> None:
    calls = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(503)

    recorder = Recorder()
    async with make_client(handler) as client:
        with pytest.raises(FetchError) as info:
            await fetch_json(client, "/x", attempts=3, sleep=recorder.sleep)
    assert calls == 3 and info.value.attempts == 3
    assert isinstance(info.value.__cause__, httpx.HTTPStatusError)
    assert len(recorder.delays) == 2  # no pause after the last attempt


@pytest.mark.parametrize("status", [400, 401, 403, 404, 422])
async def test_client_errors_are_not_retried(status: int) -> None:
    calls = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(status)

    recorder = Recorder()
    async with make_client(handler) as client:
        with pytest.raises(FetchError) as info:
            await fetch_json(client, "/x", attempts=5, sleep=recorder.sleep)
    assert calls == 1 and recorder.delays == []
    assert info.value.status_code == status and info.value.attempts == 1


@pytest.mark.parametrize("status", [408, 429, 500, 502, 503, 504])
async def test_transient_statuses_are_retried(status: int) -> None:
    calls = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(status if calls == 1 else 200, json={})

    async with make_client(handler) as client:
        _, attempts = await fetch_json(client, "/x", sleep=Recorder().sleep)
    assert attempts == 2


@pytest.mark.parametrize(
    "error",
    [
        httpx.ConnectTimeout("t"),
        httpx.ReadTimeout("t"),
        httpx.ConnectError("c"),
        httpx.PoolTimeout("p"),
    ],
)
async def test_network_errors_and_timeouts_are_retried(
    error: httpx.TransportError,
) -> None:
    calls = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls < 3:
            raise error
        return httpx.Response(200, json={"v": 1})

    recorder = Recorder()
    async with make_client(handler) as client:
        data, attempts = await fetch_json(
            client, "/x", attempts=3, sleep=recorder.sleep
        )
    assert (data, attempts) == ({"v": 1}, 3)


async def test_persistent_timeout_fails_with_the_cause() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("too slow")

    async with make_client(handler) as client:
        with pytest.raises(FetchError, match="ReadTimeout") as info:
            await fetch_json(client, "/x", attempts=2, sleep=Recorder().sleep)
    assert isinstance(info.value.__cause__, httpx.ReadTimeout)


async def test_invalid_json_is_not_retried() -> None:
    calls = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, content=b"<html>")

    async with make_client(handler) as client:
        with pytest.raises(FetchError, match="invalid JSON"):
            await fetch_json(client, "/x", attempts=3, sleep=Recorder().sleep)
    assert calls == 1


async def test_a_single_attempt_never_sleeps() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503)

    recorder = Recorder()
    async with make_client(handler) as client:
        with pytest.raises(FetchError):
            await fetch_json(client, "/x", attempts=1, sleep=recorder.sleep)
    assert recorder.delays == []


# ------------------------------------------------------------- fetch_car
async def test_fetch_car_outcomes() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        car_id = car_id_of(request)
        if car_id == 404:
            return httpx.Response(404, json={"detail": "no"})
        if car_id == 503:
            return httpx.Response(503)
        if car_id == 7:
            return httpx.Response(200, json=[1, 2])  # not an object
        return httpx.Response(200, json=car_json(car_id))

    settings = FetchSettings(attempts=2, backoff_seconds=0)
    async with make_client(handler) as client:
        ok = await fetch_car(client, 1, settings, Recorder().sleep)
        missing = await fetch_car(client, 404, settings, Recorder().sleep)
        down = await fetch_car(client, 503, settings, Recorder().sleep)
        odd = await fetch_car(client, 7, settings, Recorder().sleep)
    assert (ok.status, ok.data) == ("ok", car_json(1))
    assert (missing.status, missing.attempts) == ("not_found", 1)
    assert (down.status, down.attempts) == ("failed", 2)
    assert down.error is not None and "after 2 attempts" in down.error
    assert odd.status == "failed" and odd.error == "unexpected response shape"


# ------------------------------------------------------------ fetch_many
async def test_results_keep_the_order_of_the_ids() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        car_id = car_id_of(request)
        await asyncio.sleep(0.03 if car_id == 1 else 0)  # first one is slowest
        return httpx.Response(200, json=car_json(car_id))

    async with make_client(handler) as client:
        results = await fetch_many(client, [1, 2, 3, 4], FetchSettings())
    assert [r.car_id for r in results] == [1, 2, 3, 4]


async def test_semaphore_limits_the_number_of_parallel_requests() -> None:
    active = peak = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        await asyncio.sleep(0.02)
        active -= 1
        return httpx.Response(200, json=car_json(car_id_of(request)))

    async with make_client(handler) as client:
        results = await fetch_many(
            client, list(range(1, 21)), FetchSettings(max_concurrency=3)
        )
    assert peak == 3 and len(results) == 20
    assert all(r.status == "ok" for r in results)


async def test_concurrent_loading_is_faster_than_sequential() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        await asyncio.sleep(0.05)
        return httpx.Response(200, json=car_json(car_id_of(request)))

    settings = FetchSettings(attempts=1, max_concurrency=10)
    ids = list(range(1, 11))
    async with make_client(handler) as client:
        started = perf_counter()
        for car_id in ids:
            await fetch_car(client, car_id, settings)
        sequential = perf_counter() - started
        started = perf_counter()
        await fetch_many(client, ids, settings)
        concurrent = perf_counter() - started
    assert sequential >= 0.45 and concurrent < sequential / 2


async def test_one_failure_does_not_break_the_batch() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        car_id = car_id_of(request)
        if car_id == 2:
            return httpx.Response(404)
        if car_id == 3:
            return httpx.Response(503)
        return httpx.Response(200, json=car_json(car_id))

    async with make_client(handler) as client:
        results = await fetch_many(
            client,
            [1, 2, 3, 4],
            FetchSettings(attempts=2, backoff_seconds=0),
        )
    assert [r.status for r in results] == ["ok", "not_found", "failed", "ok"]


async def test_batch_timeout_cancels_unfinished_requests() -> None:
    started = 0
    cancelled = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal started, cancelled
        started += 1
        try:
            await asyncio.sleep(5)
        except asyncio.CancelledError:
            cancelled += 1
            raise
        return httpx.Response(200, json=car_json(1))

    async with make_client(handler) as client:
        begin = perf_counter()
        with pytest.raises(BatchTimeoutError, match="did not finish") as info:
            await fetch_many(
                client, [1, 2, 3], FetchSettings(batch_timeout=0.1)
            )
        elapsed = perf_counter() - begin
    assert elapsed < 1.0  # it did not wait for the slow upstream
    assert started == 3 and cancelled == 3
    assert isinstance(info.value.__cause__, TimeoutError)


async def test_waiting_for_the_semaphore_counts_towards_the_timeout() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        await asyncio.sleep(0.2)
        return httpx.Response(200, json=car_json(car_id_of(request)))

    async with make_client(handler) as client:
        with pytest.raises(BatchTimeoutError):
            await fetch_many(
                client,
                list(range(1, 7)),
                FetchSettings(max_concurrency=1, batch_timeout=0.3),
            )


async def test_empty_batch() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("no request expected")

    async with make_client(handler) as client:
        assert await fetch_many(client, [], FetchSettings()) == []
