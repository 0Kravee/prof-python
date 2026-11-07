"""HTTP client code: retry with backoff, timeout, Semaphore, Task, gather."""

import asyncio
import logging
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from typing import Any, Literal

import httpx

from car_catalog.config import Settings
from car_catalog.exceptions import BatchTimeoutError

logger = logging.getLogger(__name__)

# transient failures worth another attempt; 4xx (e.g. 404) never are
RETRYABLE_STATUSES = frozenset({408, 425, 429, 500, 502, 503, 504})

Sleep = Callable[[float], Awaitable[None]]


@dataclass(frozen=True)
class FetchSettings:
    attempts: int = 3
    backoff_seconds: float = 0.2
    max_concurrency: int = 5
    batch_timeout: float = 10.0

    @classmethod
    def from_settings(cls, settings: Settings) -> "FetchSettings":
        return cls(
            attempts=settings.max_attempts,
            backoff_seconds=settings.backoff_seconds,
            max_concurrency=settings.max_concurrency,
            batch_timeout=settings.batch_timeout,
        )


class FetchError(Exception):
    """A request finally failed (the original error is the __cause__)."""

    def __init__(
        self,
        message: str,
        *,
        attempts: int,
        status_code: int | None = None,
    ) -> None:
        super().__init__(message)
        self.attempts = attempts
        self.status_code = status_code


@dataclass(frozen=True)
class FetchResult:
    """Outcome of loading one car: a failure of one car is not fatal."""

    car_id: int
    status: Literal["ok", "not_found", "failed"]
    data: dict[str, Any] | None = None
    error: str | None = None
    attempts: int = 1


def backoff_delay(base_seconds: float, attempt: int) -> float:
    """Exponential backoff: base, 2*base, 4*base, ..."""
    return float(base_seconds * 2 ** (attempt - 1))


async def fetch_json(
    client: httpx.AsyncClient,
    url: str,
    *,
    attempts: int = 3,
    backoff_seconds: float = 0.2,
    sleep: Sleep = asyncio.sleep,
) -> tuple[Any, int]:
    """GET ``url`` as JSON with retry; returns (data, attempts used).

    Only transient problems are retried: network errors, timeouts and
    the statuses in RETRYABLE_STATUSES. Between attempts the coroutine
    awaits an exponentially growing pause.
    """
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            response = await client.get(url)
            response.raise_for_status()
            return response.json(), attempt
        except httpx.HTTPStatusError as error:
            status = error.response.status_code
            if status not in RETRYABLE_STATUSES:
                raise FetchError(
                    f"HTTP {status}", attempts=attempt, status_code=status
                ) from error
            last_error = error
        except httpx.TransportError as error:  # includes every timeout
            last_error = error
        except ValueError as error:  # the body is not valid JSON
            raise FetchError("invalid JSON", attempts=attempt) from error
        if attempt == attempts:
            break
        delay = backoff_delay(backoff_seconds, attempt)
        logger.warning(
            "Attempt %s/%s for %s failed (%s); retrying in %.2f s",
            attempt,
            attempts,
            url,
            type(last_error).__name__,
            delay,
        )
        await sleep(delay)
    raise FetchError(
        f"failed after {attempts} attempts: {type(last_error).__name__}",
        attempts=attempts,
    ) from last_error


async def fetch_car(
    client: httpx.AsyncClient,
    car_id: int,
    settings: FetchSettings,
    sleep: Sleep = asyncio.sleep,
) -> FetchResult:
    """Load one car through the REST API and describe the outcome."""
    try:
        data, attempts = await fetch_json(
            client,
            f"/cars/{car_id}",
            attempts=settings.attempts,
            backoff_seconds=settings.backoff_seconds,
            sleep=sleep,
        )
    except FetchError as error:
        if error.status_code == 404:
            return FetchResult(car_id, "not_found", attempts=error.attempts)
        return FetchResult(
            car_id, "failed", error=str(error), attempts=error.attempts
        )
    if not isinstance(data, dict):
        return FetchResult(
            car_id,
            "failed",
            error="unexpected response shape",
            attempts=attempts,
        )
    return FetchResult(car_id, "ok", data=data, attempts=attempts)


async def fetch_one(
    client: httpx.AsyncClient,
    semaphore: asyncio.Semaphore,
    car_id: int,
    settings: FetchSettings,
    sleep: Sleep = asyncio.sleep,
) -> FetchResult:
    """Like fetch_car, but waits for a free slot of the Semaphore first."""
    async with semaphore:
        return await fetch_car(client, car_id, settings, sleep)


async def fetch_many(
    client: httpx.AsyncClient,
    car_ids: Sequence[int],
    settings: FetchSettings,
    sleep: Sleep = asyncio.sleep,
) -> list[FetchResult]:
    """Load many cars concurrently.

    * every car is an ``asyncio.Task`` (created with create_task);
    * ``asyncio.gather`` collects the results in the order of ``car_ids``;
    * the Semaphore allows only ``max_concurrency`` requests at a time;
    * the whole batch must finish within ``batch_timeout`` seconds,
      otherwise the unfinished tasks are cancelled (BatchTimeoutError).
    """
    semaphore = asyncio.Semaphore(settings.max_concurrency)
    tasks = [
        asyncio.create_task(
            fetch_one(client, semaphore, car_id, settings, sleep)
        )
        for car_id in car_ids
    ]
    try:
        results = await asyncio.wait_for(
            asyncio.gather(*tasks), timeout=settings.batch_timeout
        )
    except TimeoutError as error:
        raise BatchTimeoutError(
            f"batch of {len(car_ids)} car(s) did not finish "
            f"in {settings.batch_timeout:g} s"
        ) from error
    finally:
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
    return list(results)
