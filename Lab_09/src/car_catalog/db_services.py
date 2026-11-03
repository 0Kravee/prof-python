"""Service layer on top of the repositories (business logic + transactions).

Persistence details stay in ``repositories.py``; this module decides when
a transaction is committed or rolled back.
"""

import math
from collections.abc import Callable
from typing import TypeVar

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from car_catalog.config import AppConfig
from car_catalog.exceptions import InvalidCarDataError
from car_catalog.models import Car
from car_catalog.orm_models import CarEntity, Manufacturer
from car_catalog.repositories import CarRepository, ManufacturerRepository
from car_catalog.validators import validate_car

T = TypeVar("T")


class CarDatabaseService:
    """Use cases of the car catalog stored in a database."""

    def __init__(
        self, session: Session, config: AppConfig | None = None
    ) -> None:
        self.session = session
        self.config = config or AppConfig()
        self.manufacturers = ManufacturerRepository(session)
        self.cars = CarRepository(session)

    def _atomic(self, action: Callable[[], T]) -> T:
        """Run ``action`` and commit; any error rolls everything back."""
        try:
            result = action()
            self.session.commit()
            return result
        except Exception:
            self.session.rollback()
            raise

    # --- manufacturers ------------------------------------------------

    def add_manufacturer(
        self, name: str, country: str | None = None
    ) -> Manufacturer:
        return self._atomic(lambda: self.manufacturers.add(name, country))

    def delete_manufacturer(self, name: str) -> None:
        def action() -> None:
            manufacturer = self.manufacturers.require_by_name(name)
            self.manufacturers.delete(manufacturer.id)

        self._atomic(action)

    # --- cars: CRUD ---------------------------------------------------

    def add_car(
        self,
        manufacturer_name: str,
        model: str,
        year: int,
        price: float,
        mileage: int,
        vin: str | None = None,
    ) -> CarEntity:
        def action() -> CarEntity:
            manufacturer = self.manufacturers.require_by_name(
                manufacturer_name
            )
            validate_car(
                Car(manufacturer.name, model, year, price, mileage),
                self.config,
            )
            return self.cars.add(
                manufacturer, model, year, price, mileage, vin
            )

        return self._atomic(action)

    def get_car(self, car_id: int) -> CarEntity:
        return self.cars.get(car_id)

    def update_price(self, car_id: int, price: float) -> CarEntity:
        def action() -> CarEntity:
            entity = self.cars.get(car_id)
            validate_car(
                Car(
                    entity.manufacturer.name,
                    entity.model,
                    entity.year,
                    price,
                    entity.mileage,
                ),
                self.config,
            )
            return self.cars.update_price(car_id, price)

        return self._atomic(action)

    def update_mileage(self, car_id: int, mileage: int) -> CarEntity:
        return self._atomic(lambda: self.cars.update_mileage(car_id, mileage))

    def delete_car(self, car_id: int) -> None:
        self._atomic(lambda: self.cars.delete(car_id))

    # --- Lab_01 functions backed by SQL ------------------------------

    def find_by_brand(self, brand: str) -> list[CarEntity]:
        return self.cars.find_by_brand(brand)

    def filter_by_year(self, year: int) -> list[CarEntity]:
        return self.cars.filter_by_year(year)

    def most_expensive(self) -> CarEntity | None:
        return self.cars.most_expensive()

    def average_price(self) -> float:
        return self.cars.average_price()

    def lowest_mileage(self) -> CarEntity | None:
        return self.cars.lowest_mileage()

    def domain_cars(self) -> list[Car]:
        """All cars as Lab_01 dataclasses (old functions still work)."""
        return [entity.to_domain() for entity in self.cars.list_all()]

    # --- transaction --------------------------------------------------

    def bulk_update_prices(
        self, manufacturer_name: str, percent: float
    ) -> int:
        """Change the price of every car of a manufacturer by ``percent``.

        All-or-nothing: if any new price is invalid, the updates that were
        already executed are rolled back and an error is raised.
        Returns the number of updated cars.
        """
        try:
            if not isinstance(percent, (int, float)) or isinstance(
                percent, bool
            ):
                raise InvalidCarDataError("Percent must be a number")
            if not math.isfinite(percent) or percent <= -100:
                raise InvalidCarDataError(
                    "Percent must be finite and greater than -100"
                )
            manufacturer = self.manufacturers.require_by_name(
                manufacturer_name
            )
            rows = self.session.execute(
                select(
                    CarEntity.id,
                    CarEntity.model,
                    CarEntity.year,
                    CarEntity.price,
                    CarEntity.mileage,
                )
                .where(CarEntity.manufacturer_id == manufacturer.id)
                .order_by(CarEntity.id)
            ).all()
            for car_id, model, year, price, mileage in rows:
                new_price = round(price * (1 + percent / 100), 2)
                validate_car(
                    Car(manufacturer.name, model, year, new_price, mileage),
                    self.config,
                )
                # executed at once: a later failure must undo it
                self.session.execute(
                    update(CarEntity)
                    .where(CarEntity.id == car_id)
                    .values(price=new_price)
                )
            self.session.commit()
            return len(rows)
        except Exception:
            self.session.rollback()
            raise
