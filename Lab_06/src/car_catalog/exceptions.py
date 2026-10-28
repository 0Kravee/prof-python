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


class ConfigurationError(CarCatalogError, ValueError):
    """Raised when the application configuration is invalid."""


class CarImportError(CarCatalogError):
    """Raised when a CSV file cannot be imported.

    ``line_number`` is the 1-based line of the broken record (the header
    is line 1); it is None for file-level problems.
    """

    def __init__(self, message: str, line_number: int | None = None) -> None:
        super().__init__(message)
        self.line_number = line_number


class ExportError(CarCatalogError):
    """Raised when the catalog cannot be written to a file."""


class ExternalServiceError(CarCatalogError):
    """Raised when an external dependency (vehicle info service) fails."""
