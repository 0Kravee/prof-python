"""Domain entities: Vehicle, Car, ElectricCar and VehicleCatalog."""

import itertools
from abc import ABC, abstractmethod
from collections.abc import Iterable, Iterator
from typing import ClassVar, TypeVar, overload

from domain_app.exceptions import (
    DuplicateEntityError,
    EntityNotFoundError,
    ValidationError,
)
from domain_app.protocols import Matcher
from domain_app.value_objects import (
    Mileage,
    MileageLike,
    Money,
    MoneyLike,
    VehicleSpecification,
)

# bound TypeVar: any subclass of Vehicle, the concrete type is preserved
VehicleT = TypeVar("VehicleT", bound="Vehicle")


class Vehicle(ABC):
    """Abstract vehicle: shared state and rules of every vehicle.

    The specification, price and mileage are held by composition (has-a),
    and the state can only be changed through validated methods.
    """

    # class-level behaviour: one id sequence shared by all instances
    _id_sequence: ClassVar[Iterator[int]] = itertools.count(1)

    def __init__(
        self,
        brand: str,
        model: str,
        year: int,
        price: MoneyLike,
        mileage: MileageLike,
        vehicle_id: int | None = None,
    ) -> None:
        if vehicle_id is not None and vehicle_id <= 0:
            raise ValidationError("Vehicle id must be positive")
        self._vehicle_id = (
            vehicle_id
            if vehicle_id is not None
            else next(Vehicle._id_sequence)
        )
        self._specification = VehicleSpecification(brand, model, year)
        self._price = Money.of(price)
        self._mileage = Mileage.of(mileage)

    @property
    def vehicle_id(self) -> int:
        return self._vehicle_id

    @property
    def id(self) -> int:
        """Alias of ``vehicle_id`` (satisfies the HasId protocol)."""
        return self._vehicle_id

    @property
    def specification(self) -> VehicleSpecification:
        return self._specification

    @property
    def brand(self) -> str:
        return self._specification.brand

    @property
    def model(self) -> str:
        return self._specification.model

    @property
    def year(self) -> int:
        return self._specification.year

    @property
    def price(self) -> Money:
        return self._price

    @price.setter
    def price(self, value: Money) -> None:
        self._price = Money.of(value)

    @property
    def mileage(self) -> Mileage:
        return self._mileage

    @mileage.setter
    def mileage(self, value: Mileage) -> None:
        new_value = Mileage.of(value)
        if new_value < self._mileage:
            raise ValidationError("Mileage cannot be decreased")
        self._mileage = new_value

    @property
    @abstractmethod
    def energy_type(self) -> str:
        """Kind of energy the vehicle uses (petrol, electric, ...)."""

    @abstractmethod
    def describe(self) -> str:
        """One-line description of the vehicle."""

    def drive(self, kilometers: int) -> None:
        """Encapsulated state change: the odometer can only grow."""
        if kilometers < 0:
            raise ValidationError("Driven distance cannot be negative")
        self._mileage = self._mileage + Mileage(kilometers)

    def reprice(self, new_price: MoneyLike) -> None:
        """Set a new price from any supported money representation."""
        self._price = Money.of(new_price)

    def apply_discount(self, percent: float) -> None:
        self._price = self._price.discounted(percent)

    def is_newer_than(self, year: int) -> bool:
        return self.year > year

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Vehicle):
            return NotImplemented
        return self._vehicle_id == other._vehicle_id

    def __hash__(self) -> int:
        return hash(self._vehicle_id)

    def __repr__(self) -> str:
        return (
            f"{type(self).__name__}(id={self._vehicle_id}, "
            f"{self._specification.title!r}, price={self._price}, "
            f"mileage={self._mileage})"
        )

    def __str__(self) -> str:
        return self.describe()


class Car(Vehicle):
    """Ordinary car (is-a Vehicle)."""

    def __init__(
        self,
        brand: str,
        model: str,
        year: int,
        price: MoneyLike,
        mileage: MileageLike,
        vehicle_id: int | None = None,
        *,
        body_type: str = "sedan",
        fuel_type: str = "petrol",
    ) -> None:
        super().__init__(brand, model, year, price, mileage, vehicle_id)
        self.body_type = body_type
        self._fuel_type = fuel_type

    @property
    def energy_type(self) -> str:
        return self._fuel_type

    def describe(self) -> str:
        return (
            f"{self.specification.title}: {self.body_type}, "
            f"{self.energy_type}, {self.mileage}, {self.price}"
        )


