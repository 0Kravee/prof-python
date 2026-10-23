"""Demonstration scenario of the typed vehicle catalog."""

import sys
from collections.abc import Callable
from dataclasses import FrozenInstanceError, dataclass
from pathlib import Path

# Allows running this file directly (``python main.py``) without
# installing the package: the ``src`` directory is added to sys.path.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from domain_app.container import build_container  # noqa: E402
from domain_app.criteria import (  # noqa: E402
    BrandCriteria,
    ModelCriteria,
    YearRangeCriteria,
)
from domain_app.dto import parse_payload  # noqa: E402
from domain_app.exceptions import CatalogError  # noqa: E402
from domain_app.experiments import CoupledCatalogService  # noqa: E402
from domain_app.generics import clamp  # noqa: E402
from domain_app.models import Car, ElectricCar, Vehicle  # noqa: E402
from domain_app.notifiers import (  # noqa: E402
    ConsoleNotifier,
    InMemoryNotifier,
)
from domain_app.processing import (  # noqa: E402
    DelimiterParser,
    MinYearValidator,
    PositivePriceValidator,
    PriceFormatter,
    Processor,
    RecentCsvProcessor,
    SemicolonProcessor,
    TitleFormatter,
)
from domain_app.protocols import Notifier  # noqa: E402
from domain_app.repositories import InMemoryRepository  # noqa: E402
from domain_app.services import CatalogService  # noqa: E402
from domain_app.value_objects import Mileage, Money  # noqa: E402


@dataclass
class Dealer:
    """Another entity: it satisfies HasId, so the same repository fits."""

    id: int
    name: str


def section(title: str) -> None:
    print(f"\n=== {title} ===")


def show(vehicles: list[Vehicle]) -> None:
    if not vehicles:
        print("  (nothing found)")
    for vehicle in vehicles:
        print(f"  {vehicle}")


def create_demo_vehicles() -> list[Vehicle]:
    """Demo data: the cars of the previous laboratory works + 2 EVs."""
    return [
        Car("Toyota", "Camry", 2019, 21500, 45000, 1),
        Car("BMW", "X5", 2021, 48200, 18000, 2, body_type="suv"),
        Car("Toyota", "Corolla", 2022, 19800, 9000, 3),
        Car("Audi", "A4", 2018, 23000, 62000, 4),
        Car("BMW", "3 Series", 2020, 31000, 27000, 5),
        ElectricCar(
            "Tesla",
            "Model 3",
            2022,
            41000,
            15000,
            6,
            battery_kwh=75,
            range_km=491,
        ),
        ElectricCar(
            "Tesla",
            "Model Y",
            2023,
            52000,
            8000,
            7,
            battery_kwh=82,
            range_km=533,
            body_type="suv",
        ),
    ]


def demo_use_cases(service: CatalogService) -> None:
    section("Use cases of the application service")
    print("Search by brand 'bmw':")
    show(service.search_by_brand("bmw"))
    print("Search by model 'Corolla':")
    show(service.search_by_model("Corolla"))
    print("Free-text search 'ser':")
    show(service.search_by_text("ser"))
    print("Filter by year 2022:")
    show(service.filter_by_year(2022))
    print(f"Most expensive: {service.most_expensive()}")
    print(f"Average price: {service.average_price()}")
    print(f"Lowest mileage: {service.lowest_mileage()}")
    stats = service.statistics()
    print(
        f"Statistics: {stats.count} vehicles, total {stats.total_value}, "
        f"average {stats.average_price}"
    )


def demo_criteria(service: CatalogService) -> None:
    section("Search criteria abstraction (strategy)")
    recent_bmw = BrandCriteria("BMW") & YearRangeCriteria(min_year=2021)
    print("BMW and year >= 2021:")
    show(service.search(recent_bmw))
    print("Toyota Corolla or any Tesla:")
    show(service.search(ModelCriteria("Corolla") | BrandCriteria("Tesla")))
    print("Everything except Toyota:")
    show(service.search(~BrandCriteria("Toyota")))


def demo_catalog(service: CatalogService) -> None:
    section("VehicleCatalog: custom collection and dunder methods")
    catalog = service.catalog()
    print(f"len(catalog) = {len(catalog)}, repr = {catalog!r}")
    print(f"catalog[0] = {catalog[0]!r}")
    print(f"catalog[1:3] = {catalog[1:3]}")
    print(f"3 in catalog: {3 in catalog}, 99 in catalog: {99 in catalog}")
    electric = catalog.of_type(ElectricCar)
    print(
        "of_type(ElectricCar) keeps the exact type:",
        [f"{car.model} {car.battery_kwh:g} kWh" for car in electric],
    )
    print("Iteration:", [vehicle.model for vehicle in catalog])


