"""Demonstration of the database version of the car catalog.

    python -m car_catalog.db_main                   # in-memory database
    python -m car_catalog.db_main --database cars.db  # keeps a SQLite file

The program never asks for input, so it also works in pipes and CI.
"""

import argparse
import sys
from collections.abc import Sequence

from car_catalog.database import (
    create_db_engine,
    create_session_factory,
    init_db,
)
from car_catalog.db_services import CarDatabaseService
from car_catalog.exceptions import CarCatalogError
from car_catalog.orm_models import CarEntity

SEED = (
    (
        "Toyota",
        "Japan",
        [
            ("Corolla", 2022, 19800.0, 9000, "JTDKARFU5H3000002"),
            ("Camry", 2019, 21500.0, 45000, "4T1BF1FK5HU000001"),
        ],
    ),
    (
        "BMW",
        "Germany",
        [
            ("X5", 2021, 48200.0, 18000, "5UXKR0C58J0000003"),
            ("3 Series", 2020, 31000.0, 27000, "WBA8E9C50GK000004"),
        ],
    ),
    (
        "Audi",
        "Germany",
        [
            ("A4", 2018, 23000.0, 62000, "WAUZZZ8K9DA000005"),
        ],
    ),
)


def describe(entity: CarEntity | None) -> str:
    if entity is None:
        return "(none)"
    return (
        f"{entity.manufacturer.name} {entity.model} ({entity.year}), "
        f"{entity.price:.2f} USD, {entity.mileage} km, VIN {entity.vin}"
    )


def seed(service: CarDatabaseService) -> None:
    for name, country, cars in SEED:
        service.add_manufacturer(name, country)
        for model, year, price, mileage, vin in cars:
            service.add_car(name, model, year, price, mileage, vin)


def run_demo(service: CarDatabaseService) -> None:
    print("=== CARS IN DATABASE ===")
    for entity in service.cars.list_all():
        print(f"{entity.id:>3}  {describe(entity)}")
    print("\n=== LAB 1 FUNCTIONS (SQL) ===")
    print("BMW cars:", [e.model for e in service.find_by_brand("bmw")])
    print("Year 2021:", [e.model for e in service.filter_by_year(2021)])
    print("Most expensive:", describe(service.most_expensive()))
    print(f"Average price: {service.average_price():.2f} USD")
    print("Lowest mileage:", describe(service.lowest_mileage()))
    print("\n=== CARS PER MANUFACTURER (GROUP BY) ===")
    for name, count, average in service.cars.stats_by_manufacturer():
        print(f"{name:<8} {count} car(s), average {average:.2f} USD")
    print("\n=== TRANSACTION: +10% for BMW ===")
    updated = service.bulk_update_prices("BMW", 10)
    print(
        f"Updated cars: {updated}, new prices:",
        [e.price for e in service.find_by_brand("BMW")],
    )
    print("\n=== TRANSACTION WITH ERROR: +46500% for Toyota ===")
    print("(the first car is updated, the second becomes too expensive)")
    before = [e.price for e in service.find_by_brand("Toyota")]
    try:
        service.bulk_update_prices("Toyota", 46500)
    except CarCatalogError as exc:
        print(f"Rolled back: {exc}")
    after = [e.price for e in service.find_by_brand("Toyota")]
    print("Prices unchanged:", before == after, after)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--database",
        help="path to a SQLite file (default: temporary in-memory database)",
    )
    args = parser.parse_args(argv)
    url = f"sqlite:///{args.database}" if args.database else "sqlite://"
    engine = create_db_engine(url)
    init_db(engine)
    factory = create_session_factory(engine)
    with factory() as session:
        service = CarDatabaseService(session)
        if not service.manufacturers.list_all():
            seed(service)
        run_demo(service)
    return 0


if __name__ == "__main__":
    sys.exit(main())
