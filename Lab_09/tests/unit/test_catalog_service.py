"""Unit tests of CatalogService with mocks and a fake repository."""

from pathlib import Path
from unittest.mock import Mock, call, create_autospec, patch

import pytest

from car_catalog import services
from car_catalog.config import AppConfig
from car_catalog.exceptions import (
    CarImportError,
    ExternalServiceError,
    InvalidCarDataError,
)
from car_catalog.repositories import InMemoryVehicleRepository
from car_catalog.services import CatalogService


@pytest.fixture
def repo_mock() -> Mock:
    """Mock of the repository boundary; autospec rejects wrong calls."""
    return create_autospec(InMemoryVehicleRepository, instance=True)


# --- state testing with a fake -----------------------------------------


def test_service_with_fake_repository_answers_queries(repository) -> None:
    service = CatalogService(repository)
    best = service.most_expensive()
    assert best is not None
    assert best.full_name == "BMW X5"
    assert service.average_price() == pytest.approx(28700.0)
    assert service.lowest_mileage().mileage == 9000  # type: ignore[union-attr]
    assert len(service.find_by_brand("bmw")) == 2
    assert [c.model for c in service.find_by_model("a4")] == ["A4"]
    assert len(service.filter_by_year(2022)) == 1


def test_service_on_empty_repository(repo_mock: Mock) -> None:
    repo_mock.list_all.return_value = []
    service = CatalogService(repo_mock)
    assert service.most_expensive() is None
    assert service.average_price() == 0.0


# --- interaction testing with Mock -------------------------------------


def test_add_car_stores_the_car_exactly_once(repo_mock, car_factory) -> None:
    car = car_factory()
    result = CatalogService(repo_mock).add_car(car)
    assert result is car
    repo_mock.add.assert_called_once_with(car)


def test_invalid_car_is_never_sent_to_the_repository(
    repo_mock, car_factory
) -> None:
    service = CatalogService(repo_mock, AppConfig(max_price=1000.0))
    with pytest.raises(InvalidCarDataError):
        service.add_car(car_factory(price=5000.0))
    repo_mock.add.assert_not_called()


def test_return_value_of_repository_is_used_by_queries(
    repo_mock, car_factory
) -> None:
    repo_mock.list_all.return_value = [
        car_factory(price=10.0),
        car_factory(price=30.0),
    ]
    service = CatalogService(repo_mock)
    assert service.average_price() == pytest.approx(20.0)
    repo_mock.list_all.assert_called_once_with()


def test_import_csv_adds_every_car_in_order(repo_mock, csv_file: Path) -> None:
    count = CatalogService(repo_mock).import_csv(csv_file)
    assert count == 5
    assert repo_mock.add.call_count == 5
    first_models = [c.args[0].model for c in repo_mock.add.call_args_list[:2]]
    assert first_models == ["Camry", "X5"]


def test_failed_import_does_not_touch_the_repository(
    repo_mock, write_csv
) -> None:
    path = write_csv("Kia,Rio,2020,9000,100\nBad,Row,xxxx,1,1\n")
    with pytest.raises(CarImportError):
        CatalogService(repo_mock).import_csv(path)
    repo_mock.add.assert_not_called()


def test_import_can_be_isolated_with_monkeypatch(
    repo_mock, car_factory, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    cars = [car_factory(), car_factory(model="Corolla")]
    fake_import = Mock(return_value=cars)
    monkeypatch.setattr(services, "import_cars_csv", fake_import)
    config = AppConfig()
    service = CatalogService(repo_mock, config)
    path = tmp_path / "ignored.csv"
    assert service.import_csv(path, skip_invalid=True) == 2
    fake_import.assert_called_once_with(path, config, True)
    assert repo_mock.add.mock_calls == [call(cars[0]), call(cars[1])]


def test_export_json_uses_the_repository_content(
    repo_mock, car_factory, tmp_path: Path
) -> None:
    repo_mock.list_all.return_value = [car_factory()]
    target = tmp_path / "out.json"
    with patch.object(services, "export_cars_json", return_value=1) as export:
        assert CatalogService(repo_mock).export_json(target) == 1
    export.assert_called_once_with(repo_mock.list_all.return_value, target)


# --- external service: return_value and side_effect --------------------


def test_describe_merges_external_data(car_factory) -> None:
    info = Mock()
    info.lookup.return_value = {"body": "SUV", "country": "Germany"}
    service = CatalogService(InMemoryVehicleRepository(), info_service=info)
    result = service.describe(car_factory(brand="BMW", model="X5"))
    assert result == {"name": "BMW X5", "body": "SUV", "country": "Germany"}
    info.lookup.assert_called_once_with("BMW", "X5")


@pytest.mark.parametrize(
    "failure", [ConnectionError("down"), TimeoutError("slow"), OSError("io")]
)
def test_external_failure_is_translated_and_chained(
    car_factory, failure: Exception
) -> None:
    info = Mock()
    info.lookup.side_effect = failure
    service = CatalogService(InMemoryVehicleRepository(), info_service=info)
    with pytest.raises(ExternalServiceError, match="Toyota Camry") as excinfo:
        service.describe(car_factory())
    assert excinfo.value.__cause__ is failure


def test_side_effect_sequence_first_fails_then_succeeds(car_factory) -> None:
    info = Mock()
    info.lookup.side_effect = [TimeoutError("slow"), {"body": "sedan"}]
    service = CatalogService(InMemoryVehicleRepository(), info_service=info)
    car = car_factory()
    with pytest.raises(ExternalServiceError):
        service.describe(car)
    assert service.describe(car)["body"] == "sedan"
    assert info.lookup.call_count == 2


def test_unexpected_error_of_external_service_is_not_hidden(
    car_factory,
) -> None:
    info = Mock()
    info.lookup.side_effect = KeyError("bug in the service")
    service = CatalogService(InMemoryVehicleRepository(), info_service=info)
    with pytest.raises(KeyError):
        service.describe(car_factory())


def test_describe_without_configured_service(car_factory) -> None:
    service = CatalogService(InMemoryVehicleRepository())
    with pytest.raises(ExternalServiceError, match="not set"):
        service.describe(car_factory())


def test_failure_of_info_service_does_not_change_the_catalog(
    repository, car_factory
) -> None:
    info = Mock()
    info.lookup.side_effect = ConnectionError
    service = CatalogService(repository, info_service=info)
    before = len(repository)
    with pytest.raises(ExternalServiceError):
        service.describe(car_factory())
    assert len(repository) == before