def demo_value_objects_and_encapsulation(service: CatalogService) -> None:
    section("Value objects, properties and encapsulation")
    price = Money.of(21500)
    print(f"Money + Money = {price + Money.of('500.50')}, x2 = {price * 2}")
    print(f"Money comparison (total_ordering): {price < Money.of(30000)}")
    print(f"Discount 10%: {price.discounted(10)}")
    try:
        price.amount = price.amount + 1  # type: ignore[misc]
    except FrozenInstanceError:
        print("Money is frozen: attribute assignment is rejected")
    car = service.get(1)
    car.drive(1000)
    print(f"After drive(1000): {car.mileage}")

    def rollback() -> None:
        car.mileage = Mileage(10)

    def negative_drive() -> None:
        car.drive(-5)

    def negative_price() -> None:
        car.reprice(-1)

    actions: dict[str, Callable[[], None]] = {
        "mileage rollback": rollback,
        "negative drive": negative_drive,
        "negative price": negative_price,
    }
    for action, change in actions.items():
        try:
            change()
        except CatalogError as error:
            print(f"Rejected ({action}): {error}")


def demo_payload(service: CatalogService) -> None:
    section("TypedDict payload -> domain object")
    raw: dict[str, object] = {
        "kind": "electric",
        "brand": "Nissan",
        "model": "Leaf",
        "year": 2021,
        "price": 24500,
        "mileage": 21000,
        "battery_kwh": 40,
        "range_km": 270,
        "vehicle_id": 8,
    }
    vehicle = service.add_from_payload(parse_payload(raw))
    print(f"Created from payload: {vehicle!r}")
    for bad in (
        {**raw, "year": "2021", "vehicle_id": 9},
        {"kind": "bike", "brand": "X"},
    ):
        try:
            parse_payload(bad)
        except CatalogError as error:
            print(f"Invalid payload rejected: {error}")


def demo_protocols_and_generics() -> None:
    section("Protocol, runtime_checkable, generics")
    print(
        "ConsoleNotifier is a Notifier:",
        isinstance(ConsoleNotifier(), Notifier),
    )
    print("object() is a Notifier:", isinstance(object(), Notifier))

    dealers = InMemoryRepository[Dealer]([Dealer(1, "Lviv Motors")])
    dealers.add(Dealer(2, "Kyiv Auto"))
    print("Generic repository of another entity:", dealers.list_all())
    print(f"clamp(150, 0, 100) = {clamp(150, 0, 100)}")
    print(f"clamp(-2.5, 0.0, 1.0) = {clamp(-2.5, 0.0, 1.0)}")


def demo_inheritance_vs_composition() -> None:
    section("Research: inheritance vs composition")
    lines = [
        "Toyota,Camry,2019,21500,45000",
        "BMW,X5,2021,48200,18000",
        "Tesla;Model 3;2022;41000;15000",
        "broken line",
    ]
    print(
        "Inheritance, SemicolonProcessor:", SemicolonProcessor().process(lines)
    )
    print(
        "Inheritance, RecentCsvProcessor:", RecentCsvProcessor().process(lines)
    )
    combined = Processor(
        DelimiterParser(";"), MinYearValidator(2020), PriceFormatter()
    )
    print("Composition, semicolon + recent + price format:")
    print(" ", combined.process(lines))
    default = Processor(
        DelimiterParser(","), PositivePriceValidator(), TitleFormatter()
    )
    print("Composition, default parts:", default.process(lines))


def demo_dependency_injection() -> None:
    section("Research: dependency injection")
    print("Variant A (service creates ConsoleNotifier itself):")
    coupled = CoupledCatalogService()
    coupled.add_vehicle(Car("Skoda", "Octavia", 2023, 26500, 1200, 20))
    print("Variant B (notifier injected, here an in-memory one):")
    notifier = InMemoryNotifier()
    container = build_container(notifier=notifier)
    container.service.add_vehicle(
        Car("Skoda", "Octavia", 2023, 26500, 1200, 20)
    )
    print(f"  captured without printing: {notifier.messages}")


def main() -> None:
    container = build_container(notifier=ConsoleNotifier())
    service = container.service

    section("Adding vehicles (notifications go through the Notifier)")
    for vehicle in create_demo_vehicles():
        service.add_vehicle(vehicle)
    print(f"Stored vehicles: {service.count()}")
    print(f"repr: {service.get(2)!r}")
    print(f"is-a: ElectricCar is Car -> {isinstance(service.get(6), Car)}")
    print(f"describe(): {service.get(6)}")

    demo_use_cases(service)
    demo_criteria(service)
    demo_catalog(service)
    demo_value_objects_and_encapsulation(service)
    demo_payload(service)
    demo_protocols_and_generics()
    demo_inheritance_vs_composition()
    demo_dependency_injection()
    print("\nStatic check: python -m mypy   (strict mode)")


if __name__ == "__main__":
    main()
