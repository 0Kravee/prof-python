"""FastAPI application: REST endpoints of the car catalog."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from time import perf_counter
from typing import Annotated, Any

import httpx
from fastapi import APIRouter, FastAPI, Query, Request, Response, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from pydantic import ValidationError

from car_catalog import __version__
from car_catalog.config import MAX_YEAR, MIN_YEAR, Settings
from car_catalog.database import Database
from car_catalog.dependencies import HttpClientDep, ServiceDep, SettingsDep
from car_catalog.exceptions import (
    BatchTimeoutError,
    CatalogError,
    ConflictError,
    DuplicateEntityError,
    EntityNotFoundError,
    InvalidQueryError,
)
from car_catalog.external_api import FetchSettings, fetch_many
from car_catalog.models import Car, Manufacturer
from car_catalog.repositories import CarFilter
from car_catalog.schemas import (
    ApiInfo,
    BatchFailure,
    BatchRequest,
    BatchResponse,
    CarCreate,
    CarResponse,
    CarStatistics,
    CarUpdate,
    ErrorResponse,
    HealthResponse,
    ManufacturerCreate,
    ManufacturerResponse,
    SortField,
    SortOrder,
)

TAGS = [
    {"name": "system", "description": "Service information and health."},
    {"name": "cars", "description": "Cars of the catalog (CRUD, search)."},
    {
        "name": "manufacturers",
        "description": "Manufacturers and the cars they produce.",
    },
    {
        "name": "batch",
        "description": "Concurrent loading of many cars through HTTP.",
    },
]

DESCRIPTION = """
REST API of the car catalog (variant 5).

* **cars** - CRUD, search by brand/model, filtering by year/price,
  sorting, pagination, statistics;
* **manufacturers** - manufacturers and their cars;
* **batch** - loads many cars concurrently with `httpx.AsyncClient`,
  `asyncio.Task`, `asyncio.gather`, a `Semaphore`, timeout and retry.
