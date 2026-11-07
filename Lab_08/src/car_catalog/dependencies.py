"""FastAPI dependencies: settings, database session, service, HTTP client."""

from collections.abc import Iterator
from typing import Annotated

import httpx
from fastapi import Depends, FastAPI, Request
from sqlalchemy.orm import Session

from car_catalog.config import Settings
from car_catalog.database import Database
from car_catalog.services import CatalogService


def get_settings(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


def get_database(request: Request) -> Database:
    database: Database = request.app.state.database
    return database


def get_session(
    database: Annotated[Database, Depends(get_database)],
) -> Iterator[Session]:
    """One database session per request; always closed afterwards."""
    yield from database.session()


def get_service(
    session: Annotated[Session, Depends(get_session)],
) -> CatalogService:
    return CatalogService(session)


def build_http_client(app: FastAPI, settings: Settings) -> httpx.AsyncClient:
    """Create the shared AsyncClient used by the batch endpoint.

    Without ``api_base_url`` the client talks to this very application
    through the ASGI transport (a real HTTP request/response cycle, but
    in-process); with it, requests go over the network.
    """
    timeout = httpx.Timeout(settings.request_timeout)
    if settings.api_base_url:
        return httpx.AsyncClient(
            base_url=settings.api_base_url, timeout=timeout
        )
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://catalog.local",
        timeout=timeout,
    )


async def get_http_client(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
) -> httpx.AsyncClient:
    """Return the application-wide AsyncClient (created on first use).

    The client is reused between requests (connection pooling) and is
    closed by the application lifespan on shutdown.
    """
    client: httpx.AsyncClient | None = request.app.state.http_client
    if client is None:
        client = build_http_client(request.app, settings)
        request.app.state.http_client = client
    return client


SettingsDep = Annotated[Settings, Depends(get_settings)]
ServiceDep = Annotated[CatalogService, Depends(get_service)]
HttpClientDep = Annotated[httpx.AsyncClient, Depends(get_http_client)]
