"""Application service layer."""

from typing import Generic

from domain_app.criteria import (
    BrandCriteria,
    BrandOrModelCriteria,
    ModelCriteria,
    SearchCriteria,
    YearCriteria,
)
from domain_app.dto import (
    CatalogStatistics,
    VehiclePayload,
    VehicleSummary,
    vehicle_from_payload,
)
from domain_app.models import Vehicle, VehicleCatalog
from domain_app.protocols import Notifier, Repository
from domain_app.repositories import E
from domain_app.value_objects import Money


class EntityService(Generic[E]):
    """Generic service: basic use cases for any entity type."""

    def __init__(self, repository: Repository[E]) -> None:
        self._repository = repository

    def add(self, entity: E) -> E:
        self._repository.add(entity)
        return entity

    def get(self, entity_id: int) -> E:
        return self._repository.get(entity_id)

    def remove(self, entity_id: int) -> None:
        self._repository.remove(entity_id)

    def all(self) -> list[E]:
        return list(self._repository.list_all())

    def count(self) -> int:
        return len(self._repository.list_all())


class CatalogService(EntityService[Vehicle]):
    """Use cases of the vehicle catalog.

    Dependencies (repository and notifier) are injected through the
    constructor and are described by protocols, not by concrete classes.
    """

    def __init__(
        self, repository: Repository[Vehicle], notifier: Notifier
    ) -> None:
        super().__init__(repository)
        self._notifier = notifier

    def add_vehicle(self, vehicle: Vehicle) -> Vehicle:
        self.add(vehicle)
        self._notifier.notify(f"Added: {vehicle.specification.title}")
        return vehicle

    def add_from_payload(self, payload: VehiclePayload) -> Vehicle:
        return self.add_vehicle(vehicle_from_payload(payload))

    def remove_vehicle(self, vehicle_id: int) -> None:
        vehicle = self.get(vehicle_id)
        self.remove(vehicle_id)
        self._notifier.notify(f"Removed: {vehicle.specification.title}")

    def catalog(self) -> VehicleCatalog:
        """Snapshot of the stored vehicles as a domain collection."""
        return VehicleCatalog(self.all())

    def search(self, criteria: SearchCriteria) -> list[Vehicle]:
        return list(self.catalog().filter(criteria))

    def search_by_brand(self, brand: str) -> list[Vehicle]:
        return self.search(BrandCriteria(brand))

    def search_by_model(self, model: str) -> list[Vehicle]:
        return self.search(ModelCriteria(model))

    def search_by_text(self, query: str) -> list[Vehicle]:
        return self.search(BrandOrModelCriteria(query))

    def filter_by_year(self, year: int) -> list[Vehicle]:
        return self.search(YearCriteria(year))

    def most_expensive(self) -> Vehicle | None:
        return self.catalog().most_expensive()

    def average_price(self) -> Money:
        return self.catalog().average_price()

    def lowest_mileage(self) -> Vehicle | None:
        return self.catalog().lowest_mileage()

    def sorted_by_price(self, descending: bool = True) -> list[Vehicle]:
        return self.catalog().sorted_by_price(descending)

    def statistics(self) -> CatalogStatistics:
        catalog = self.catalog()
        expensive = catalog.most_expensive()
        lowest = catalog.lowest_mileage()
        return CatalogStatistics(
            count=len(catalog),
            total_value=catalog.total_value(),
            average_price=catalog.average_price(),
            most_expensive=(
                VehicleSummary.from_vehicle(expensive) if expensive else None
            ),
            lowest_mileage=(
                VehicleSummary.from_vehicle(lowest) if lowest else None
            ),
        )

    # Alternative names for the same use cases.
    add_car = add_vehicle
    find_most_expensive = most_expensive
    calculate_average_price = average_price
    find_lowest_mileage = lowest_mileage
    min_mileage = lowest_mileage