"""

Responses = dict[int | str, dict[str, Any]]

SUMMARIES = {
    "root": "Service information",
    "health": "Health check",
    "list_manufacturers": "List manufacturers",
    "create_manufacturer": "Create a manufacturer",
    "get_manufacturer": "Get a manufacturer",
    "delete_manufacturer": "Delete a manufacturer without cars",
    "get_manufacturer_cars": "Cars of a manufacturer",
    "list_cars": "Search, filter, sort and paginate cars",
    "get_most_expensive": "The most expensive car",
    "get_lowest_mileage": "The car with the lowest mileage",
    "get_statistics": "Catalog statistics",
    "get_car": "Get a car",
    "create_car": "Create a car",
    "update_car": "Change price, mileage, model or year",
    "delete_car": "Delete a car",
    "batch_cars": "Load many cars concurrently through HTTPX",
}

NOT_FOUND: Responses = {404: {"model": ErrorResponse}}
CONFLICT: Responses = {409: {"model": ErrorResponse}}
TIMEOUT: Responses = {504: {"model": ErrorResponse}}

system_router = APIRouter(tags=["system"])
manufacturers_router = APIRouter(tags=["manufacturers"])
cars_router = APIRouter(tags=["cars"])
batch_router = APIRouter(tags=["batch"])


# ------------------------------------------------------------------ system
@system_router.get("/", response_model=ApiInfo, summary="Service info")
async def root() -> ApiInfo:
    return ApiInfo(name="Car Catalog API", version=__version__, docs="/docs")


@system_router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(status="ok")


# ------------------------------------------------------------ manufacturers
@manufacturers_router.get(
    "/manufacturers", response_model=list[ManufacturerResponse]
)
def list_manufacturers(service: ServiceDep) -> list[Manufacturer]:
    return service.list_manufacturers()


@manufacturers_router.post(
    "/manufacturers",
    response_model=ManufacturerResponse,
    status_code=status.HTTP_201_CREATED,
    responses=CONFLICT,
)
def create_manufacturer(
    data: ManufacturerCreate, service: ServiceDep
) -> Manufacturer:
    return service.create_manufacturer(data)


@manufacturers_router.get(
    "/manufacturers/{manufacturer_id}",
    response_model=ManufacturerResponse,
    responses=NOT_FOUND,
)
def get_manufacturer(
    manufacturer_id: int, service: ServiceDep
) -> Manufacturer:
    return service.get_manufacturer(manufacturer_id)


@manufacturers_router.delete(
    "/manufacturers/{manufacturer_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={**NOT_FOUND, **CONFLICT},
)
def delete_manufacturer(manufacturer_id: int, service: ServiceDep) -> None:
    service.delete_manufacturer(manufacturer_id)


@manufacturers_router.get(
    "/manufacturers/{manufacturer_id}/cars",
    response_model=list[CarResponse],
    responses=NOT_FOUND,
)
def get_manufacturer_cars(
    manufacturer_id: int, service: ServiceDep
) -> list[Car]:
    return service.cars_of_manufacturer(manufacturer_id)


# -------------------------------------------------------------------- cars
@cars_router.get("/cars", response_model=list[CarResponse])
def list_cars(
    service: ServiceDep,
    response: Response,
    brand: Annotated[str | None, Query(description="Brand (exact)")] = None,
    model: Annotated[
        str | None, Query(description="Part of the model name")
    ] = None,
    year: Annotated[int | None, Query(ge=MIN_YEAR, le=MAX_YEAR)] = None,
    min_year: Annotated[int | None, Query(ge=MIN_YEAR, le=MAX_YEAR)] = None,
    max_year: Annotated[int | None, Query(ge=MIN_YEAR, le=MAX_YEAR)] = None,
    min_price: Annotated[float | None, Query(ge=0)] = None,
    max_price: Annotated[float | None, Query(ge=0)] = None,
    max_mileage: Annotated[int | None, Query(ge=0)] = None,
    sort: SortField = "id",
    order: SortOrder = "asc",
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[Car]:
    """Search, filter, sort and paginate cars.

    The total number of matches is returned in the `X-Total-Count` header.
    """
    if min_year is not None and max_year is not None and min_year > max_year:
        raise InvalidQueryError("min_year must not exceed max_year")
    if (
        min_price is not None
        and max_price is not None
        and min_price > max_price
    ):
        raise InvalidQueryError("min_price must not exceed max_price")
    criteria = CarFilter(
        brand=brand,
        model=model,
        year=year,
        min_year=min_year,
        max_year=max_year,
        min_price=min_price,
        max_price=max_price,
        max_mileage=max_mileage,
    )
    cars, total = service.search(
        criteria,
        sort=sort,
        descending=order == "desc",
        limit=limit,
        offset=offset,
    )
    response.headers["X-Total-Count"] = str(total)
    return cars


# fixed paths must be declared before "/cars/{car_id}"
@cars_router.get(
    "/cars/most-expensive", response_model=CarResponse, responses=NOT_FOUND
)
def get_most_expensive(service: ServiceDep) -> Car:
    return service.most_expensive()


@cars_router.get(
    "/cars/lowest-mileage", response_model=CarResponse, responses=NOT_FOUND
)
def get_lowest_mileage(service: ServiceDep) -> Car:
    return service.lowest_mileage()


@cars_router.get("/cars/statistics", response_model=CarStatistics)
def get_statistics(service: ServiceDep) -> CarStatistics:
    return service.statistics()


@cars_router.get(
    "/cars/{car_id}", response_model=CarResponse, responses=NOT_FOUND
)
def get_car(car_id: int, service: ServiceDep) -> Car:
    return service.get_car(car_id)


@cars_router.post(
    "/cars",
    response_model=CarResponse,
    status_code=status.HTTP_201_CREATED,
    responses={**NOT_FOUND, **CONFLICT},
)
def create_car(data: CarCreate, service: ServiceDep) -> Car:
    return service.create_car(data)


@cars_router.patch(
    "/cars/{car_id}", response_model=CarResponse, responses=NOT_FOUND
)
def update_car(car_id: int, data: CarUpdate, service: ServiceDep) -> Car:
    return service.update_car(car_id, data)


@cars_router.delete(
    "/cars/{car_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=NOT_FOUND,
)
def delete_car(car_id: int, service: ServiceDep) -> None:
    service.delete_car(car_id)


# ------------------------------------------------------------------- batch
@batch_router.post(
    "/cars/batch",
    response_model=BatchResponse,
    responses=TIMEOUT,
)
async def batch_cars(
    payload: BatchRequest, client: HttpClientDep, settings: SettingsDep
) -> BatchResponse:
    """Load many cars concurrently (Task + gather + Semaphore + retry).

    Each car is requested from the REST API itself with `httpx`. One
    missing or failing car does not break the batch: it is reported in
    `missing` or `failed`. The whole batch is limited by a timeout (504).
    """
    car_ids = list(dict.fromkeys(payload.ids))
    if len(car_ids) > settings.max_batch_size:
        raise InvalidQueryError(
            f"a batch may contain at most {settings.max_batch_size} cars"
        )
    started = perf_counter()
    results = await fetch_many(
        client, car_ids, FetchSettings.from_settings(settings)
    )
    found: list[CarResponse] = []
    missing: list[int] = []
    failed: list[BatchFailure] = []
    for result in results:
        if result.status == "not_found":
            missing.append(result.car_id)
        elif result.status == "ok":
            try:
                found.append(CarResponse.model_validate(result.data))
            except ValidationError:
                failed.append(
                    BatchFailure(
                        id=result.car_id,
                        reason="invalid payload from upstream",
                        attempts=result.attempts,
                    )
                )
        else:
            failed.append(
                BatchFailure(
                    id=result.car_id,
                    reason=result.error or "unknown error",
                    attempts=result.attempts,
                )
            )
    return BatchResponse(
        requested=len(car_ids),
        found=found,
        missing=missing,
        failed=failed,
        duration_seconds=round(perf_counter() - started, 4),
    )


# ------------------------------------------------------- error handling
def error_response(
    status_code: int, detail: object, code: str
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=jsonable_encoder({"detail": detail, "code": code}),
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Every error leaves the API as ``{"detail": ..., "code": ...}``."""

    @app.exception_handler(EntityNotFoundError)
    async def not_found(
        _: Request, error: EntityNotFoundError
    ) -> JSONResponse:
        return error_response(404, str(error), error.code)

    @app.exception_handler(DuplicateEntityError)
    async def duplicate(
        _: Request, error: DuplicateEntityError
    ) -> JSONResponse:
        return error_response(409, str(error), error.code)

    @app.exception_handler(ConflictError)
    async def conflict(_: Request, error: ConflictError) -> JSONResponse:
        return error_response(409, str(error), error.code)

    @app.exception_handler(InvalidQueryError)
    async def invalid_query(
        _: Request, error: InvalidQueryError
    ) -> JSONResponse:
        return error_response(422, str(error), error.code)

    @app.exception_handler(BatchTimeoutError)
    async def batch_timeout(
        _: Request, error: BatchTimeoutError
    ) -> JSONResponse:
        return error_response(504, str(error), error.code)

    @app.exception_handler(CatalogError)
    async def catalog_error(_: Request, error: CatalogError) -> JSONResponse:
        return error_response(400, str(error), error.code)

    @app.exception_handler(RequestValidationError)
    async def validation_error(
        _: Request, error: RequestValidationError
    ) -> JSONResponse:
        return error_response(422, error.errors(), "validation_error")


