"""Tests for the application service and dependency injection."""

import pytest

from domain_app.container import Container, build_container
from domain_app.criteria import BrandCriteria, YearRangeCriteria
from domain_app.exceptions import (
    DuplicateEntityError,
    EntityNotFoundError,
    InvalidPayloadError,
)
from domain_app.models import Car
from domain_app.notifiers import ConsoleNotifier, InMemoryNotifier
from domain_app.protocols import Notifier
from domain_app.repositories import InMemoryRepository
from domain_app.services import CatalogService, EntityService
from domain_app.value_objects import Money


def test_use_cases(container: Container) -> None:
    service = container.service
    assert service.count() == 5
    assert [v.vehicle_id for v in service.search_by_brand("toyota")] == [1, 3]
    assert [v.model for v in service.search_by_model("X5")] == ["X5"]
    assert [v.vehicle_id for v in service.search_by_text("model")] == [5]
    assert [v.vehicle_id for v in service.filter_by_year(2022)] == [3, 5]
    most_expensive = service.most_expensive()
    lowest = service.lowest_mileage()
    assert most_expensive is not None and most_expensive.model == "X5"
    assert lowest is not None and lowest.model == "Corolla"
    assert service.average_price() == Money.of(30700)


def test_combined_criteria_through_service(container: Container) -> None:
    found = container.service.search(
        BrandCriteria("Toyota") & YearRangeCriteria(min_year=2020)
    )
    assert [v.model for v in found] == ["Corolla"]


def test_statistics(container: Container) -> None:
    stats = container.service.statistics()
    assert stats.count == 5 and stats.total_value == Money.of(153500)
    assert stats.most_expensive is not None
    assert stats.most_expensive.title == "BMW X5 (2021)"
    assert stats.lowest_mileage is not None
    assert stats.lowest_mileage.title == "Toyota Corolla (2022)"


def test_statistics_of_empty_service() -> None:
    stats = build_container(notifier=InMemoryNotifier()).service.statistics()
    assert stats.count == 0 and stats.most_expensive is None
    assert stats.average_price == Money.zero()


def test_injected_notifier_receives_messages(
    container: Container, notifier: InMemoryNotifier
) -> None:
    container.service.add_vehicle(
        Car("Skoda", "Octavia", 2023, 26500, 1200, 9)
    )
    container.service.remove_vehicle(9)
    assert notifier.messages == [
        "Added: Skoda Octavia (2023)",
        "Removed: Skoda Octavia (2023)",
    ]


def test_add_from_payload(container: Container) -> None:
    vehicle = container.service.add_from_payload(
        {
            "kind": "car",
            "brand": "Kia",
            "model": "Rio",
            "year": 2020,
            "price": 9000,
            "mileage": 5000,
            "vehicle_id": 10,
        }
    )
    assert vehicle in container.service.catalog()
    with pytest.raises(InvalidPayloadError):
        container.service.add_from_payload(
            {  # type: ignore[typeddict-item]
                "kind": "electric",
                "brand": "A",
                "model": "B",
                "year": 2020,
                "price": 1.0,
                "mileage": 1,
            }
        )


def test_service_errors(container: Container, vehicles: list[Car]) -> None:
    with pytest.raises(DuplicateEntityError):
        container.service.add_vehicle(vehicles[0])
    with pytest.raises(EntityNotFoundError):
        container.service.remove_vehicle(999)
    with pytest.raises(EntityNotFoundError):
        container.service.get(999)


def test_sorted_by_price_and_aliases(container: Container) -> None:
    service = container.service
    prices = [v.price for v in service.sorted_by_price()]
    assert prices == sorted(prices, reverse=True)
    assert service.find_most_expensive() == service.most_expensive()
    assert service.calculate_average_price() == service.average_price()
    assert service.find_lowest_mileage() == service.min_mileage()
    assert service.add_car is not None


def test_generic_service_for_any_entity() -> None:
    class Item:
        def __init__(self, item_id: int) -> None:
            self.id = item_id

    service = EntityService[Item](InMemoryRepository[Item]())
    service.add(Item(1))
    service.add(Item(2))
    assert service.count() == 2 and service.get(2).id == 2
    service.remove(1)
    assert [i.id for i in service.all()] == [2]


def test_dependencies_can_be_replaced() -> None:
    repo = InMemoryRepository[Car]()  # any repository fits the protocol
    custom = build_container(repository=repo, notifier=InMemoryNotifier())
    assert isinstance(custom.service, CatalogService)
    assert custom.repository is repo


def test_runtime_checkable_notifier_protocol() -> None:
    assert isinstance(ConsoleNotifier(), Notifier)
    assert isinstance(InMemoryNotifier(), Notifier)
    assert not isinstance(object(), Notifier)


def test_default_container_uses_console_notifier(
    capsys: pytest.CaptureFixture[str],
) -> None:
    built = build_container()
    built.service.add_vehicle(Car("A", "B", 2020, 1, 1, 1))
    assert "[notify] Added: A B (2020)" in capsys.readouterr().out
