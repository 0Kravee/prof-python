"""Pydantic schemas: request validation and response models."""

from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from car_catalog.config import MAX_YEAR, MIN_YEAR

Year = Annotated[int, Field(ge=MIN_YEAR, le=MAX_YEAR)]
Price = Annotated[float, Field(ge=0, allow_inf_nan=False)]
Mileage = Annotated[int, Field(ge=0)]
ModelName = Annotated[str, Field(min_length=1, max_length=100)]

SortField = Literal["id", "price", "year", "mileage", "model"]
SortOrder = Literal["asc", "desc"]


class StrictInput(BaseModel):
    """Base of all request bodies: trims strings, rejects unknown fields."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")


# ----------------------------------------------------------- manufacturers
class ManufacturerCreate(StrictInput):
    name: str = Field(min_length=1, max_length=100, examples=["Toyota"])
    country: str | None = Field(
        default=None, max_length=100, examples=["Japan"]
    )


class ManufacturerResponse(BaseModel):
    id: int
    name: str
    country: str | None = None

    model_config = ConfigDict(from_attributes=True)


# -------------------------------------------------------------------- cars
class CarCreate(StrictInput):
    """A car is created for an existing manufacturer or for a brand name.

    Exactly one of ``manufacturer_id`` and ``brand`` must be given; an
    unknown brand creates the manufacturer automatically.
    """

    manufacturer_id: int | None = Field(default=None, gt=0, examples=[1])
    brand: str | None = Field(
        default=None, min_length=1, max_length=100, examples=["Toyota"]
    )
    model: ModelName = Field(examples=["Camry"])
    year: Year = Field(examples=[2019])
    price: Price = Field(examples=[21500.0])
    mileage: Mileage = Field(examples=[45000])

    @model_validator(mode="after")
    def exactly_one_manufacturer_reference(self) -> Self:
        if (self.manufacturer_id is None) == (self.brand is None):
            raise ValueError(
                "provide exactly one of 'manufacturer_id' and 'brand'"
            )
        return self


class CarUpdate(StrictInput):
    """Partial update (PATCH): only the fields that are sent are changed."""

    model: ModelName | None = None
    year: Year | None = None
    price: Price | None = None
    mileage: Mileage | None = None

    @model_validator(mode="after")
    def at_least_one_field(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("at least one field must be provided")
        if any(getattr(self, name) is None for name in self.model_fields_set):
            raise ValueError("fields must not be null")
        return self


class CarResponse(BaseModel):
    id: int
    manufacturer_id: int
    brand: str
    model: str
    year: int
    price: float
    mileage: int

    model_config = ConfigDict(from_attributes=True)


class CarStatistics(BaseModel):
    count: int
    average_price: float
    min_price: float | None
    max_price: float | None
    total_value: float
    most_expensive: CarResponse | None
    lowest_mileage: CarResponse | None


# ------------------------------------------------------------------- batch
class BatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ids: list[Annotated[int, Field(gt=0)]] = Field(
        min_length=1, max_length=1000, examples=[[1, 2, 3]]
    )


class BatchFailure(BaseModel):
    id: int
    reason: str
    attempts: int


class BatchResponse(BaseModel):
    requested: int
    found: list[CarResponse]
    missing: list[int]
    failed: list[BatchFailure]
    duration_seconds: float


# ------------------------------------------------------------------ errors
class ErrorResponse(BaseModel):
    """Structured error body used by every error response."""

    detail: str | list[dict[str, object]]
    code: str


# ------------------------------------------------------------------ system
class ApiInfo(BaseModel):
    name: str
    version: str
    docs: str


class HealthResponse(BaseModel):
    status: Literal["ok"]
