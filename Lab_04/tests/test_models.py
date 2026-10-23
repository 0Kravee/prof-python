"""Tests for Vehicle, Car and ElectricCar."""

import pytest

from domain_app.exceptions import ValidationError
from domain_app.models import Car, ElectricCar, Vehicle
from domain_app.protocols import HasId
from domain_app.value_objects import Mileage, Money, VehicleSpecification


def test_abstract_vehicle_cannot_be_instantiated() -> None:
    with pytest.raises(TypeError):
        Vehicle("A", "B", 2020, 1, 1)  # type: ignore[abstract]


def test_car_composition_and_properties() -> None:
    car = Car("Toyota", "Camry", 2019, 21500, 45000, 1)
    assert isinstance(car.specification, VehicleSpecification)
    assert isinstance(car.price, Money) and isinstance(car.mileage, Mileage)
    assert (car.brand, car.model, car.year) == ("Toyota", "Camry", 2019)
    assert car.vehicle_id == car.id == 1
    assert car.energy_type == "petrol"
    assert car.is_newer_than(2018) and not car.is_newer_than(2019)


def test_inheritance_and_substitutability() -> None:
    electric = ElectricCar(
        "Tesla",
        "Model 3",
        2022,
        41000,
        15000,
        5,
        battery_kwh=75,
        range_km=491,
    )
    assert isinstance(electric, Car) and isinstance(electric, Vehicle)
    assert electric.energy_type == "electric"
    assert "battery 75 kWh" in electric.describe()

    def use_car(car: Car) -> str:  # an ElectricCar can be used as a Car
        return car.describe()

    assert "Tesla Model 3" in use_car(electric)


def test_electric_car_validation() -> None:
    with pytest.raises(ValidationError):
        ElectricCar("T", "M", 2022, 1, 1, battery_kwh=0, range_km=10)
    with pytest.raises(ValidationError):
        ElectricCar("T", "M", 2022, 1, 1, battery_kwh=10, range_km=0)


def test_price_property_and_reprice() -> None:
    car = Car("A", "B", 2020, 1000, 0, 1)
    car.price = Money.of(900)
    assert car.price == Money.of(900)
    car.reprice(800.5)
    assert car.price == Money.of("800.50")
    car.apply_discount(50)
    assert car.price == Money.of("400.25")
    with pytest.raises(ValidationError):
        car.reprice(-1)


def test_encapsulation_of_mileage() -> None:
    car = Car("A", "B", 2020, 1000, 100, 1)
    car.drive(50)
    assert car.mileage == Mileage(150)
    car.mileage = Mileage(200)
    assert car.mileage == Mileage(200)
    with pytest.raises(ValidationError):
        car.mileage = Mileage(10)
    with pytest.raises(ValidationError):
        car.drive(-1)


def test_invalid_vehicle_data() -> None:
    with pytest.raises(ValidationError):
        Car("", "B", 2020, 1, 1, 1)
    with pytest.raises(ValidationError):
        Car("A", "B", 1500, 1, 1, 1)
    with pytest.raises(ValidationError):
        Car("A", "B", 2020, 1, 1, 0)


def test_auto_generated_ids_are_unique() -> None:
    first = Car("A", "B", 2020, 1, 1)
    second = Car("A", "B", 2020, 1, 1)
    assert first.vehicle_id != second.vehicle_id and first != second


def test_dunder_methods() -> None:
    car = Car("Toyota", "Camry", 2019, 21500, 45000, 7)
    same = Car("Other", "Model", 2000, 1, 1, 7)
    assert car == same and hash(car) == hash(same)
    assert car != "text" and car != Car("A", "B", 2020, 1, 1, 8)
    assert repr(car).startswith("Car(id=7, 'Toyota Camry (2019)'")
    assert str(car) == car.describe()


def test_has_id_structural_typing() -> None:
    car: HasId = Car("A", "B", 2020, 1, 1, 3)
    assert car.id == 3
