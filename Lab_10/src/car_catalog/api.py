"""REST API of the car catalog (FastAPI).

Run with ``uvicorn car_catalog.api:create_app --factory`` or with the
``car-catalog-api`` command. Interactive documentation: ``/docs``.
"""

import logging
import secrets
import time
from collections.abc import AsyncIterator, Callable, Iterator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import (
    Depends,
    FastAPI,
    Header,
    HTTPException,
    Query,
    Request,
    Response,
    status,
)
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from car_catalog import __version__
from car_catalog.config import Settings
from car_catalog.database import (
    create_db_engine,
    create_session_factory,
    init_db,
)
from car_catalog.db_services import CarDatabaseService
from car_catalog.exceptions import (
    DuplicateRecordError,
    InvalidCarDataError,
    InvalidQueryError,
    RecordNotFoundError,
)
from car_catalog.logging_config import configure_logging
from car_catalog.schemas import (
    AveragePriceOut,
    CarCreate,
    CarOut,
    CarUpdate,
    HealthOut,
    ManufacturerCreate,
    ManufacturerOut,
    ManufacturerStatsOut,
    StatisticsOut,
    manufacturer_out,
)

logger = logging.getLogger(__name__)

DESCRIPTION = """
Catalog of cars and manufacturers (laboratory works 1 - 10).

* read endpoints are open;
* `POST`, `PATCH` and `DELETE` require the `X-API-Key` header when the
  `API_KEY` environment variable is set.
"""


def get_session(request: Request) -> Iterator[Session]:
    factory: sessionmaker[Session] = request.app.state.session_factory
    with factory() as session:
        yield session


def get_service(
    request: Request, session: Annotated[Session, Depends(get_session)]
) -> CarDatabaseService:
    return CarDatabaseService(session)


Service = Annotated[CarDatabaseService, Depends(get_service)]


def require_api_key(
    request: Request,
    x_api_key: Annotated[str | None, Header()] = None,
) -> None:
    """Protect the changing endpoints when an API key is configured."""
    settings: Settings = request.app.state.settings
    if settings.api_key is None:
        return
    expected = settings.api_key.get_secret_value()
    if x_api_key is None or not secrets.compare_digest(
        x_api_key.encode(), expected.encode()
    ):
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "Invalid or missing API key"
        )


Protected = Depends(require_api_key)


