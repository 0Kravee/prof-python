"""Unit tests of the measuring and profiling tools."""

from pathlib import Path

import pytest

from car_catalog import profiling as prof


def busy(n: int = 20_000) -> int:
    return sum(i * i for i in range(n))


# --- time ---------------------------------------------------------------


def test_measure_runs_the_function_repeats_times() -> None:
    calls = []
    timing = prof.measure(lambda: calls.append(1), repeats=4)
    assert len(calls) == 4
    assert len(timing.runs) == 4


def test_warmup_runs_are_not_measured() -> None:
    calls = []
    timing = prof.measure(lambda: calls.append(1), repeats=3, warmup=2)
    assert len(calls) == 5
    assert len(timing.runs) == 3


def test_timing_statistics() -> None:
    timing = prof.Timing((1.0, 2.0, 3.0))
    assert timing.mean == pytest.approx(2.0)
    assert timing.minimum == 1.0
    assert timing.stdev == pytest.approx(1.0)


def test_single_run_has_zero_deviation() -> None:
    assert prof.Timing((0.5,)).stdev == 0.0


def test_measure_rejects_zero_repeats() -> None:
    with pytest.raises(ValueError):
        prof.measure(lambda: None, repeats=0)


def test_measured_times_are_positive_and_realistic() -> None:
    timing = prof.measure(busy, repeats=3)
    assert all(run > 0 for run in timing.runs)


@pytest.mark.parametrize(
    ("baseline", "other", "expected"),
    [(10.0, 5.0, 2.0), (10.0, 10.0, 1.0), (1.0, 4.0, 0.25)],
)
def test_speedup(baseline, other, expected) -> None:
    assert prof.speedup(baseline, other) == pytest.approx(expected)


def test_speedup_needs_positive_time() -> None:
    with pytest.raises(ValueError):
        prof.speedup(1.0, 0.0)


# --- cProfile -----------------------------------------------------------


def helper(x: int) -> int:
    return x * 2


def many_calls() -> None:
    for i in range(300):
        helper(i)


def test_profile_finds_the_called_function() -> None:
    report = prof.profile_call(many_calls, top=10)
    row = next(r for r in report.rows if "helper" in r.function)
    assert row.ncalls == 300
    assert row.cumtime >= row.tottime >= 0
    assert report.total_time > 0
    assert "ncalls" in report.text and "tottime" in report.text


def test_profile_rows_are_sorted_by_cumulative_time() -> None:
    report = prof.profile_call(many_calls, top=5)
    times = [row.cumtime for row in report.rows]
    assert times == sorted(times, reverse=True)
    assert len(report.rows) <= 5


def test_profile_can_sort_by_total_time() -> None:
    report = prof.profile_call(many_calls, top=5, sort="tottime")
    times = [row.tottime for row in report.rows]
    assert times == sorted(times, reverse=True)


def test_profile_propagates_errors() -> None:
    def broken() -> None:
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError):
        prof.profile_call(broken)


# --- tracemalloc ----------------------------------------------------------


def test_peak_memory_reflects_the_allocation() -> None:
    result, memory = prof.trace_memory(lambda: [0] * 1_000_000)
    assert len(result) == 1_000_000
    assert memory.peak_bytes >= 7_000_000
    assert memory.peak_mb == pytest.approx(memory.peak_bytes / 2**20)


def test_peak_is_not_smaller_than_current() -> None:
    _, memory = prof.trace_memory(lambda: list(range(100_000)))
    assert memory.peak_bytes >= memory.current_bytes > 0


def test_trace_memory_stops_tracing_afterwards() -> None:
    import tracemalloc

    prof.trace_memory(lambda: [1] * 1000)
    assert not tracemalloc.is_tracing()


def test_trace_memory_works_when_tracing_is_already_on() -> None:
    import tracemalloc

    tracemalloc.start()
    try:
        _, memory = prof.trace_memory(lambda: [0] * 200_000)
        assert memory.peak_bytes > 1_000_000
        assert tracemalloc.is_tracing()
    finally:
        tracemalloc.stop()


def test_top_allocations_lists_source_lines() -> None:
    lines = prof.top_allocations(lambda: [str(i) for i in range(50_000)], 3)
    assert 1 <= len(lines) <= 3
    assert all("test_profiling.py" in line for line in lines[:1])


# --- benchmark records ----------------------------------------------------


def record(**changes):
    values = {
        "experiment": "methods", "method": "Threads", "data_size": 1000,
        "workers": 4, "runs": (0.1, 0.2), "mean_time": 0.15,
        "stdev_time": 0.07, "peak_memory_mb": 1.5, "speedup": 0.8,
        "correct": True,
    }
    values.update(changes)
    return prof.BenchmarkRecord(**values)


def test_records_survive_a_csv_roundtrip(tmp_path: Path) -> None:
    records = [record(), record(method="NumPy", workers=0, correct=False)]
    path = prof.save_records_csv(records, tmp_path / "out" / "r.csv")
    assert prof.load_records_csv(path) == records


def test_table_contains_every_record() -> None:
    table = prof.format_records_table(
        [record(), record(method="NumPy", workers=0, speedup=12.5)]
    )
    assert "Threads" in table and "NumPy" in table
    assert "12.50" in table
    assert table.count("\n") == 3  # header, ruler, two rows
