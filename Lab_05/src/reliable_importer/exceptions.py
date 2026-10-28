"""Custom exception hierarchy of the importer.

ApplicationError
├── ConfigurationError
└── DataError
    ├── DataImportError
    ├── RecordValidationError
    └── DataExportError
"""


class ApplicationError(Exception):
    """Base application exception."""


class ConfigurationError(ApplicationError):
    """Configuration is missing or invalid."""


class DataError(ApplicationError):
    """Base class of all data-related errors."""


class DataImportError(DataError):
    """Input data cannot be read or has a wrong structure."""


class RecordValidationError(DataError):
    """A single record is invalid (carries the line and the field)."""

    def __init__(
        self,
        message: str,
        *,
        line_number: int | None = None,
        field: str | None = None,
    ) -> None:
        super().__init__(message)
        self.line_number = line_number
        self.field = field


class DataExportError(DataError):
    """Output cannot be written."""
