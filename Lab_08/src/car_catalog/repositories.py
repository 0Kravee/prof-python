"""Repository layer: all SQL lives here."""

from dataclasses import dataclass
from typing import Any

from sqlalchemy import Select, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from car_catalog.exceptions import DuplicateEntityError
from car_catalog.models import Car, Manufacturer
from car_catalog.schemas import SortField

SORT_COLUMNS = {
    "id": Car.id,
    "price": Car.price,
    "year": Car.year,
    "mileage": Car.mileage,
    "model": Car.model,
}


@dataclass(frozen=True)
class CarFilter:
    """Search criteria; criteria that are None are ignored."""

    brand: str | None = None
    model: str | None = None
    year: int | None = None
    min_year: int | None = None
    max_year: int | None = None
    min_price: float | None = None
    max_price: float | None = None
    max_mileage: int | None = None


@dataclass(frozen=True)
class CarAggregates:
    count: int
    average_price: float
    min_price: float | None
    max_price: float | None
    total_value: float


class ManufacturerRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_all(self) -> list[Manufacturer]:
        statement = select(Manufacturer).order_by(Manufacturer.name)
        return list(self.session.scalars(statement))

    def get_by_id(self, manufacturer_id: int) -> Manufacturer | None:
        return self.session.get(Manufacturer, manufacturer_id)

    def get_by_name(self, name: str) -> Manufacturer | None:
        statement = select(Manufacturer).where(
            func.lower(Manufacturer.name) == name.strip().lower()
        )
        return self.session.scalars(statement).first()

    def add(self, manufacturer: Manufacturer) -> Manufacturer:
        self.session.add(manufacturer)
        try:
            self.session.commit()
        except IntegrityError as error:
            self.session.rollback()
            raise DuplicateEntityError(
                f"Manufacturer {manufacturer.name!r} already exists"
            ) from error
        self.session.refresh(manufacturer)
        return manufacturer

    def delete(self, manufacturer: Manufacturer) -> None:
        self.session.delete(manufacturer)
        self.session.commit()

    def count_cars(self, manufacturer_id: int) -> int:
        statement = select(func.count(Car.id)).where(
            Car.manufacturer_id == manufacturer_id
        )
        return int(self.session.scalar(statement) or 0)


class CarRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    @staticmethod
    def _filtered(statement: Select[Any], f: CarFilter) -> Select[Any]:
        if f.brand is not None:
            statement = statement.join(Manufacturer).where(
                func.lower(Manufacturer.name) == f.brand.strip().lower()
            )
        if f.model is not None:
            pattern = f"%{f.model.strip().lower()}%"
            statement = statement.where(func.lower(Car.model).like(pattern))
        if f.year is not None:
            statement = statement.where(Car.year == f.year)
        if f.min_year is not None:
            statement = statement.where(Car.year >= f.min_year)
        if f.max_year is not None:
            statement = statement.where(Car.year <= f.max_year)
        if f.min_price is not None:
            statement = statement.where(Car.price >= f.min_price)
        if f.max_price is not None:
            statement = statement.where(Car.price <= f.max_price)
        if f.max_mileage is not None:
            statement = statement.where(Car.mileage <= f.max_mileage)
        return statement

    def get_all(
        self,
        criteria: CarFilter | None = None,
        *,
        sort: SortField = "id",
        descending: bool = False,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[Car]:
        statement = self._filtered(select(Car), criteria or CarFilter())
        column = SORT_COLUMNS[sort]
        ordering = column.desc() if descending else column.asc()
        statement = statement.order_by(ordering, Car.id)
        if limit is not None:
            statement = statement.limit(limit).offset(offset)
        return list(self.session.scalars(statement).unique())

    def count(self, criteria: CarFilter | None = None) -> int:
        inner = self._filtered(select(Car.id), criteria or CarFilter())
        statement = select(func.count()).select_from(inner.subquery())
        return int(self.session.scalar(statement) or 0)

    def get_by_id(self, car_id: int) -> Car | None:
        return self.session.get(Car, car_id)

    def get_by_manufacturer(self, manufacturer_id: int) -> list[Car]:
        statement = (
            select(Car)
            .where(Car.manufacturer_id == manufacturer_id)
            .order_by(Car.id)
        )
        return list(self.session.scalars(statement).unique())

    def add(self, car: Car) -> Car:
        self.session.add(car)
        self.session.commit()
        self.session.refresh(car)
        return car

    def save(self, car: Car) -> Car:
        self.session.commit()
        self.session.refresh(car)
        return car

    def delete(self, car: Car) -> None:
        self.session.delete(car)
        self.session.commit()

    def most_expensive(self) -> Car | None:
        statement = select(Car).order_by(Car.price.desc(), Car.id).limit(1)
        return self.session.scalars(statement).unique().first()

    def lowest_mileage(self) -> Car | None:
        statement = select(Car).order_by(Car.mileage.asc(), Car.id).limit(1)
        return self.session.scalars(statement).unique().first()

    def aggregates(self) -> CarAggregates:
        row = self.session.execute(
            select(
                func.count(Car.id),
                func.avg(Car.price),
                func.min(Car.price),
                func.max(Car.price),
                func.sum(Car.price),
            )
        ).one()
        count, average, minimum, maximum, total = row
        return CarAggregates(
            count=int(count),
            average_price=round(float(average or 0.0), 2),
            min_price=None if minimum is None else float(minimum),
            max_price=None if maximum is None else float(maximum),
            total_value=round(float(total or 0.0), 2),
        )
