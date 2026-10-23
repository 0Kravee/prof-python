"""Tests for the research modules (design comparisons)."""

import pytest

from domain_app.experiments import CoupledCatalogService
from domain_app.models import Car
from domain_app.notifiers import ConsoleNotifier, InMemoryNotifier
from domain_app.container import build_container
from domain_app.processing import (
    BaseProcessor,
    CsvProcessor,
    DelimiterParser,
    MinYearValidator,
    PositivePriceValidator,
    PriceFormatter,
    Processor,
    RecentCsvProcessor,
    SemicolonProcessor,
    TitleFormatter,
)

LINES = [
    "Toyota,Camry,2019,21500,45000",
    "BMW,X5,2021,48200,18000",
    "Tesla;Model 3;2022;41000;15000",
    "broken line",
    "Audi,A4,2018,0,62000",
    "Audi,A4,year,23000,62000",
]


def test_base_processor_is_abstract() -> None:
    with pytest.raises(TypeError):
        BaseProcessor()  # type: ignore[abstract]


def test_inheritance_and_composition_give_the_same_result() -> None:
    by_inheritance = CsvProcessor().process(LINES)
    by_composition = Processor(
        DelimiterParser(","), PositivePriceValidator(), TitleFormatter()
    ).process(LINES)
    assert by_inheritance == by_composition
    assert by_inheritance == ["Toyota Camry (2019)", "BMW X5 (2021)"]


def test_variations_by_subclassing() -> None:
    assert SemicolonProcessor().process(LINES) == ["Tesla Model 3 (2022)"]
    assert RecentCsvProcessor().process(LINES) == ["BMW X5 (2021)"]


def test_variations_by_swapping_components() -> None:
    combined = Processor(
        DelimiterParser(";"), MinYearValidator(2020), PriceFormatter()
    )
    assert combined.process(LINES) == ["Tesla Model 3: 41000.00"]


def test_coupled_service_cannot_be_isolated(
    capsys: pytest.CaptureFixture[str],
) -> None:
    coupled = CoupledCatalogService()
    coupled.add_vehicle(Car("A", "B", 2020, 1, 1, 1))
    assert "[notify] Added: A B (2020)" in capsys.readouterr().out
    assert isinstance(
        coupled.notifier, ConsoleNotifier
    )  # fixed, not injectable


def test_injected_service_is_isolated(
    capsys: pytest.CaptureFixture[str],
) -> None:
    notifier = InMemoryNotifier()
    service = build_container(notifier=notifier).service
    service.add_vehicle(Car("A", "B", 2020, 1, 1, 1))
    assert notifier.messages == ["Added: A B (2020)"]
    assert capsys.readouterr().out == ""
