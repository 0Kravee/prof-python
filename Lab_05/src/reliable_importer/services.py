"""Application services: streaming import, summary, error report, pipeline."""

import csv
import json
import logging
from collections.abc import Iterable, Iterator, Mapping
from contextlib import ExitStack
from dataclasses import dataclass
from pathlib import Path
from types import TracebackType
from typing import Any, Protocol

from reliable_importer.exporters import select_exporter
from reliable_importer.exceptions import DataExportError, RecordValidationError
from reliable_importer.importers import Importer, select_importer
from reliable_importer.models import AppConfig, ValidationRules, Vehicle
from reliable_importer.utils import atomic_output, logged_operation
from reliable_importer.validators import parse_vehicle

logger = logging.getLogger(__name__)


@dataclass
class ImportStatistics:
    """Counters of the import: how many records were valid or invalid."""

    total: int = 0
    valid: int = 0
    invalid: int = 0
    exported: int = 0


class ErrorSink(Protocol):
    """Receives every rejected record (for example an error CSV)."""

    def write(
        self, error: RecordValidationError, data: Mapping[str, object]
    ) -> None: ...


def import_vehicles(
    importer: Importer,
    path: Path,
    *,
    skip_invalid: bool,
    rules: ValidationRules,
    statistics: ImportStatistics,
    error_sink: ErrorSink | None = None,
) -> Iterator[Vehicle]:
    """Streaming import: valid vehicles are produced one by one.

    tolerant mode (``skip_invalid=True``): invalid records are counted,
    logged and skipped. strict mode: the first invalid record aborts.
    """
    for row in importer.read(path):
        statistics.total += 1
        try:
            vehicle = parse_vehicle(
                row.data, line_number=row.line_number, rules=rules
            )
        except RecordValidationError as error:
            statistics.invalid += 1
            logger.warning(
                "Invalid record at line %s: %s", error.line_number, error
            )
            if error_sink is not None:
                error_sink.write(error, row.data)
            if skip_invalid:
                continue
            raise
        statistics.valid += 1
        yield vehicle


@dataclass
class SummaryAccumulator:
    """Single-pass dataset summary (no list of all vehicles is kept)."""

    count: int = 0
    total_price: float = 0.0
    most_expensive: Vehicle | None = None
    lowest_mileage: Vehicle | None = None

    def observe(self, vehicle: Vehicle) -> None:
        self.count += 1
        self.total_price += vehicle.price
        if self.most_expensive is None or vehicle.price > (
            self.most_expensive.price
        ):
            self.most_expensive = vehicle
        if self.lowest_mileage is None or vehicle.mileage < (
            self.lowest_mileage.mileage
        ):
            self.lowest_mileage = vehicle

    @property
    def average_price(self) -> float:
        return round(self.total_price / self.count, 2) if self.count else 0.0


def track(
    vehicles: Iterable[Vehicle], summary: SummaryAccumulator
) -> Iterator[Vehicle]:
    """Pass vehicles through while feeding the summary accumulator."""
    for vehicle in vehicles:
        summary.observe(vehicle)
        yield vehicle


class ErrorCsvReport:
    """Context manager that writes rejected records to an error CSV.

    The report is committed even when the processing is aborted (strict
    mode), because it documents why the run stopped.
    """

    def __init__(self, path: Path | None) -> None:
        self._path = path
        self._stack: ExitStack | None = None
        self._writer: Any = None

    def __enter__(self) -> "ErrorCsvReport":
        if self._path is not None:
            self._stack = ExitStack()
            file = self._stack.enter_context(
                atomic_output(self._path, newline="")
            )
            self._writer = csv.writer(file)
            self._writer.writerow(
                ["line_number", "field", "message", "raw_record"]
            )
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        stack, self._stack = self._stack, None
        if stack is None:
            return
        try:
            stack.close()
        except OSError as error:
            raise DataExportError(
                f"Cannot write the error report {self._path}"
            ) from error

    def write(
        self, error: RecordValidationError, data: Mapping[str, object]
    ) -> None:
        if self._writer is None:
            return
        raw = json.dumps(dict(data), ensure_ascii=False, default=str)
        self._writer.writerow(
            [error.line_number, error.field or "", str(error), raw]
        )


@dataclass
class RunResult:
    statistics: ImportStatistics
    summary: SummaryAccumulator


def run_import(
    config: AppConfig, statistics: ImportStatistics | None = None
) -> RunResult:
    """The whole pipeline: read -> validate -> summarise -> export.

    A caller may pass its own ``statistics`` object: it keeps the counters
    even when strict mode aborts the processing with an exception.
    """
    statistics = statistics if statistics is not None else ImportStatistics()
    summary = SummaryAccumulator()
    importer = select_importer(config.input.path, config.input.format)
    exporter = select_exporter(
        config.output.path,
        config.output.format,
        backup=config.output.backup_existing,
    )
    with ErrorCsvReport(config.output.errors_path) as report:
        with logged_operation("Vehicle import/export"):
            vehicles = import_vehicles(
                importer,
                config.input.path,
                skip_invalid=config.processing.skip_invalid,
                rules=config.processing.rules,
                statistics=statistics,
                error_sink=report,
            )
            statistics.exported = exporter.export(
                track(vehicles, summary), config.output.path
            )
    return RunResult(statistics, summary)
