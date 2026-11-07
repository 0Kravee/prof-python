"""Domain exceptions (mapped to HTTP status codes in api.py)."""


class CatalogError(Exception):
    """Base class of all domain errors."""

    code = "catalog_error"


class EntityNotFoundError(CatalogError):
    """The requested resource does not exist (HTTP 404)."""

    code = "not_found"

    def __init__(self, resource: str, identifier: object) -> None:
        super().__init__(f"{resource} {identifier} not found")
        self.resource = resource
        self.identifier = identifier


class DuplicateEntityError(CatalogError):
    """A resource with the same unique value already exists (HTTP 409)."""

    code = "duplicate"


class ConflictError(CatalogError):
    """The operation conflicts with the current state (HTTP 409)."""

    code = "conflict"


class BatchTimeoutError(CatalogError):
    """The whole batch did not finish in time (HTTP 504)."""

    code = "batch_timeout"


class InvalidQueryError(CatalogError):
    """Query parameters contradict each other (HTTP 422)."""

    code = "invalid_query"
