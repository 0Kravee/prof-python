"""Research: dependency created inside a class vs dependency injection."""

from domain_app.models import Vehicle
from domain_app.notifiers import ConsoleNotifier
from domain_app.repositories import InMemoryRepository


class CoupledCatalogService:
    """Variant A: the service creates its concrete dependencies itself.

    It is tightly coupled to InMemoryRepository and ConsoleNotifier: they
    cannot be replaced from outside, and every call prints to the console.
    """

    def __init__(self) -> None:
        self.repository = InMemoryRepository[Vehicle]()
        self.notifier = ConsoleNotifier()

    def add_vehicle(self, vehicle: Vehicle) -> None:
        self.repository.add(vehicle)
        self.notifier.notify(f"Added: {vehicle.specification.title}")
