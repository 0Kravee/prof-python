"""Custom exceptions of the stream processor."""


class StreamProcessorError(Exception):
    """Base class for all stream processor errors."""


class InvalidCarDataError(StreamProcessorError, ValueError):
    """Raised when the data of a single car record is invalid.

    It also inherits from ValueError, so generic ``except ValueError``
    handlers and ``pytest.raises(ValueError)`` keep working.
    """


class InvalidBatchSizeError(StreamProcessorError, ValueError):
    """Raised when a batch size is not a positive number."""
