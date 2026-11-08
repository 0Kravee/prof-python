"""Repository implementations.

``InMemoryVehicleRepository`` keeps cars in a list (Lab_06 tests).
``ManufacturerRepository`` and ``CarRepository`` are the persistence
layer on top of SQLAlchemy ORM and SQLite (Lab_07). They only ``flush``;
committing or rolling back is the job of the service layer.
"""

from collections.abc import Iterable
from typing import Any

from sqlalchemy import Select, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from car_catalog.exceptions import (
    CarNotFoundError,
    DuplicateRecordError,
    InvalidCarDataError,
    InvalidQueryError,
    RecordNotFoundError,
)
from car_catalog.models import Car
from car_catalog.orm_models import CarEntity, Manufacturer
from car_catalog.validators import normalize_vin


class InMemoryVehicleRepository:
    """Simple list-backed repository (also used as a fake in tests)."""

    def __init__(self, cars: Iterable[Car] | None = None) -> None:
        self._cars: list[Car] = list(cars) if cars is not None else []

    def __len__(self) -> int:
        return len(self._cars)

    def add(self, car: Car) -> None:
        self._cars.append(car)

    def list_all(self) -> list[Car]:
        """Return a copy, so callers cannot change the storage."""
        return list(self._cars)

    def remove(self, brand: str, model: str) -> Car:
        for index, car in enumerate(self._cars):
            if (
                car.brand.lower() == brand.strip().lower()
                and car.model.lower() == model.strip().lower()
            ):
                return self._cars.pop(index)
        raise CarNotFoundError(f"Car {brand} {model} was not found")


SORT_FIELDS: dict[str, Any] = {
    "id": CarEntity.id,
    "model": CarEntity.model,
    "year": CarEntity.year,
    "price": CarEntity.price,
    "mileage": CarEntity.mileage,
}


def _flush_new(
    session: Session, entity: object, duplicate_message: str
) -> None:
    """Insert inside a SAVEPOINT and translate constraint errors.

    The SAVEPOINT keeps the outer transaction usable after a failure.
    """
    try:
        with session.begin_nested():
            session.add(entity)
    except IntegrityError as exc:
        reason = str(exc.orig)
        if "UNIQUE" in reason:
            raise DuplicateRecordError(duplicate_message) from exc
        if "FOREIGN KEY" in reason:
            raise RecordNotFoundError("Manufacturer does not exist") from exc
        raise InvalidCarDataError(reason) from exc


