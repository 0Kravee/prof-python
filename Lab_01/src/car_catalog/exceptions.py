"""Custom exceptions of the car catalog."""


class CarCatalogError(Exception):
    """Base class for all car catalog errors."""


class InvalidCarDataError(CarCatalogError, ValueError):
    """Raised when car data is invalid.

    It also inherits from ValueError, so generic ``except ValueError``
    handlers and ``pytest.raises(ValueError)`` keep working.
    """


class CarNotFoundError(CarCatalogError, LookupError):
    """Raised when a car cannot be found in the catalog."""
