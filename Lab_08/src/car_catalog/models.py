"""SQLAlchemy ORM models of the car catalog."""

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from car_catalog.config import MAX_YEAR, MIN_YEAR
from car_catalog.database import Base


class Manufacturer(Base):
    __tablename__ = "manufacturers"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    country: Mapped[str | None] = mapped_column(String(100), default=None)

    cars: Mapped[list["Car"]] = relationship(
        back_populates="manufacturer", order_by="Car.id"
    )

    def __repr__(self) -> str:
        return f"Manufacturer(id={self.id}, name={self.name!r})"


# manufacturer names are unique regardless of the letter case
Index("uq_manufacturers_name_ci", func.lower(Manufacturer.name), unique=True)


class Car(Base):
    __tablename__ = "cars"
    __table_args__ = (
        CheckConstraint(
            f"year >= {MIN_YEAR} AND year <= {MAX_YEAR}", name="ck_cars_year"
        ),
        CheckConstraint("price >= 0", name="ck_cars_price"),
        CheckConstraint("mileage >= 0", name="ck_cars_mileage"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    manufacturer_id: Mapped[int] = mapped_column(
        ForeignKey("manufacturers.id", ondelete="RESTRICT"), index=True
    )
    model: Mapped[str] = mapped_column(String(100))
    year: Mapped[int]
    price: Mapped[float]
    mileage: Mapped[int]

    manufacturer: Mapped[Manufacturer] = relationship(
        back_populates="cars", lazy="joined"
    )

    @property
    def brand(self) -> str:
        """The brand of a car is the name of its manufacturer."""
        return self.manufacturer.name

    def __repr__(self) -> str:
        return f"Car(id={self.id}, {self.brand} {self.model} {self.year})"
