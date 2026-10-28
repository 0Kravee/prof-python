"""Exception hierarchy and exception chaining."""

import pytest

from reliable_importer.exceptions import (
    ApplicationError,
    ConfigurationError,
    DataError,
    DataExportError,
    DataImportError,
    RecordValidationError,
)
from reliable_importer.models import ValidationRules
from reliable_importer.validators import parse_vehicle


def test_hierarchy() -> None:
    assert issubclass(ConfigurationError, ApplicationError)
    assert issubclass(DataError, ApplicationError)
    for error in (DataImportError, RecordValidationError, DataExportError):
        assert issubclass(error, DataError)
    assert not issubclass(ConfigurationError, DataError)


def test_record_validation_error_carries_context() -> None:
    error = RecordValidationError("bad", line_number=7, field="price")
    assert (error.line_number, error.field, str(error)) == (7, "price", "bad")
    assert RecordValidationError("x").line_number is None


def test_specific_handlers_do_not_catch_unrelated_errors() -> None:
    with pytest.raises(ConfigurationError):
        try:
            raise ConfigurationError("config")
        except DataError:  # must not catch a configuration error
            pytest.fail("DataError handler caught ConfigurationError")


def test_chaining_keeps_the_original_cause(rules: ValidationRules) -> None:
    row = {
        "vehicle_id": "1",
        "brand": "A",
        "model": "B",
        "year": "2020",
        "price": "wrong",
        "mileage": "1",
    }
    with pytest.raises(RecordValidationError) as info:
        parse_vehicle(row, line_number=2, rules=rules)
    assert isinstance(info.value.__cause__, ValueError)
    assert "wrong" in str(info.value.__cause__)
    assert info.value.field == "price" and info.value.line_number == 2
