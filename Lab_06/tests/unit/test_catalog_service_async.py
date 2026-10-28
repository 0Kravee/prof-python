"""Unit tests of the asynchronous part (AsyncMock)."""

from unittest.mock import AsyncMock

import pytest

from car_catalog.exceptions import ExternalServiceError
from car_catalog.repositories import InMemoryVehicleRepository
from car_catalog.services import CatalogService

pytestmark = pytest.mark.asyncio


async def test_describe_async_returns_merged_data(car_factory) -> None:
    info = AsyncMock()
    info.fetch.return_value = {"body": "SUV"}
    service = CatalogService(
        InMemoryVehicleRepository(), async_info_service=info
    )
    result = await service.describe_async(car_factory(brand="BMW", model="X5"))
    assert result == {"name": "BMW X5", "body": "SUV"}
    info.fetch.assert_awaited_once_with("BMW", "X5")


async def test_async_timeout_becomes_external_service_error(
    car_factory,
) -> None:
    info = AsyncMock()
    info.fetch.side_effect = TimeoutError("no answer")
    service = CatalogService(
        InMemoryVehicleRepository(), async_info_service=info
    )
    with pytest.raises(ExternalServiceError) as excinfo:
        await service.describe_async(car_factory())
    assert isinstance(excinfo.value.__cause__, TimeoutError)


async def test_describe_async_without_service(car_factory) -> None:
    service = CatalogService(InMemoryVehicleRepository())
    with pytest.raises(ExternalServiceError, match="Async"):
        await service.describe_async(car_factory())


async def test_describe_all_async_queries_every_car(repository) -> None:
    info = AsyncMock()
    info.fetch.side_effect = lambda brand, model: {"key": f"{brand}-{model}"}
    service = CatalogService(repository, async_info_service=info)
    result = await service.describe_all_async()
    assert [item["key"] for item in result][:2] == ["Toyota-Camry", "BMW-X5"]
    assert info.fetch.await_count == 5


async def test_describe_all_async_on_empty_catalog() -> None:
    info = AsyncMock()
    service = CatalogService(
        InMemoryVehicleRepository(), async_info_service=info
    )
    assert await service.describe_all_async() == []
    info.fetch.assert_not_awaited()


async def test_one_failing_request_fails_describe_all(repository) -> None:
    info = AsyncMock()
    info.fetch.side_effect = [{"a": "1"}, ConnectionError("down")] + [{}] * 3
    service = CatalogService(repository, async_info_service=info)
    with pytest.raises(ExternalServiceError):
        await service.describe_all_async()