def apply_summaries(*routers: APIRouter) -> None:
    """Give every endpoint a readable title in Swagger UI."""
    for router in routers:
        for route in router.routes:
            if isinstance(route, APIRoute) and route.name in SUMMARIES:
                route.summary = SUMMARIES[route.name]


# ------------------------------------------------------------ application
def create_app(
    settings: Settings | None = None, database: Database | None = None
) -> FastAPI:
    """Application factory: every dependency can be replaced in tests."""
    settings = settings if settings is not None else Settings.from_env()
    database = (
        database if database is not None else Database(settings.database_url)
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        database.ensure_schema()
        yield
        client: httpx.AsyncClient | None = app.state.http_client
        if client is not None:  # lifecycle management of the HTTP client
            await client.aclose()
            app.state.http_client = None
        database.dispose()

    app = FastAPI(
        title="Car Catalog API",
        version=__version__,
        description=DESCRIPTION,
        openapi_tags=TAGS,
        contact={"name": "Kravets Vladyslav, group FEP-31"},
        license_info={"name": "MIT"},
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.database = database
    app.state.http_client = None
    register_exception_handlers(app)
    for router in (
        system_router,
        manufacturers_router,
        batch_router,  # POST /cars/batch before the generic /cars routes
        cars_router,
    ):
        app.include_router(router)
    apply_summaries(
        system_router, manufacturers_router, batch_router, cars_router
    )
    return app


app = create_app()
