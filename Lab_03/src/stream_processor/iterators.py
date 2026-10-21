"""Custom iterator classes (iterator protocol: __iter__ / __next__)."""

import csv
from pathlib import Path

from stream_processor.filters import validate_row
from stream_processor.models import CarRecord


class NumberRangeIterator:
    """Iterator: keeps its position, raises StopIteration at the end."""

    def __init__(self, start: int, stop: int) -> None:
        self.current = start
        self.stop = stop

    def __iter__(self) -> "NumberRangeIterator":
        return self

    def __next__(self) -> int:
        if self.current >= self.stop:
            raise StopIteration
        value = self.current
        self.current += 1
        return value


class NumberRange:
    """Iterable: every iter() call returns a new independent iterator."""

    def __init__(self, start: int, stop: int) -> None:
        self.start = start
        self.stop = stop

    def __iter__(self) -> NumberRangeIterator:
        return NumberRangeIterator(self.start, self.stop)


class CarFileIterator:
    """Iterator over validated cars of a CSV file (reads the file lazily)."""

    def __init__(self, path: Path) -> None:
        self._file = path.open("r", encoding="utf-8", newline="")
        self._reader = csv.DictReader(self._file)

    def __iter__(self) -> "CarFileIterator":
        return self

    def __next__(self) -> CarRecord:
        for row in self._reader:
            record = validate_row(row)
            if record is not None:
                return record
        self.close()
        raise StopIteration

    def close(self) -> None:
        """Release the file resource (also called when the data ends)."""
        if not self._file.closed:
            self._file.close()


class CarFile:
    """Re-usable iterable: each `for` loop opens the file again."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def __iter__(self) -> CarFileIterator:
        return CarFileIterator(self.path)


NumberIterator = NumberRangeIterator
