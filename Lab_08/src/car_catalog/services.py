"""Service layer: use cases and business rules on top of repositories."""

from sqlalchemy.orm import Session

from car_catalog.exceptions import ConflictError, EntityNotFoundError
from car_catalog.models import Car, Manufacturer
from car_catalog.repositories import (
    CarFilter,
    CarRepository,
    ManufacturerRepository,
)
from car_catalog.schemas import (
    CarCreate,
    CarResponse,
    CarStatistics,
    CarUpdate,
    ManufacturerCreate,
    SortField,
)


class CatalogService:
    """Coordinates the repositories; knows nothing about HTTP."""

    def __init__(self, session: Session) -> None:
        self.manufacturers = ManufacturerRepository(session)
        self.cars = CarRepository(session)

    # ------------------------------------------------------ manufacturers
    def list_manufacturers(self) -> list[Manufacturer]:
        return self.manufacturers.get_all()

    def get_manufacturer(self, manufacturer_id: int) -> Manufacturer:
        manufacturer = self.manufacturers.get_by_id(manufacturer_id)
        if manufacturer is None:
            raise EntityNotFoundError("Manufacturer", manufacturer_id)
        return manufacturer

    def create_manufacturer(self, data: ManufacturerCreate) -> Manufacturer:
        return self.manufacturers.add(
            Manufacturer(name=data.name, country=data.country)
        )

    def delete_manufacturer(self, manufacturer_id: int) -> None:
        manufacturer = self.get_manufacturer(manufacturer_id)
        if self.manufacturers.count_cars(manufacturer_id):
            raise ConflictError(
                f"Manufacturer {manufacturer_id} still has cars"
            )
        self.manufacturers.delete(manufacturer)

    def cars_of_manufacturer(self, manufacturer_id: int) -> list[Car]:
        self.get_manufacturer(manufacturer_id)
        return self.cars.get_by_manufacturer(manufacturer_id)

    # --------------------------------------------------------------- cars
    def _resolve_manufacturer(self, data: CarCreate) -> Manufacturer:
        if data.manufacturer_id is not None:
            return self.get_manufacturer(data.manufacturer_id)
        assert data.brand is not None  # guaranteed by the schema
        existing = self.manufacturers.get_by_name(data.brand)
        if existing is not None:
            return existing
        return self.manufacturers.add(Manufacturer(name=data.brand))

    def create_car(self, data: CarCreate) -> Car:
        manufacturer = self._resolve_manufacturer(data)
        car = Car(
            manufacturer_id=manufacturer.id,
            model=data.model,
            year=data.year,
            price=data.price,
            mileage=data.mileage,
        )
        return self.cars.add(car)

    def get_car(self, car_id: int) -> Car:
        car = self.cars.get_by_id(car_id)
        if car is None:
            raise EntityNotFoundError("Car", car_id)
        return car

    def update_car(self, car_id: int, data: CarUpdate) -> Car:
        car = self.get_car(car_id)
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(car, field, value)
        return self.cars.save(car)

    def delete_car(self, car_id: int) -> None:
        self.cars.delete(self.get_car(car_id))

    def search(
        self,
        criteria: CarFilter,
        *,
        sort: SortField = "id",
        descending: bool = False,
        limit: int | None = None,
        offset: int = 0,
    ) -> tuple[list[Car], int]:
        """Return one page of cars and the total number of matches."""
        items = self.cars.get_all(
            criteria,
            sort=sort,
            descending=descending,
            limit=limit,
            offset=offset,
        )
        return items, self.cars.count(criteria)

    def most_expensive(self) -> Car:
        car = self.cars.most_expensive()
        if car is None:
            raise EntityNotFoundError("Car", "(catalog is empty)")
        return car

    def lowest_mileage(self) -> Car:
        car = self.cars.lowest_mileage()
        if car is None:
            raise EntityNotFoundError("Car", "(catalog is empty)")
        return car

    def statistics(self) -> CarStatistics:
        totals = self.cars.aggregates()
        expensive = self.cars.most_expensive()
        lowest = self.cars.lowest_mileage()
        return CarStatistics(
            count=totals.count,
            average_price=totals.average_price,
            min_price=totals.min_price,
            max_price=totals.max_price,
            total_value=totals.total_value,
            most_expensive=(
                CarResponse.model_validate(expensive) if expensive else None
            ),
            lowest_mileage=(
                CarResponse.model_validate(lowest) if lowest else None
            ),
        )
