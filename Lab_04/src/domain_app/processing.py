"""Research: the same behaviour built with inheritance and composition.

Behaviour: turn text lines ``brand,model,year,price,mileage`` into short
descriptions, skipping invalid lines.
"""

from abc import ABC, abstractmethod
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class RawVehicle:
    brand: str
    model: str
    year: int
    price: float
    mileage: int


def _split(line: str, delimiter: str) -> RawVehicle | None:
    parts = [part.strip() for part in line.split(delimiter)]
    if len(parts) != 5:
        return None
    try:
        return RawVehicle(
            parts[0], parts[1], int(parts[2]), float(parts[3]), int(parts[4])
        )
    except ValueError:
        return None


# --------------------------------------------------------------- inheritance
class BaseProcessor(ABC):
    """Template method: the algorithm is fixed, the steps are overridden."""

    def process(self, lines: Iterable[str]) -> list[str]:
        result: list[str] = []
        for line in lines:
            record = self.parse(line)
            if record is not None and self.validate(record):
                result.append(self.format(record))
        return result

    @abstractmethod
    def parse(self, line: str) -> RawVehicle | None:
        """Turn a line into a record (None for a broken line)."""

    def validate(self, record: RawVehicle) -> bool:
        return record.price > 0

    def format(self, record: RawVehicle) -> str:
        return f"{record.brand} {record.model} ({record.year})"


class CsvProcessor(BaseProcessor):
    delimiter = ","

    def parse(self, line: str) -> RawVehicle | None:
        return _split(line, self.delimiter)


class SemicolonProcessor(CsvProcessor):
    delimiter = ";"


class RecentCsvProcessor(CsvProcessor):
    def validate(self, record: RawVehicle) -> bool:
        return super().validate(record) and record.year >= 2020


# --------------------------------------------------------------- composition
class Parser(Protocol):
    def parse(self, line: str) -> RawVehicle | None: ...


class Validator(Protocol):
    def is_valid(self, record: RawVehicle) -> bool: ...


class Formatter(Protocol):
    def format(self, record: RawVehicle) -> str: ...


class DelimiterParser:
    def __init__(self, delimiter: str = ",") -> None:
        self._delimiter = delimiter

    def parse(self, line: str) -> RawVehicle | None:
        return _split(line, self._delimiter)


class PositivePriceValidator:
    def is_valid(self, record: RawVehicle) -> bool:
        return record.price > 0


class MinYearValidator:
    def __init__(self, min_year: int) -> None:
        self._min_year = min_year

    def is_valid(self, record: RawVehicle) -> bool:
        return record.price > 0 and record.year >= self._min_year


class TitleFormatter:
    def format(self, record: RawVehicle) -> str:
        return f"{record.brand} {record.model} ({record.year})"


class PriceFormatter:
    def format(self, record: RawVehicle) -> str:
        return f"{record.brand} {record.model}: {record.price:.2f}"


class Processor:
    """Has-a Parser, Validator and Formatter; any of them can be replaced."""

    def __init__(
        self, parser: Parser, validator: Validator, formatter: Formatter
    ) -> None:
        self._parser = parser
        self._validator = validator
        self._formatter = formatter

    def process(self, lines: Iterable[str]) -> list[str]:
        result: list[str] = []
        for line in lines:
            record = self._parser.parse(line)
            if record is not None and self._validator.is_valid(record):
                result.append(self._formatter.format(record))
        return result
