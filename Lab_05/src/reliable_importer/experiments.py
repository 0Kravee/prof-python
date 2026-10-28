"""Experiments of the laboratory work (strict/tolerant, streaming, ...).

Run:  python -m reliable_importer.experiments [--quick]
"""

import contextlib
import csv
import io
import logging
import random
import sys
import tempfile
import traceback
import tracemalloc
from collections.abc import Callable, Iterator
from dataclasses import replace
from pathlib import Path
from time import perf_counter
from typing import TypeVar

# Allows running this file directly without installing the package.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from reliable_importer.config import load_config  # noqa: E402
from reliable_importer.exceptions import (  # noqa: E402
    ApplicationError,
    DataExportError,
    RecordValidationError,
)
from reliable_importer.exporters import JsonExporter  # noqa: E402
from reliable_importer.importers import CsvImporter  # noqa: E402
from reliable_importer.main import main as run_application  # noqa: E402
from reliable_importer.models import Vehicle  # noqa: E402
from reliable_importer.readers import REQUIRED_COLUMNS  # noqa: E402
from reliable_importer.services import (  # noqa: E402
    ImportStatistics,
    import_vehicles,
    run_import,
)

T = TypeVar("T")

BRANDS = {
    "Toyota": ("Camry", "Corolla", "RAV4"),
    "BMW": ("X5", "3 Series", "i4"),
    "Audi": ("A4", "A6", "Q7"),
    "Skoda": ("Octavia", "Superb"),
    "Tesla": ("Model 3", "Model Y"),
}

CONFIG_TEMPLATE = """\
schema_version: 1
input:
  path: {input}
output:
  path: {output}
  errors_path: {errors}
processing:
  skip_invalid: {skip}
  minimum_year: 1990
  maximum_year: 2026
  minimum_price: 0
  maximum_price: 200000
logging:
  level: INFO
  path: {log}
"""


def generate_csv(
    path: Path, rows: int, *, invalid_every: int = 0, seed: int = 42
) -> None:
    """Write a synthetic vehicle CSV; every N-th row has a broken price."""
    rng = random.Random(seed)
    brands = list(BRANDS)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(REQUIRED_COLUMNS)
        for index in range(1, rows + 1):
            brand = rng.choice(brands)
            price: object = round(rng.uniform(2000, 150000), 2)
            if invalid_every and index % invalid_every == 0:
                price = "error"
            writer.writerow(
                [
                    index,
                    brand,
                    rng.choice(BRANDS[brand]),
                    rng.randint(1995, 2025),
                    price,
                    rng.randint(0, 250_000),
                ]
            )


def write_config(
    folder: Path,
    *,
    skip: bool = True,
    input_name: str = "vehicles.csv",
    output_name: str = "result.json",
    extra: str = "",
) -> Path:
    config_path = folder / "config.yaml"
    text = CONFIG_TEMPLATE.format(
        input=input_name,
        output=output_name,
        errors="errors.csv",
        skip=str(skip).lower(),
        log="app.log",
    )
    config_path.write_text(text + extra, encoding="utf-8")
    return config_path


@contextlib.contextmanager
def quiet_logging() -> Iterator[None]:
    """Silence logging while a measurement is running."""
    logging.disable(logging.CRITICAL)
    try:
        yield
    finally:
        logging.disable(logging.NOTSET)


def timed(function: Callable[[], T]) -> tuple[T, float]:
    start = perf_counter()
    result = function()
    return result, perf_counter() - start


def peak_memory(function: Callable[[], T]) -> tuple[T, int]:
    tracemalloc.start()
    try:
        result = function()
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    return result, peak


# -------------------------------------------- experiment 1: strict/tolerant
def strict_vs_tolerant(folder: Path) -> dict[str, dict[str, object]]:
    """1000 valid + 10 invalid records processed in both modes."""
    source = folder / "vehicles.csv"
    generate_csv(source, 1010, invalid_every=101)  # rows 101, 202, ... 1010
    results: dict[str, dict[str, object]] = {}
    for mode, skip in (("strict", False), ("tolerant", True)):
        config = load_config(
            write_config(folder, skip=skip, output_name=f"{mode}.json")
        )
        statistics = ImportStatistics()
        with quiet_logging():
            try:
                run_import(config, statistics)
                ending = "finished normally, exit code 0"
            except RecordValidationError as error:
                ending = (
                    f"aborted at line {error.line_number} "
                    f"({error}), exit code 1"
                )
        results[mode] = {
            "processed": statistics.total,
            "valid": statistics.valid,
            "invalid": statistics.invalid,
            "exported": statistics.exported,
            "output_created": (folder / f"{mode}.json").exists(),
            "ending": ending,
        }
    return results


