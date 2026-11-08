"""Request and response models of the REST API (pydantic)."""

from pydantic import BaseModel, ConfigDict, Field

from car_catalog.config import MAX_YEAR, MIN_YEAR
from car_catalog.orm_models import CarEntity, Manufacturer


class ManufacturerCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100, examples=["Toyota"])
    country: str | None = Field(
        default=None, max_length=100, examples=["Japan"]
    )


class ManufacturerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    country: str | None


class CarCreate(BaseModel):
    manufacturer_id: int = Field(ge=1)
    model: str = Field(min_length=1, max_length=100, examples=["Camry"])
    year: int = Field(ge=MIN_YEAR, le=MAX_YEAR, examples=[2020])
    price: float = Field(ge=0, allow_inf_nan=False, examples=[21500.0])
    mileage: int = Field(ge=0, examples=[45000])
    vin: str | None = Field(
        default=None, max_length=17, examples=["4T1BF1FK5HU000001"]
    )


class CarUpdate(BaseModel):
    """Only the price and the mileage can be changed."""

    price: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    mileage: int | None = Field(default=None, ge=0)


class CarOut(BaseModel):
    id: int
    manufacturer_id: int
    manufacturer: str
    model: str
    year: int
    price: float
    mileage: int
    vin: str | None

    @classmethod
    def from_entity(cls, entity: CarEntity) -> "CarOut":
        return cls(
            id=entity.id,
            manufacturer_id=entity.manufacturer_id,
            manufacturer=entity.manufacturer.name,
            model=entity.model,
            year=entity.year,
            price=entity.price,
            mileage=entity.mileage,
            vin=entity.vin,
        )


class ManufacturerStatsOut(BaseModel):
    manufacturer: str
    cars: int
    average_price: float


class StatisticsOut(BaseModel):
    count: int
    total_price: float
    average_price: float
    min_price: float
    max_price: float
    manufacturers: list[ManufacturerStatsOut]


class AveragePriceOut(BaseModel):
    count: int
    average_price: float


class HealthOut(BaseModel):
    status: str
    version: str
    environment: str
    database: str


def manufacturer_out(manufacturer: Manufacturer) -> ManufacturerOut:
    return ManufacturerOut.model_validate(manufacturer)