class ManufacturerRepository:
    """Persistence of manufacturers."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, name: str, country: str | None = None) -> Manufacturer:
        clean = name.strip() if isinstance(name, str) else ""
        if not clean:
            raise InvalidCarDataError("Manufacturer name must not be empty")
        if self.get_by_name(clean) is not None:
            raise DuplicateRecordError(f"Manufacturer {clean} already exists")
        manufacturer = Manufacturer(name=clean, country=country)
        _flush_new(
            self.session, manufacturer, f"Manufacturer {clean} already exists"
        )
        return manufacturer

    def get(self, manufacturer_id: int) -> Manufacturer:
        manufacturer = self.session.get(Manufacturer, manufacturer_id)
        if manufacturer is None:
            raise RecordNotFoundError(
                f"Manufacturer {manufacturer_id} was not found"
            )
        return manufacturer

    def get_by_name(self, name: str) -> Manufacturer | None:
        statement = select(Manufacturer).where(
            func.lower(Manufacturer.name) == name.strip().lower()
        )
        return self.session.scalar(statement)

    def require_by_name(self, name: str) -> Manufacturer:
        manufacturer = self.get_by_name(name)
        if manufacturer is None:
            raise RecordNotFoundError(f"Manufacturer {name} was not found")
        return manufacturer

    def list_all(self) -> list[Manufacturer]:
        statement = select(Manufacturer).order_by(Manufacturer.name)
        return list(self.session.scalars(statement))

    def update_country(
        self, manufacturer_id: int, country: str | None
    ) -> Manufacturer:
        manufacturer = self.get(manufacturer_id)
        manufacturer.country = country
        self.session.flush()
        return manufacturer

    def delete(self, manufacturer_id: int) -> None:
        """Delete the manufacturer; its cars are deleted with it."""
        self.session.delete(self.get(manufacturer_id))
        self.session.flush()

    def count_cars(self, manufacturer_id: int) -> int:
        statement = select(func.count(CarEntity.id)).where(
            CarEntity.manufacturer_id == manufacturer_id
        )
        return int(self.session.scalar(statement) or 0)


class CarRepository:
    """Persistence of cars (CRUD, search, aggregates)."""

    def __init__(self, session: Session) -> None:
        self.session = session

    # --- Create -------------------------------------------------------

    def add(
        self,
        manufacturer: Manufacturer,
        model: str,
        year: int,
        price: float,
        mileage: int,
        vin: str | None = None,
    ) -> CarEntity:
        # the Lab_01 dataclass validates the values for us
        car = Car(manufacturer.name, model, year, price, mileage)
        clean_vin = normalize_vin(vin) if vin is not None else None
        entity = CarEntity(
            manufacturer_id=manufacturer.id,
            model=car.model,
            year=car.year,
            price=car.price,
            mileage=car.mileage,
            vin=clean_vin,
        )
        _flush_new(
            self.session, entity, f"A car with VIN {clean_vin} already exists"
        )
        self.session.refresh(entity)
        return entity

    # --- Read ---------------------------------------------------------

    def _select(self) -> Select[Any]:
        return select(CarEntity).options(joinedload(CarEntity.manufacturer))

    def get(self, car_id: int) -> CarEntity:
        entity: CarEntity | None = self.session.scalar(
            self._select().where(CarEntity.id == car_id)
        )
        if entity is None:
            raise RecordNotFoundError(f"Car {car_id} was not found")
        return entity

    def list_all(self) -> list[CarEntity]:
        return list(
            self.session.scalars(self._select().order_by(CarEntity.id))
        )

    def count(self) -> int:
        return int(self.session.scalar(select(func.count(CarEntity.id))) or 0)

    def find_by_brand(self, brand: str) -> list[CarEntity]:
        """Case-insensitive search by manufacturer name (Lab_01)."""
        statement = (
            self._select()
            .join(CarEntity.manufacturer)
            .where(func.lower(Manufacturer.name) == brand.strip().lower())
            .order_by(CarEntity.id)
        )
        return list(self.session.scalars(statement))

    def find_by_model(self, model: str) -> list[CarEntity]:
        statement = (
            self._select()
            .where(func.lower(CarEntity.model) == model.strip().lower())
            .order_by(CarEntity.id)
        )
        return list(self.session.scalars(statement))

    def filter_by_year(self, year: int) -> list[CarEntity]:
        statement = (
            self._select().where(CarEntity.year == year).order_by(CarEntity.id)
        )
        return list(self.session.scalars(statement))

    def find_by_vin(self, vin: str) -> CarEntity | None:
        statement = self._select().where(CarEntity.vin == normalize_vin(vin))
        found: CarEntity | None = self.session.scalar(statement)
        return found

    def search(
        self,
        brand: str | None = None,
        model: str | None = None,
        min_year: int | None = None,
        max_year: int | None = None,
        min_price: float | None = None,
        max_price: float | None = None,
        max_mileage: int | None = None,
        sort_by: str = "id",
        descending: bool = False,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[CarEntity]:
        """Several criteria + sorting + pagination."""
        if sort_by not in SORT_FIELDS:
            raise InvalidQueryError(f"Cannot sort by {sort_by!r}")
        if offset < 0 or (limit is not None and limit < 0):
            raise InvalidQueryError("limit and offset must not be negative")
        statement = self._select().join(CarEntity.manufacturer)
        if brand is not None:
            statement = statement.where(
                func.lower(Manufacturer.name) == brand.strip().lower()
            )
        if model is not None:
            statement = statement.where(
                func.lower(CarEntity.model) == model.strip().lower()
            )
        if min_year is not None:
            statement = statement.where(CarEntity.year >= min_year)
        if max_year is not None:
            statement = statement.where(CarEntity.year <= max_year)
        if min_price is not None:
            statement = statement.where(CarEntity.price >= min_price)
        if max_price is not None:
            statement = statement.where(CarEntity.price <= max_price)
        if max_mileage is not None:
            statement = statement.where(CarEntity.mileage <= max_mileage)
        column = SORT_FIELDS[sort_by]
        order = column.desc() if descending else column.asc()
        statement = statement.order_by(order, CarEntity.id).offset(offset)
        if limit is not None:
            statement = statement.limit(limit)
        return list(self.session.scalars(statement))

    # --- Aggregates (Lab_01 functions, now in SQL) --------------------

    def most_expensive(self) -> CarEntity | None:
        statement = (
            self._select()
            .order_by(CarEntity.price.desc(), CarEntity.id)
            .limit(1)
        )
        found: CarEntity | None = self.session.scalar(statement)
        return found

    def lowest_mileage(self) -> CarEntity | None:
        statement = (
            self._select().order_by(CarEntity.mileage, CarEntity.id).limit(1)
        )
        found: CarEntity | None = self.session.scalar(statement)
        return found

    def average_price(self) -> float:
        result = self.session.scalar(select(func.avg(CarEntity.price)))
        return 0.0 if result is None else float(result)

    def statistics(self) -> dict[str, float]:
        """COUNT, SUM, AVG, MIN and MAX of the price in one query."""
        row = self.session.execute(
            select(
                func.count(CarEntity.id),
                func.sum(CarEntity.price),
                func.avg(CarEntity.price),
                func.min(CarEntity.price),
                func.max(CarEntity.price),
            )
        ).one()
        count, total, average, lowest, highest = row
        return {
            "count": int(count),
            "total_price": float(total or 0.0),
            "average_price": float(average or 0.0),
            "min_price": float(lowest or 0.0),
            "max_price": float(highest or 0.0),
        }

    def stats_by_manufacturer(self) -> list[tuple[str, int, float]]:
        """JOIN + GROUP BY: (manufacturer, number of cars, average price)."""
        statement = (
            select(
                Manufacturer.name,
                func.count(CarEntity.id),
                func.avg(CarEntity.price),
            )
            .join(CarEntity, CarEntity.manufacturer_id == Manufacturer.id)
            .group_by(Manufacturer.id, Manufacturer.name)
            .order_by(Manufacturer.name)
        )
        return [
            (name, int(count), float(average))
            for name, count, average in self.session.execute(statement)
        ]

    # --- Update -------------------------------------------------------

    def _revalidate(self, entity: CarEntity, **changes: Any) -> None:
        values: dict[str, Any] = {
            "brand": entity.manufacturer.name,
            "model": entity.model,
            "year": entity.year,
            "price": entity.price,
            "mileage": entity.mileage,
        }
        values.update(changes)
        Car(**values)  # raises InvalidCarDataError for bad values

    def update_price(self, car_id: int, price: float) -> CarEntity:
        entity = self.get(car_id)
        self._revalidate(entity, price=price)
        entity.price = float(price)
        self.session.flush()
        return entity

    def update_mileage(self, car_id: int, mileage: int) -> CarEntity:
        entity = self.get(car_id)
        self._revalidate(entity, mileage=mileage)
        entity.mileage = mileage
        self.session.flush()
        return entity

    def set_vin(self, car_id: int, vin: str) -> CarEntity:
        entity = self.get(car_id)
        clean = normalize_vin(vin)
        try:
            with self.session.begin_nested():
                entity.vin = clean
        except IntegrityError as exc:
            raise DuplicateRecordError(
                f"A car with VIN {clean} already exists"
            ) from exc
        return entity

    # --- Delete -------------------------------------------------------

    def delete(self, car_id: int) -> None:
        self.session.delete(self.get(car_id))
        self.session.flush()