# ------------------------------------------ experiment 2: streaming vs eager
def eager_import(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as file:
        return list(csv.DictReader(file))


def streaming_import(path: Path) -> Iterator[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as file:
        yield from csv.DictReader(file)


def _consume_eager(path: Path) -> int:
    return len(eager_import(path))


def _consume_streaming(path: Path) -> int:
    count = 0
    for _ in streaming_import(path):
        count += 1
    return count


def _full_pipeline(path: Path, output: Path) -> int:
    config = load_config(
        write_config(
            path.parent, input_name=path.name, output_name=output.name
        )
    )
    return run_import(replace(config)).statistics.exported


def streaming_vs_eager(
    folder: Path, sizes: tuple[int, ...]
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for size in sizes:
        path = folder / f"cars_{size}.csv"
        generate_csv(path, size, invalid_every=1000)
        with quiet_logging():
            eager_count, eager_time = timed(lambda: _consume_eager(path))
            stream_count, stream_time = timed(lambda: _consume_streaming(path))
            _, eager_peak = peak_memory(lambda: _consume_eager(path))
            _, stream_peak = peak_memory(lambda: _consume_streaming(path))
            output = folder / f"pipeline_{size}.json"
            exported, pipeline_time = timed(
                lambda: _full_pipeline(path, output)
            )
            _, pipeline_peak = peak_memory(
                lambda: _full_pipeline(path, output)
            )
        rows.append(
            {
                "records": size,
                "same_count": eager_count == stream_count == size,
                "eager_time": eager_time,
                "stream_time": stream_time,
                "eager_peak_mb": eager_peak / 1024 / 1024,
                "stream_peak_mb": stream_peak / 1024 / 1024,
                "pipeline_exported": exported,
                "pipeline_time": pipeline_time,
                "pipeline_peak_mb": pipeline_peak / 1024 / 1024,
            }
        )
    return rows


# --------------------------------------- experiment 3: exception chaining
def exception_chain(folder: Path) -> dict[str, object]:
    """Non-numeric price: ValueError -> RecordValidationError."""
    source = folder / "wrong.csv"
    source.write_text(
        "vehicle_id,brand,model,year,price,mileage\n"
        "1,Toyota,Camry,2019,wrong,45000\n",
        encoding="utf-8",
    )
    config = load_config(
        write_config(folder, skip=False, input_name="wrong.csv")
    )
    statistics = ImportStatistics()
    with quiet_logging():
        try:
            list(
                import_vehicles(
                    CsvImporter(),
                    source,
                    skip_invalid=False,
                    rules=config.processing.rules,
                    statistics=statistics,
                )
            )
        except RecordValidationError as error:
            text = "".join(traceback.format_exception(error))
            cause = error.__cause__
            return {
                "traceback": text.rstrip().splitlines(),
                "error": f"{type(error).__name__}: {error}",
                "cause": (
                    f"{type(cause).__name__}: {cause}" if cause else None
                ),
                "line": error.line_number,
                "field": error.field,
            }
    raise AssertionError("the record must be rejected")


# ------------------------------------------- experiment 4: atomic output
def _failing_vehicles() -> Iterator[Vehicle]:
    yield Vehicle(1, "Toyota", "Camry", 2019, 21500.0, 45000)
    yield Vehicle(2, "BMW", "X5", 2021, 48200.0, 18000)
    raise OSError("No space left on device (simulated)")


def atomic_output(folder: Path) -> dict[str, object]:
    """Failures during export must not damage the previous good output."""
    source = folder / "vehicles.csv"
    generate_csv(source, 20)
    config_path = write_config(folder, output_name="production.json")
    production = folder / "production.json"
    log_path = folder / "app.log"

    with contextlib.redirect_stderr(io.StringIO()):
        good_exit = run_application(["--config", str(config_path)])
    good_bytes = production.read_bytes()

    # (a) strict mode aborts in the middle of the export
    broken = folder / "broken.csv"
    broken.write_text(
        source.read_text(encoding="utf-8") + "21,Audi,A4,2018,oops,1\n",
        encoding="utf-8",
    )
    strict_config = write_config(
        folder,
        skip=False,
        input_name="broken.csv",
        output_name="production.json",
    )
    with contextlib.redirect_stderr(io.StringIO()):
        strict_exit = run_application(["--config", str(strict_config)])
    log_text = log_path.read_text(encoding="utf-8")

    # (b) the disk fails while writing (simulated OSError)
    export_error: str | None = None
    export_cause: str | None = None
    try:
        JsonExporter().export(_failing_vehicles(), production)
    except DataExportError as error:
        message = str(error.args[0]).replace(str(folder), "<tmp>")
        export_error = f"{type(error).__name__}: {message}"
        export_cause = repr(error.__cause__)

    return {
        "good_exit": good_exit,
        "strict_exit": strict_exit,
        "previous_output_intact": production.read_bytes() == good_bytes,
        "tmp_files_left": sorted(p.name for p in folder.glob("*.tmp")),
        "logged_application_error": "Application error" in log_text,
        "export_error": export_error,
        "export_cause": export_cause,
        "output_intact_after_oserror": production.read_bytes() == good_bytes,
    }


# ------------------------------------- experiment 5: configuration errors
def configuration_errors(folder: Path) -> list[dict[str, str]]:
    source = folder / "vehicles.csv"
    generate_csv(source, 5)
    scenarios: list[tuple[str, Path]] = []

    scenarios.append(("missing config.yaml", folder / "does_not_exist.yaml"))

    bad_yaml = folder / "bad_yaml.yaml"
    bad_yaml.write_text("input: [unclosed\n", encoding="utf-8")
    scenarios.append(("invalid YAML", bad_yaml))

    no_input = folder / "no_input.yaml"
    full = write_config(folder).read_text(encoding="utf-8")
    no_input.write_text(
        full.replace("input:\n  path: vehicles.csv\n", ""), encoding="utf-8"
    )
    scenarios.append(("no 'input' key", no_input))

    bad_range = folder / "bad_range.yaml"
    bad_range.write_text(
        full.replace("maximum_year: 2026", "maximum_year: 3000"),
        encoding="utf-8",
    )
    scenarios.append(("maximum_year = 3000", bad_range))

    no_file = folder / "no_file.yaml"
    no_file.write_text(
        full.replace("path: vehicles.csv", "path: missing.csv"),
        encoding="utf-8",
    )
    scenarios.append(("input file is missing", no_file))

    new_dir = folder / "new_dir.yaml"
    new_dir.write_text(
        full.replace("path: result.json", "path: new/sub/dir/result.json"),
        encoding="utf-8",
    )
    scenarios.append(("output directory does not exist", new_dir))

    results: list[dict[str, str]] = []
    for name, config_path in scenarios:
        buffer = io.StringIO()
        with contextlib.redirect_stderr(buffer):
            code = run_application(["--config", str(config_path)])
        lines = [
            line
            for line in buffer.getvalue().splitlines()
            if "Configuration error" in line or "Application error" in line
        ]
        message = lines[0].split(": ", 1)[-1] if lines else "(no error)"
        message = message.replace(str(folder) + "/", "")
        behaviour = "controlled exit" if code else "created and finished"
        results.append(
            {
                "scenario": name,
                "exit_code": str(code),
                "message": message,
                "behaviour": behaviour,
            }
        )
    return results


# ------------------------------------------------------------------- CLI
def _print_section(title: str) -> None:
    print(f"\n=== {title} ===")


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    quick = "--quick" in args
    sizes = (10_000, 100_000) if quick else (10_000, 100_000, 500_000)
    try:
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            for index, runner in enumerate(
                (
                    _run_strict,
                    lambda folder: _run_streaming(folder, sizes),
                    _run_chain,
                    _run_atomic,
                    _run_config,
                ),
                start=1,
            ):
                folder = root / f"exp{index}"
                folder.mkdir()
                runner(folder)
    except ApplicationError as error:
        print(f"Experiment failed: {error}", file=sys.stderr)
        return 1
    return 0


def _run_strict(folder: Path) -> None:
    _print_section(
        "Experiment 1: strict vs tolerant (1000 valid + 10 invalid)"
    )
    results = strict_vs_tolerant(folder)
    for key in ("processed", "valid", "invalid", "exported"):
        print(
            f"{key:<10} strict={results['strict'][key]!s:<6} "
            f"tolerant={results['tolerant'][key]}"
        )
    for mode in ("strict", "tolerant"):
        print(
            f"{mode:<9}: output file created = "
            f"{results[mode]['output_created']}"
        )
        print(f"{mode:<9}: {results[mode]['ending']}")


def _run_streaming(folder: Path, sizes: tuple[int, ...]) -> None:
    _print_section("Experiment 2: eager vs streaming")
    rows = streaming_vs_eager(folder, sizes)
    print(
        f"{'Records':>9} {'Eager s':>9} {'Stream s':>9} "
        f"{'Eager MB':>9} {'Stream MB':>9} {'Same':>5}"
    )
    for row in rows:
        print(
            f"{row['records']:>9} {row['eager_time']:>9.3f} "
            f"{row['stream_time']:>9.3f} {row['eager_peak_mb']:>9.2f} "
            f"{row['stream_peak_mb']:>9.2f} {row['same_count']!s:>5}"
        )
    print("Full pipeline (read -> validate -> summarise -> export JSON):")
    print(f"{'Records':>9} {'Time s':>9} {'Peak MB':>9} {'Exported':>9}")
    for row in rows:
        print(
            f"{row['records']:>9} {row['pipeline_time']:>9.3f} "
            f"{row['pipeline_peak_mb']:>9.2f} {row['pipeline_exported']:>9}"
        )


def _run_chain(folder: Path) -> None:
    _print_section("Experiment 3: exception chaining")
    result = exception_chain(folder)
    for line in result["traceback"]:  # type: ignore[attr-defined]
        print(line)
    print(f"error : {result['error']}")
    print(f"cause : {result['cause']}")


def _run_atomic(folder: Path) -> None:
    _print_section("Experiment 4: atomic output")
    for key, value in atomic_output(folder).items():
        print(f"{key}: {value}")


def _run_config(folder: Path) -> None:
    _print_section("Experiment 5: configuration errors")
    for row in configuration_errors(folder):
        print(
            f"[{row['scenario']}] exit={row['exit_code']} "
            f"({row['behaviour']}): {row['message']}"
        )


if __name__ == "__main__":
    raise SystemExit(main())
