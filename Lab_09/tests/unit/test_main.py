"""Unit tests of the console interface (input is replaced by monkeypatch)."""

import io
import sys

import pytest

from car_catalog import main as app


class FakeTerminal(io.StringIO):
    def isatty(self) -> bool:
        return True


def feed(monkeypatch: pytest.MonkeyPatch, answers: list[str]) -> None:
    iterator = iter(answers)
    monkeypatch.setattr("builtins.input", lambda _="": next(iterator))


def test_demo_cars_are_valid_and_not_empty() -> None:
    cars = app.create_demo_cars()
    assert len(cars) == 5


def test_print_cars_formats_a_table(capsys, sample_cars) -> None:
    app.print_cars(sample_cars)
    out = capsys.readouterr().out
    assert "BMW X5" in out
    assert "48200.00" in out


def test_print_cars_of_empty_list(capsys) -> None:
    app.print_cars([])
    assert "(no cars)" in capsys.readouterr().out


def test_read_line_returns_none_when_input_is_closed(monkeypatch) -> None:
    def raise_eof(_: str = "") -> str:
        raise EOFError

    monkeypatch.setattr("builtins.input", raise_eof)
    assert app.read_line("> ") is None


def test_read_number_rejects_text(monkeypatch, capsys) -> None:
    feed(monkeypatch, ["abc"])
    assert app.read_number("Year: ", int) is None
    assert "Invalid value" in capsys.readouterr().out


def test_read_new_car_builds_a_car(monkeypatch) -> None:
    feed(monkeypatch, ["Kia", "Rio", "2020", "9000", "15000"])
    car = app.read_new_car()
    assert car is not None
    assert car.full_name == "Kia Rio"


def test_read_new_car_stops_on_invalid_number(monkeypatch) -> None:
    feed(monkeypatch, ["Kia", "Rio", "year", "9000", "15000"])
    assert app.read_new_car() is None


def test_menu_commands_work_together(monkeypatch, capsys) -> None:
    cars = app.create_demo_cars()
    feed(
        monkeypatch,
        ["1", "2", "bmw", "3", "2019", "4", "5", "6", "7", "8", "bmw",
         "2020", "50000", "9", "10", "Kia", "Rio", "2020", "9000", "15000",
         "99", "0"],
    )
    app.run_menu(cars)
    out = capsys.readouterr().out
    assert "Average price" in out
    assert "Unknown command." in out
    assert "Goodbye." in out
    assert any(car.brand == "Kia" for car in cars)


def test_menu_shows_error_for_invalid_new_car(monkeypatch, capsys) -> None:
    cars = app.create_demo_cars()
    feed(monkeypatch, ["10", "Kia", "Rio", "1800", "9000", "15000", "0"])
    app.run_menu(cars)
    assert "Error:" in capsys.readouterr().out
    assert len(cars) == 5


def test_menu_on_empty_catalog(monkeypatch, capsys) -> None:
    feed(monkeypatch, ["4", "6", "0"])
    app.run_menu([])
    assert capsys.readouterr().out.count("(no cars)") == 2


def test_menu_survives_closed_input(monkeypatch) -> None:
    def raise_eof(_: str = "") -> str:
        raise EOFError

    monkeypatch.setattr("builtins.input", raise_eof)
    app.run_menu([])  # must return without an exception


def test_main_in_pipe_runs_only_the_demo(monkeypatch, capsys) -> None:
    monkeypatch.setattr(sys, "stdin", io.StringIO(""))
    app.main()
    out = capsys.readouterr().out
    assert "STATISTICS" in out
    assert "1. Show all cars" not in out


def test_main_in_terminal_opens_the_menu(monkeypatch, capsys) -> None:
    monkeypatch.setattr(sys, "stdin", FakeTerminal(""))
    feed(monkeypatch, ["0"])
    app.main()
    out = capsys.readouterr().out
    assert "1. Show all cars" in out
    assert "Goodbye." in out


# --- paths that the first coverage report showed as not covered ---------


def close_input(monkeypatch: pytest.MonkeyPatch) -> None:
    def raise_eof(_: str = "") -> str:
        raise EOFError

    monkeypatch.setattr("builtins.input", raise_eof)


def test_demo_on_empty_catalog_skips_the_summary_lines(capsys) -> None:
    app.run_demo([])
    out = capsys.readouterr().out
    assert "(no cars)" in out
    assert "Most expensive car" not in out
    assert "Lowest mileage car" not in out


def test_read_number_returns_none_when_input_is_closed(monkeypatch) -> None:
    close_input(monkeypatch)
    assert app.read_number("Year: ", int) is None


def test_read_new_car_returns_none_when_input_is_closed(monkeypatch) -> None:
    close_input(monkeypatch)
    assert app.read_new_car() is None


@pytest.mark.parametrize("command", ["2", "3", "10"])
def test_commands_do_nothing_when_input_closes_midway(
    monkeypatch, sample_cars, command
) -> None:
    close_input(monkeypatch)
    before = list(sample_cars)
    app.handle_command(command, sample_cars)
    assert sample_cars == before


def test_module_executed_as_script_runs_main(monkeypatch, capsys) -> None:
    import runpy

    monkeypatch.setattr(sys, "stdin", io.StringIO(""))
    # run the file as a script: drop the cached module first
    monkeypatch.delitem(sys.modules, "car_catalog.main")
    runpy.run_module("car_catalog.main", run_name="__main__")
    assert "STATISTICS" in capsys.readouterr().out