class ElectricCar(Car):
    """Electric car: a Car with a battery (Liskov-substitutable for Car)."""

    def __init__(
        self,
        brand: str,
        model: str,
        year: int,
        price: MoneyLike,
        mileage: MileageLike,
        vehicle_id: int | None = None,
        *,
        battery_kwh: float,
        range_km: int,
        body_type: str = "sedan",
    ) -> None:
        if battery_kwh <= 0 or range_km <= 0:
            raise ValidationError(
                "Battery capacity and range must be positive"
            )
        super().__init__(
            brand,
            model,
            year,
            price,
            mileage,
            vehicle_id,
            body_type=body_type,
            fuel_type="electric",
        )
        self.battery_kwh = battery_kwh
        self.range_km = range_km

    def describe(self) -> str:
        return (
            f"{super().describe()}, battery {self.battery_kwh:g} kWh, "
            f"range {self.range_km} km"
        )


class VehicleCatalog:
    """Custom collection of vehicles (a domain query model).

    It supports ``len()``, iteration, ``in``, indexing and slicing, and it
    knows the domain statistics: most expensive, average price, etc.
    """

    def __init__(self, vehicles: Iterable[Vehicle] = ()) -> None:
        self._vehicles: list[Vehicle] = []
        for vehicle in vehicles:
            self.add(vehicle)

    def add(self, vehicle: Vehicle) -> None:
        if vehicle in self:
            raise DuplicateEntityError(
                f"Vehicle with id {vehicle.vehicle_id} already exists"
            )
        self._vehicles.append(vehicle)

    def extend(self, vehicles: Iterable[Vehicle]) -> None:
        for vehicle in vehicles:
            self.add(vehicle)

    def remove(self, vehicle_id: int) -> Vehicle:
        vehicle = self.get(vehicle_id)
        self._vehicles.remove(vehicle)
        return vehicle

    def get(self, vehicle_id: int) -> Vehicle:
        for vehicle in self._vehicles:
            if vehicle.vehicle_id == vehicle_id:
                return vehicle
        raise EntityNotFoundError(f"Vehicle {vehicle_id} was not found")

    def __len__(self) -> int:
        return len(self._vehicles)

    def __iter__(self) -> Iterator[Vehicle]:
        return iter(self._vehicles)

    def __contains__(self, item: object) -> bool:
        if isinstance(item, Vehicle):
            return any(v.vehicle_id == item.vehicle_id for v in self._vehicles)
        if isinstance(item, int):
            return any(v.vehicle_id == item for v in self._vehicles)
        return False

    @overload
    def __getitem__(self, index: int) -> Vehicle: ...

    @overload
    def __getitem__(self, index: slice) -> list[Vehicle]: ...

    def __getitem__(self, index: int | slice) -> Vehicle | list[Vehicle]:
        return self._vehicles[index]

    def __repr__(self) -> str:
        return f"VehicleCatalog({len(self)} vehicles)"

    def filter(self, matcher: Matcher[Vehicle]) -> "VehicleCatalog":
        """New catalog with the vehicles accepted by `matcher`."""
        return VehicleCatalog(v for v in self._vehicles if matcher.matches(v))

    def of_type(self, kind: type[VehicleT]) -> list[VehicleT]:
        """Vehicles of the given class; the result keeps the exact type."""
        return [v for v in self._vehicles if isinstance(v, kind)]

    def most_expensive(self) -> Vehicle | None:
        return max(self._vehicles, key=lambda v: v.price, default=None)

    def lowest_mileage(self) -> Vehicle | None:
        return min(self._vehicles, key=lambda v: v.mileage, default=None)

    def total_value(self) -> Money:
        return Money.total(v.price for v in self._vehicles)

    def average_price(self) -> Money:
        if not self._vehicles:
            return Money.zero()
        return self.total_value() / len(self._vehicles)

    def sorted_by_price(self, descending: bool = True) -> list[Vehicle]:
        return sorted(
            self._vehicles, key=lambda v: v.price, reverse=descending
        )