def create_app(settings: Settings | None = None) -> FastAPI:
    """Application factory: every call builds an independent application."""
    settings = settings or Settings()
    configure_logging(settings.log_level, settings.app_env)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        engine = create_db_engine(settings.database_url)
        if settings.auto_create_tables:
            init_db(engine)
        app.state.settings = settings
        app.state.engine = engine
        app.state.session_factory = create_session_factory(engine)
        logger.info("Application started: %s", settings.summary())
        if settings.is_production and settings.api_key is None:
            logger.warning(
                "API_KEY is not set: changing endpoints are not protected"
            )
        yield
        engine.dispose()
        logger.info("Application stopped")

    app = FastAPI(
        title="Car Catalog API",
        version=__version__,
        description=DESCRIPTION,
        lifespan=lifespan,
    )
    # the settings are also available before the start-up (used by tests)
    app.state.settings = settings

    @app.middleware("http")
    async def log_requests(
        request: Request, call_next: Callable[[Request], object]
    ) -> Response:
        started = time.perf_counter()
        response: Response = await call_next(request)  # type: ignore[misc]
        logger.info(
            "%s %s -> %d (%.1f ms)",
            request.method,
            request.url.path,
            response.status_code,
            (time.perf_counter() - started) * 1000,
        )
        return response

    def error_handler(code: int) -> Callable[..., JSONResponse]:
        def handle(request: Request, exc: Exception) -> JSONResponse:
            return JSONResponse({"detail": str(exc)}, status_code=code)

        return handle

    app.add_exception_handler(
        RecordNotFoundError, error_handler(status.HTTP_404_NOT_FOUND)
    )
    app.add_exception_handler(
        DuplicateRecordError, error_handler(status.HTTP_409_CONFLICT)
    )
    for error in (InvalidCarDataError, InvalidQueryError):
        app.add_exception_handler(error, error_handler(422))

    # --- health ----------------------------------------------------------

    @app.get("/health", response_model=HealthOut, tags=["service"])
    def health(request: Request, response: Response) -> HealthOut:
        """Liveness and database check (used by the Docker HEALTHCHECK)."""
        factory: sessionmaker[Session] = request.app.state.session_factory
        database = "ok"
        try:
            with factory() as session:
                session.execute(text("SELECT 1 FROM manufacturers LIMIT 1"))
        except SQLAlchemyError:
            logger.exception("Health check: database is not available")
            database = "unavailable"
            response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return HealthOut(
            status="ok" if database == "ok" else "error",
            version=__version__,
            environment=settings.app_env,
            database=database,
        )

    # --- manufacturers ---------------------------------------------------

    @app.get(
        "/manufacturers",
        response_model=list[ManufacturerOut],
        tags=["manufacturers"],
    )
    def list_manufacturers(service: Service) -> list[ManufacturerOut]:
        return [manufacturer_out(m) for m in service.manufacturers.list_all()]

    @app.post(
        "/manufacturers",
        response_model=ManufacturerOut,
        status_code=status.HTTP_201_CREATED,
        dependencies=[Protected],
        tags=["manufacturers"],
    )
    def create_manufacturer(
        body: ManufacturerCreate, service: Service
    ) -> ManufacturerOut:
        return manufacturer_out(
            service.add_manufacturer(body.name, body.country)
        )

    @app.get(
        "/manufacturers/{manufacturer_id}",
        response_model=ManufacturerOut,
        tags=["manufacturers"],
    )
    def get_manufacturer(
        manufacturer_id: int, service: Service
    ) -> ManufacturerOut:
        return manufacturer_out(service.manufacturers.get(manufacturer_id))

    @app.get(
        "/manufacturers/{manufacturer_id}/cars",
        response_model=list[CarOut],
        tags=["manufacturers"],
    )
    def list_manufacturer_cars(
        manufacturer_id: int, service: Service
    ) -> list[CarOut]:
        manufacturer = service.manufacturers.get(manufacturer_id)
        return [CarOut.from_entity(car) for car in manufacturer.cars]

    # --- statistics and the Lab_01 operations --------------------------------

    @app.get("/statistics", response_model=StatisticsOut, tags=["statistics"])
    def statistics(service: Service) -> StatisticsOut:
        totals = service.cars.statistics()
        return StatisticsOut(
            count=int(totals["count"]),
            total_price=totals["total_price"],
            average_price=totals["average_price"],
            min_price=totals["min_price"],
            max_price=totals["max_price"],
            manufacturers=[
                ManufacturerStatsOut(
                    manufacturer=name, cars=count, average_price=average
                )
                for name, count, average in (
                    service.cars.stats_by_manufacturer()
                )
            ],
        )

    @app.get("/cars/most-expensive", response_model=CarOut, tags=["cars"])
    def most_expensive(service: Service) -> CarOut:
        car = service.most_expensive()
        if car is None:
            raise RecordNotFoundError("The catalog is empty")
        return CarOut.from_entity(car)

    @app.get("/cars/lowest-mileage", response_model=CarOut, tags=["cars"])
    def lowest_mileage(service: Service) -> CarOut:
        car = service.lowest_mileage()
        if car is None:
            raise RecordNotFoundError("The catalog is empty")
        return CarOut.from_entity(car)

    @app.get(
        "/cars/average-price", response_model=AveragePriceOut, tags=["cars"]
    )
    def average_price(service: Service) -> AveragePriceOut:
        return AveragePriceOut(
            count=service.cars.count(), average_price=service.average_price()
        )

    # --- cars ------------------------------------------------------------

    @app.get("/cars", response_model=list[CarOut], tags=["cars"])
    def list_cars(
        service: Service,
        brand: str | None = None,
        model: str | None = None,
        year: Annotated[int | None, Query(ge=1)] = None,
        min_year: int | None = None,
        max_year: int | None = None,
        min_price: Annotated[float | None, Query(ge=0)] = None,
        max_price: Annotated[float | None, Query(ge=0)] = None,
        max_mileage: Annotated[int | None, Query(ge=0)] = None,
        sort_by: str = "id",
        descending: bool = False,
        limit: Annotated[int, Query(ge=1, le=1000)] = 50,
        offset: Annotated[int, Query(ge=0)] = 0,
    ) -> list[CarOut]:
        """Search by brand/model, filter by year, price and mileage."""
        if year is not None:
            min_year = max_year = year
        cars = service.cars.search(
            brand=brand,
            model=model,
            min_year=min_year,
            max_year=max_year,
            min_price=min_price,
            max_price=max_price,
            max_mileage=max_mileage,
            sort_by=sort_by,
            descending=descending,
            limit=limit,
            offset=offset,
        )
        return [CarOut.from_entity(car) for car in cars]

    @app.post(
        "/cars",
        response_model=CarOut,
        status_code=status.HTTP_201_CREATED,
        dependencies=[Protected],
        tags=["cars"],
    )
    def create_car(body: CarCreate, service: Service) -> CarOut:
        manufacturer = service.manufacturers.get(body.manufacturer_id)
        car = service.add_car(
            manufacturer.name,
            body.model,
            body.year,
            body.price,
            body.mileage,
            body.vin,
        )
        return CarOut.from_entity(car)

    @app.get("/cars/{car_id}", response_model=CarOut, tags=["cars"])
    def get_car(car_id: int, service: Service) -> CarOut:
        return CarOut.from_entity(service.get_car(car_id))

    @app.patch(
        "/cars/{car_id}",
        response_model=CarOut,
        dependencies=[Protected],
        tags=["cars"],
    )
    def update_car(car_id: int, body: CarUpdate, service: Service) -> CarOut:
        car = service.get_car(car_id)
        if body.price is not None:
            car = service.update_price(car_id, body.price)
        if body.mileage is not None:
            car = service.update_mileage(car_id, body.mileage)
        return CarOut.from_entity(car)

    @app.delete(
        "/cars/{car_id}",
        status_code=status.HTTP_204_NO_CONTENT,
        dependencies=[Protected],
        tags=["cars"],
    )
    def delete_car(car_id: int, service: Service) -> Response:
        service.delete_car(car_id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    return app
