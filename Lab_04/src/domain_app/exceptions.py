"""Custom exception hierarchy of the vehicle catalog."""


class CatalogError(Exception):
    """Base class for all domain errors."""


class ValidationError(CatalogError, ValueError):
    """Raised when domain data violates an invariant.

    It also inherits from ValueError, so generic ``except ValueError``
    handlers and ``pytest.raises(ValueError)`` keep working.
    """


class InvalidPayloadError(ValidationError):
    """Raised when an external payload has a wrong structure."""


class EntityNotFoundError(CatalogError, LookupError):
    """Raised when an entity with the given id does not exist."""


class DuplicateEntityError(CatalogError):
    """Raised when an entity with the same id already exists."""
