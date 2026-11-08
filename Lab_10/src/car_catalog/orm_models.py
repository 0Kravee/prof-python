"""SQLAlchemy ORM models: tables ``manufacturers`` and ``cars``."""

from __future__ import annotations

from sqlalchemy import (
    CheckConstraint,
    Float,
    ForeignKey,
    Integer,
    MetaData,
    String,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
)

from car_catalog.config import MAX_YEAR, MIN_YEAR
from car_catalog.models import Car

# Stable constraint names make migrations (and their downgrade) possible.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class Manufacturer(Base):
    """A car manufacturer (the brand of the Lab_01 catalog)."""

    __tablename__ = "manufacturers"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    country: Mapped[str | None] = mapped_column(String(100), nullable=True)

    cars: Mapped[list[CarEntity]] = relationship(
        back_populates="manufacturer",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="CarEntity.id",
    )

    def __repr__(self) -> str:
        return f"Manufacturer(id={self.id}, name={self.name!r})"


class CarEntity(Base):
    """One car: many cars belong to one manufacturer."""

    __tablename__ = "cars"
    __table_args__ = (
        CheckConstraint(
            f"year BETWEEN {MIN_YEAR} AND {MAX_YEAR}", name="year_range"
        ),
        CheckConstraint("price >= 0", name="price_not_negative"),
        CheckConstraint("mileage >= 0", name="mileage_not_negative"),
    )

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    manufacturer_id: Mapped[int] = mapped_column(
        ForeignKey("manufacturers.id", ondelete="CASCADE"),
        nullable=False,
    )
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    price: Mapped[float] = mapped_column(Float, nullable=False)
    mileage: Mapped[int] = mapped_column(Integer, nullable=False)
    # added by migration 0002
    vin: Mapped[str | None] = mapped_column(
        String(17), unique=True, nullable=True
    )

    manufacturer: Mapped[Manufacturer] = relationship(back_populates="cars")

    def to_domain(self) -> Car:
        """Convert the row to the Lab_01 dataclass (used by old functions)."""
        return Car(
            brand=self.manufacturer.name,
            model=self.model,
            year=self.year,
            price=self.price,
            mileage=self.mileage,
        )

    def __repr__(self) -> str:
        return f"CarEntity(id={self.id}, model={self.model!r})"
