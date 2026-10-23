"""Shared fixtures."""

import pytest

from domain_app.container import Container, build_container
from domain_app.models import Car, ElectricCar, Vehicle
from domain_app.notifiers import InMemoryNotifier


@pytest.fixture
def vehicles() -> list[Vehicle]:
    return [
        Car("Toyota", "Camry", 2019, 21500, 45000, 1),
        Car("BMW", "X5", 2021, 48200, 18000, 2, body_type="suv"),
        Car("Toyota", "Corolla", 2022, 19800, 9000, 3),
        Car("Audi", "A4", 2018, 23000, 62000, 4),
        ElectricCar(
            "Tesla",
            "Model 3",
            2022,
            41000,
            15000,
            5,
            battery_kwh=75,
            range_km=491,
        ),
    ]


@pytest.fixture
def notifier() -> InMemoryNotifier:
    return InMemoryNotifier()


@pytest.fixture
def container(
    vehicles: list[Vehicle], notifier: InMemoryNotifier
) -> Container:
    built = build_container(notifier=notifier)
    for vehicle in vehicles:
        built.service.add_vehicle(vehicle)
    notifier.messages.clear()
    return built
