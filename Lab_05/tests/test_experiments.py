"""The experiments of the laboratory work (small sizes)."""

from pathlib import Path

from reliable_importer.experiments import (
    atomic_output,
    configuration_errors,
    eager_import,
    exception_chain,
    generate_csv,
    streaming_import,
    streaming_vs_eager,
    strict_vs_tolerant,
)


def test_strict_vs_tolerant(tmp_path: Path) -> None:
    results = strict_vs_tolerant(tmp_path)
    strict, tolerant = results["strict"], results["tolerant"]
    assert (strict["processed"], strict["exported"]) == (101, 0)
    assert strict["output_created"] is False and "line 102" in str(
        strict["ending"]
    )
    assert (tolerant["processed"], tolerant["valid"]) == (1010, 1000)
    assert tolerant["invalid"] == 10 and tolerant["exported"] == 1000


def test_streaming_and_eager_agree(tmp_path: Path) -> None:
    rows = streaming_vs_eager(tmp_path, (500,))
    assert (
        rows[0]["same_count"] is True and rows[0]["pipeline_exported"] == 500
    )
    path = tmp_path / "x.csv"
    generate_csv(path, 50)
    assert list(streaming_import(path)) == eager_import(path)
    stream_peak = float(str(rows[0]["stream_peak_mb"]))
    eager_peak = float(str(rows[0]["eager_peak_mb"]))
    assert stream_peak < eager_peak


def test_exception_chain(tmp_path: Path) -> None:
    result = exception_chain(tmp_path)
    assert result["error"] == "RecordValidationError: Invalid price"
    assert str(result["cause"]).startswith("ValueError: could not convert")
    assert (result["line"], result["field"]) == (2, "price")


def test_atomic_output_experiment(tmp_path: Path) -> None:
    result = atomic_output(tmp_path)
    assert result["good_exit"] == 0 and result["strict_exit"] == 1
    assert result["previous_output_intact"] is True
    assert result["output_intact_after_oserror"] is True
    assert result["tmp_files_left"] == []
    assert result["logged_application_error"] is True
    assert "OSError" in str(result["export_cause"])


def test_configuration_errors(tmp_path: Path) -> None:
    rows = {row["scenario"]: row for row in configuration_errors(tmp_path)}
    assert len(rows) == 6
    failing = [r for r in rows.values() if r["exit_code"] == "1"]
    assert len(failing) == 5
    assert rows["output directory does not exist"]["exit_code"] == "0"
    assert "Years must be between" in rows["maximum_year = 3000"]["message"]
    assert (tmp_path / "new" / "sub" / "dir" / "result.json").exists()
